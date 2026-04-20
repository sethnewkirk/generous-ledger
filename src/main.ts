import { Editor, MarkdownView, Notice, Plugin, TFile, normalizePath } from 'obsidian';
import { Prec } from '@codemirror/state';
import { EditorView, keymap } from '@codemirror/view';
import { DEFAULT_SETTINGS, GenerousLedgerSettings, GenerousLedgerSettingTab } from './settings';
import { checkClaudeCodeVersion } from './claude-process';
import { checkCodexExecStatus } from './codex-process';
import { captureActivitySnapshot, buildActivitySummary, diffActivitySnapshots } from './activity-tracker';
import { StewardThreadStore, createThreadTitle } from './chat-store';
import { StewardChatView, STEWARD_CHAT_VIEW_TYPE } from './chat-view';
import { NoteIntent, NoteWritebackAction, StewardThread, StewardTurn } from './chat-types';
import { buildChatPrompt, buildOnboardingPrompt, parseOnboardingCompletion } from './conversation-prompts';
import { runProviderTurn } from './conversation-runtime';
import { StewardOnboardingView, STEWARD_ONBOARDING_VIEW_TYPE } from './onboarding-view';
import { getRangeForOffsets, createNoteIntent, buildLinkedNoteContent, buildLinkedNotePath, insertCalloutIntoNoteText, replaceSelectionInNoteText, selectionStillMatches } from './note-context';
import { getConfiguredHandle, getMissingProviderNotice, getProviderBinaryPath, getProviderModel, normalizeConfiguredProvider } from './provider-config';
import { AssistantProvider, getProviderDisplayName } from './provider-types';
import { SessionManager } from './session-manager';
import { TerminalSessionStore } from './terminal-session';
import {
	claudeIndicatorField,
	findAssistantMentionInView,
	getParagraphAtCursor,
	hasAssistantMention,
	ParagraphBounds,
	removeAssistantMentionFromText,
	setIndicatorState,
} from './trigger';

interface SendCallbacks {
	onAssistantText?: (text: string) => void;
}

export default class GenerousLedgerPlugin extends Plugin {
	settings: GenerousLedgerSettings;
	private sessionManager!: SessionManager;
	private processingRequest = false;
	private threadStore!: StewardThreadStore;
	private legacyOnboardingSession!: TerminalSessionStore;
	private chatView: StewardChatView | null = null;
	private onboardingView: StewardOnboardingView | null = null;

	async onload() {
		await this.loadSettings();
		this.sessionManager = new SessionManager(this.app);
		this.threadStore = new StewardThreadStore(this.app.vault.adapter as any);
		this.legacyOnboardingSession = new TerminalSessionStore(this);
		await this.legacyOnboardingSession.load();
		await this.threadStore.ensureStore();
		await this.migrateLegacyOnboardingSession();
		await this.checkConfiguredProviderSetup(false);
		this.checkProfileExists();

		this.registerView(STEWARD_CHAT_VIEW_TYPE, (leaf) => {
			const view = new StewardChatView(leaf, this);
			this.chatView = view;
			return view;
		});

		this.registerView(STEWARD_ONBOARDING_VIEW_TYPE, (leaf) => {
			const view = new StewardOnboardingView(leaf, this);
			this.onboardingView = view;
			return view;
		});

		this.addSettingTab(new GenerousLedgerSettingTab(this.app, this));

		this.registerEditorExtension([
			claudeIndicatorField,
			Prec.highest(keymap.of([{
				key: 'Enter',
				run: (view: EditorView) => this.handleEnterKey(view),
			}])),
		]);

		this.registerEvent(
			this.app.workspace.on('editor-change', (editor: Editor) => {
				this.updateVisualIndicator(editor);
			})
		);

		this.addCommand({
			id: 'open-steward-chat',
			name: 'Open Steward Chat',
			callback: async () => {
				await this.openStewardChat();
			},
		});

		this.addCommand({
			id: 'send-current-paragraph-to-chat',
			name: 'Send current paragraph to Steward Chat',
			editorCallback: async (editor: Editor) => {
				const cmView = this.getEditorView(editor);
				if (cmView) {
					await this.triggerCurrentParagraphToChat(cmView, 'command');
				}
			},
		});

		this.addCommand({
			id: 'start-onboarding',
			name: 'Begin onboarding',
			callback: async () => {
				await this.openOnboarding();
			},
		});

		this.addCommand({
			id: 'clear-session',
			name: 'Clear legacy inline conversation for this note',
			editorCallback: async (_editor: Editor, view: MarkdownView) => {
				const file = view.file;
				if (!file) {
					return;
				}

				const provider = this.getConfiguredProvider();
				await this.sessionManager.clearSession(file, provider ?? undefined);
				new Notice(provider
					? `${getProviderDisplayName(provider)} legacy inline conversation cleared for this note.`
					: 'All legacy inline assistant conversations cleared for this note.');
			},
		});

		this.addRibbonIcon('message-square', 'Open Steward Chat', async () => {
			await this.openStewardChat();
		});

		console.log('Generous Ledger plugin loaded');
	}

	onunload() {
		this.app.workspace.detachLeavesOfType(STEWARD_CHAT_VIEW_TYPE);
		this.app.workspace.detachLeavesOfType(STEWARD_ONBOARDING_VIEW_TYPE);
		console.log('Generous Ledger plugin unloaded');
	}

	getActiveProvider(): AssistantProvider | null {
		return this.getConfiguredProvider();
	}

	async loadSettings() {
		const data = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
		this.settings = {
			...data,
			provider: normalizeConfiguredProvider(data.provider),
			assistantHandle: getConfiguredHandle(data.assistantHandle),
			codexPath: data.codexPath || DEFAULT_SETTINGS.codexPath,
			claudePath: data.claudePath || DEFAULT_SETTINGS.claudePath,
			codexModel: typeof data.codexModel === 'string' ? data.codexModel : DEFAULT_SETTINGS.codexModel,
			claudeModel: typeof data.claudeModel === 'string' ? data.claudeModel : DEFAULT_SETTINGS.claudeModel,
		};
	}

	async saveSettings() {
		const allData = (await this.loadData()) || {};
		allData.provider = this.settings.provider;
		allData.assistantHandle = this.assistantHandle;
		allData.codexPath = this.settings.codexPath;
		allData.claudePath = this.settings.claudePath;
		allData.codexModel = this.settings.codexModel;
		allData.claudeModel = this.settings.claudeModel;
		await this.saveData(allData);
	}

	async listChatThreads() {
		const provider = this.getConfiguredProvider();
		if (!provider) {
			return [];
		}
		return this.threadStore.listThreads('chat', provider);
	}

	async loadChatThread(threadId: string): Promise<StewardThread | null> {
		return this.threadStore.loadThread(threadId);
	}

	async getDefaultChatThread(): Promise<StewardThread | null> {
		const provider = this.getConfiguredProvider();
		if (!provider) {
			return null;
		}

		const existing = await this.threadStore.getLatestThread('chat', provider);
		if (existing) {
			return existing;
		}

		return this.createFreshChatThread();
	}

	async createFreshChatThread(): Promise<StewardThread> {
		const provider = await this.requireConfiguredProvider();
		return this.threadStore.createThread({
			threadKind: 'chat',
			status: 'active',
			provider,
			title: 'New chat',
			runtimeSessionId: null,
			turns: [],
			sourceContext: null,
			onboardingCompletedAt: null,
		});
	}

	async openStewardChat(): Promise<StewardChatView> {
		const view = await this.activateChatView();
		const thread = await this.getDefaultChatThread();
		if (thread) {
			view.setThread(thread);
		}
		return view;
	}

	async getOrCreateOnboardingThread(): Promise<StewardThread> {
		const provider = await this.requireConfiguredProvider();
		const existing = await this.threadStore.getLatestThread('onboarding');
		if (existing) {
			if (existing.provider !== provider) {
				existing.provider = provider;
				await this.threadStore.saveThread(existing);
			}
			return existing;
		}

		return this.threadStore.createThread({
			threadKind: 'onboarding',
			status: 'active',
			provider,
			title: 'Onboarding',
			runtimeSessionId: null,
			turns: [],
			sourceContext: null,
			onboardingCompletedAt: null,
		});
	}

	async openOnboarding(): Promise<StewardOnboardingView> {
		await this.requireConfiguredProvider();
		const view = await this.activateOnboardingView();
		const thread = await this.getOrCreateOnboardingThread();
		view.setThread(thread);
		return view;
	}

	async restartOnboarding(): Promise<StewardThread> {
		const provider = await this.requireConfiguredProvider();
		return this.threadStore.createThread({
			threadKind: 'onboarding',
			status: 'active',
			provider,
			title: 'Onboarding',
			runtimeSessionId: null,
			turns: [],
			sourceContext: null,
			onboardingCompletedAt: null,
		});
	}

	async redoOnboarding(): Promise<StewardThread> {
		const thread = await this.getOrCreateOnboardingThread();
		const turns = [...thread.turns];

		if (turns.length === 0) {
			return thread;
		}

		if (turns[turns.length - 1]?.role === 'assistant') {
			turns.pop();
		}
		if (turns[turns.length - 1]?.role === 'user') {
			turns.pop();
		}

		thread.turns = turns;
		thread.status = 'active';
		thread.onboardingCompletedAt = null;
		thread.runtimeSessionId = null;
		await this.threadStore.saveThread(thread);
		return thread;
	}

	async sendChatMessage(
		thread: StewardThread,
		userText: string,
		noteIntent: NoteIntent | null,
		callbacks: SendCallbacks = {}
	): Promise<StewardThread> {
		if (this.processingRequest) {
			throw new Error('Steward is already processing a request.');
		}

		const provider = await this.requireConfiguredProvider();
		await this.assertProviderReady();
		const activeThread = thread.provider === provider
			? thread
			: await this.createFreshChatThread();

		const attachedContext = noteIntent ?? activeThread.sourceContext;
		const userTurn = this.createTurn('user', userText, attachedContext);
		activeThread.turns.push(userTurn);
		activeThread.sourceContext = attachedContext;
		if (activeThread.title === 'New chat') {
			activeThread.title = createThreadTitle(userText, 'New chat');
		}
		await this.threadStore.saveThread(activeThread);

		const trackedPaths = ['profile', 'memory'];
		if (attachedContext) {
			trackedPaths.push(attachedContext.notePath);
		}
		const beforeSnapshot = captureActivitySnapshot(this.getVaultPath(), trackedPaths);

		this.processingRequest = true;
		try {
			const result = await runProviderTurn({
				provider,
				prompt: await buildChatPrompt(this.app.vault.adapter as {
					exists(path: string, sensitive?: boolean): Promise<boolean>;
					read(path: string): Promise<string>;
				}, {
					provider,
					userText,
					noteIntent: attachedContext,
				}),
				cwd: this.getVaultPath(),
				sessionId: activeThread.runtimeSessionId || undefined,
				model: getProviderModel(provider, this.settings),
				binaryPath: getProviderBinaryPath(provider, this.settings),
				timeoutMs: 15 * 60 * 1000,
			}, {
				onText: callbacks.onAssistantText,
			});

			activeThread.runtimeSessionId = result.sessionId || activeThread.runtimeSessionId;
			const afterSnapshot = captureActivitySnapshot(this.getVaultPath(), trackedPaths);
			const changedFiles = diffActivitySnapshots(beforeSnapshot, afterSnapshot);

			const assistantText = result.error
				? `Error: ${result.error}`
				: (result.text.trim() || 'Steward returned an empty response.');

			const assistantTurn = this.createTurn(
				result.error ? 'system' : 'assistant',
				assistantText,
				attachedContext,
				result.error ? null : buildActivitySummary(
					attachedContext,
					changedFiles,
					attachedContext ? ['insert-callout', 'replace-selection', 'create-linked-note'] : []
				)
			);

			activeThread.turns.push(assistantTurn);
			await this.threadStore.saveThread(activeThread);
			return activeThread;
		} finally {
			this.processingRequest = false;
		}
	}

	async sendOnboardingMessage(
		thread: StewardThread,
		userText: string | null,
		callbacks: SendCallbacks = {}
	): Promise<StewardThread> {
		if (this.processingRequest) {
			throw new Error('Steward is already processing a request.');
		}

		const provider = await this.requireConfiguredProvider();
		await this.assertProviderReady();

		const activeThread = thread;
		activeThread.provider = provider;
		activeThread.status = 'active';
		activeThread.onboardingCompletedAt = null;
		activeThread.runtimeSessionId = null;

		if (userText) {
			activeThread.turns.push(this.createTurn('user', userText, null));
		}
		await this.threadStore.saveThread(activeThread);

		this.processingRequest = true;
		try {
			const result = await runProviderTurn({
				provider,
				prompt: await buildOnboardingPrompt(this.app.vault.adapter as {
					exists(path: string, sensitive?: boolean): Promise<boolean>;
					read(path: string): Promise<string>;
				}, provider, activeThread, undefined),
				cwd: this.getVaultPath(),
				model: getProviderModel(provider, this.settings),
				binaryPath: getProviderBinaryPath(provider, this.settings),
				timeoutMs: 15 * 60 * 1000,
			}, {
				onText: callbacks.onAssistantText,
			});

			const assistantText = result.error
				? `Error: ${result.error}`
				: (result.text.trim() || 'Steward returned an empty response.');

			if (result.error) {
				activeThread.turns.push(this.createTurn('system', assistantText, null));
			} else {
				const completion = parseOnboardingCompletion(assistantText);
				activeThread.turns.push(this.createTurn('assistant', completion.cleanedText, null));
				if (completion.completed) {
					activeThread.status = 'completed';
					activeThread.onboardingCompletedAt = new Date().toISOString();
				}
			}

			await this.threadStore.saveThread(activeThread);
			return activeThread;
		} finally {
			this.processingRequest = false;
		}
	}

	async applyNoteWriteback(turn: StewardTurn, action: NoteWritebackAction): Promise<void> {
		const noteIntent = turn.noteIntent;
		if (!noteIntent) {
			new Notice('This reply has no attached note context.');
			return;
		}

		const abstractFile = this.app.vault.getAbstractFileByPath(noteIntent.notePath);
		if (!(abstractFile instanceof TFile)) {
			new Notice(`Source note not found: ${noteIntent.notePath}`);
			return;
		}

		if (action === 'create-linked-note') {
			const newPath = normalizePath(buildLinkedNotePath(noteIntent.notePath));
			const created = await this.app.vault.create(newPath, buildLinkedNoteContent(noteIntent.notePath, turn.text));
			const leaf = this.app.workspace.getLeaf('tab');
			await leaf.openFile(created);
			new Notice(`Created ${created.path}`);
			return;
		}

		const currentText = await this.app.vault.cachedRead(abstractFile);
		if (!selectionStillMatches(currentText, noteIntent)) {
			new Notice('The source note changed, so Steward will not apply this write-back automatically.');
			return;
		}

		const nextText = action === 'insert-callout'
			? insertCalloutIntoNoteText(currentText, noteIntent, turn.text, this.assistantHandle)
			: replaceSelectionInNoteText(currentText, noteIntent, turn.text);

		await this.app.vault.modify(abstractFile, nextText);
		const leaf = this.app.workspace.getLeaf(false);
		await leaf.openFile(abstractFile);
		new Notice(action === 'insert-callout' ? 'Inserted Steward callout into the note.' : 'Replaced the note selection with Steward’s reply.');
	}

	private get assistantHandle(): string {
		return getConfiguredHandle(this.settings.assistantHandle);
	}

	private getConfiguredProvider(): AssistantProvider | null {
		return normalizeConfiguredProvider(this.settings.provider);
	}

	private async requireConfiguredProvider(): Promise<AssistantProvider> {
		const provider = this.getConfiguredProvider();
		if (!provider) {
			throw new Error(getMissingProviderNotice());
		}
		return provider;
	}

	private async assertProviderReady(): Promise<void> {
		if (!(await this.checkConfiguredProviderSetup())) {
			throw new Error('The configured provider is not ready.');
		}
	}

	private async checkConfiguredProviderSetup(showNotice = true): Promise<boolean> {
		const provider = this.getConfiguredProvider();
		if (!provider) {
			if (showNotice) {
				new Notice(getMissingProviderNotice(), 10000);
			}
			return false;
		}

		if (provider === 'claude') {
			const status = await checkClaudeCodeVersion(this.settings.claudePath);
			if (!status.installed) {
				if (showNotice) {
					new Notice('Claude CLI not found. Install Claude Code or update the Claude path in settings.', 10000);
				}
				return false;
			}
			if (!status.authenticated) {
				if (showNotice) {
					new Notice('Claude is not authenticated. Run "claude" in a terminal and complete setup.', 10000);
				}
				return false;
			}
			return true;
		}

		const status = await checkCodexExecStatus(this.settings.codexPath);
		if (!status.installed || !status.ready) {
			if (showNotice) {
				new Notice(status.problem || 'Codex is not ready. Check the Codex path and local state directory.', 12000);
			}
			return false;
		}
		return true;
	}

	private checkProfileExists(): void {
		this.app.workspace.onLayoutReady(() => {
			const profileIndex = this.app.vault.getAbstractFileByPath('profile/index.md');
			if (!profileIndex) {
				new Notice(
					'Welcome to Generous Ledger. Run "Begin onboarding" or open Steward Chat to begin.',
					15000
				);
			}
		});
	}

	private updateVisualIndicator(editor: Editor) {
		if (this.processingRequest) {
			return;
		}

		const view = this.getEditorView(editor);
		if (!view) {
			return;
		}

		const mentionPos = findAssistantMentionInView(view, this.assistantHandle);
		view.dispatch({
			effects: setIndicatorState.of(
				mentionPos !== null ? { pos: mentionPos, state: 'ready' } : null
			),
		});
	}

	private handleEnterKey(view: EditorView): boolean {
		if (this.processingRequest) {
			return false;
		}

		const selection = view.state.selection.main;
		if (selection.from !== selection.to) {
			const selectedText = view.state.sliceDoc(selection.from, selection.to);
			if (hasAssistantMention(selectedText, this.assistantHandle)) {
				const bounds: ParagraphBounds = {
					from: selection.from,
					to: selection.to,
					text: selectedText,
				};
				const mentionPos = findAssistantMentionInView(view, this.assistantHandle);
				void this.handoffNoteContext(view, bounds, 'mention', mentionPos);
				return true;
			}
		}

		const paragraph = getParagraphAtCursor(view.state, selection.head);
		if (!paragraph || !hasAssistantMention(paragraph.text, this.assistantHandle)) {
			return false;
		}

		const mentionPos = findAssistantMentionInView(view, this.assistantHandle);
		void this.handoffNoteContext(view, paragraph, 'mention', mentionPos);
		return true;
	}

	private async triggerCurrentParagraphToChat(view: EditorView, triggerSource: NoteIntent['triggerSource']): Promise<void> {
		if (this.processingRequest) {
			new Notice('Steward is already processing a request.');
			return;
		}

		const cursor = view.state.selection.main.head;
		const paragraph = getParagraphAtCursor(view.state, cursor);
		if (!paragraph) {
			new Notice('No paragraph found at cursor.');
			return;
		}

		const mentionPos = findAssistantMentionInView(view, this.assistantHandle);
		await this.handoffNoteContext(view, paragraph, triggerSource, mentionPos);
	}

	private async handoffNoteContext(
		view: EditorView,
		paragraph: ParagraphBounds,
		triggerSource: NoteIntent['triggerSource'],
		mentionPos: number | null
	): Promise<void> {
		const provider = this.getConfiguredProvider();
		if (!provider) {
			new Notice(getMissingProviderNotice());
			return;
		}
		if (!(await this.checkConfiguredProviderSetup())) {
			return;
		}

		const activeView = this.app.workspace.getActiveViewOfType(MarkdownView);
		const file = activeView?.file;
		if (!activeView || !file) {
			return;
		}

		const promptText = removeAssistantMentionFromText(paragraph.text, this.assistantHandle);
		if (!promptText.trim()) {
			new Notice('Provide content for Steward to respond to.');
			return;
		}

		if (mentionPos !== null) {
			view.dispatch({
				effects: setIndicatorState.of({ pos: mentionPos, state: 'processing' }),
			});
		}

		try {
			const noteIntent = createNoteIntent(
				file,
				paragraph.text,
				promptText,
				getRangeForOffsets(view.state.doc.toString(), paragraph.from, paragraph.to),
				triggerSource
			);
			const chatView = await this.openStewardChat();
			await chatView.submitMessage(promptText, noteIntent);
		} finally {
			view.dispatch({ effects: setIndicatorState.of(null) });
		}
	}

	private async activateChatView(): Promise<StewardChatView> {
		const existing = this.app.workspace.getLeavesOfType(STEWARD_CHAT_VIEW_TYPE);
		if (existing.length > 0) {
			this.app.workspace.revealLeaf(existing[0]);
			this.chatView = existing[0].view as StewardChatView;
			return this.chatView;
		}

		const leaf = this.app.workspace.getLeaf('tab');
		await leaf.setViewState({ type: STEWARD_CHAT_VIEW_TYPE, active: true });
		this.app.workspace.revealLeaf(leaf);
		this.chatView = leaf.view as StewardChatView;
		return this.chatView;
	}

	private async activateOnboardingView(): Promise<StewardOnboardingView> {
		const existing = this.app.workspace.getLeavesOfType(STEWARD_ONBOARDING_VIEW_TYPE);
		if (existing.length > 0) {
			this.app.workspace.revealLeaf(existing[0]);
			this.onboardingView = existing[0].view as StewardOnboardingView;
			return this.onboardingView;
		}

		const leaf = this.app.workspace.getLeaf('tab');
		await leaf.setViewState({ type: STEWARD_ONBOARDING_VIEW_TYPE, active: true });
		this.app.workspace.revealLeaf(leaf);
		this.onboardingView = leaf.view as StewardOnboardingView;
		return this.onboardingView;
	}

	private async migrateLegacyOnboardingSession(): Promise<void> {
		const existing = await this.threadStore.getLatestThread('onboarding');
		if (existing) {
			return;
		}

		const log = this.legacyOnboardingSession.getLog();
		if (log.length === 0) {
			return;
		}

		const provider = this.legacyOnboardingSession.getProvider() ?? this.getConfiguredProvider();
		if (!provider) {
			return;
		}

		const thread: StewardThread = {
			threadId: 'thread_legacy_onboarding',
			threadKind: 'onboarding',
			status: 'active',
			provider,
			title: 'Onboarding',
			createdAt: new Date().toISOString(),
			updatedAt: new Date().toISOString(),
			runtimeSessionId: null,
			sourceContext: null,
			onboardingCompletedAt: null,
			turns: log.map((entry) => this.createTurn(
				entry.role === 'steward' ? 'assistant' : entry.role,
				entry.text,
				null
			)),
		};

		await this.threadStore.upsertImportedThread(thread);
		await this.legacyOnboardingSession.clear();
	}

	private createTurn(
		role: StewardTurn['role'],
		text: string,
		noteIntent: NoteIntent | null,
		activitySummary: StewardTurn['activitySummary'] = null
	): StewardTurn {
		return {
			turnId: crypto.randomUUID(),
			role,
			text,
			createdAt: new Date().toISOString(),
			noteIntent,
			activitySummary,
		};
	}

	private getVaultPath(): string {
		return (this.app.vault.adapter as { basePath?: string }).basePath || '/';
	}

	private getEditorView(editor: Editor): EditorView | null {
		// @ts-ignore Obsidian internal CodeMirror view
		return editor.cm as EditorView;
	}
}
