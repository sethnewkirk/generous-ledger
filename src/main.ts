import { Editor, MarkdownView, Notice, Plugin } from 'obsidian';
import { EditorView, keymap } from '@codemirror/view';
import { Prec } from '@codemirror/state';
import { GenerousLedgerSettings, GenerousLedgerSettingTab, DEFAULT_SETTINGS } from './settings';
import { ClaudeCodeProcess, ClaudeCodeOptions, checkClaudeCodeVersion } from './claude-process';
import { SessionManager } from './session-manager';
import { StreamMessage, extractStreamingText, extractTextContent, extractSessionId, extractError, extractCurrentToolUse, extractThinkingAndText, separateThinkingFromAnswer } from './stream-parser';
import { ResponseRenderer } from './renderer';
import { OnboardingTerminalView, TERMINAL_VIEW_TYPE } from './terminal-view';
import { TerminalSessionStore } from './terminal-session';
import {
	claudeIndicatorField,
	setIndicatorState,
	findClaudeMentionInView,
	getParagraphAtCursor,
	removeClaudeMentionFromText,
	hasClaudeMention,
	ParagraphBounds,
} from './trigger';

export default class GenerousLedgerPlugin extends Plugin {
	settings: GenerousLedgerSettings;
	private sessionManager: SessionManager;
	private currentProcess: ClaudeCodeProcess | null = null;
	private claudeCodeReady = false;
	private processingRequest = false;
	private terminalSession: TerminalSessionStore;
	private terminalView: OnboardingTerminalView | null = null;

	async onload() {
		await this.loadSettings();
		this.sessionManager = new SessionManager(this.app);
		this.terminalSession = new TerminalSessionStore(this);
		await this.terminalSession.load();
		await this.checkClaudeCodeSetup();
		this.checkProfileExists();

		this.registerView(TERMINAL_VIEW_TYPE, (leaf) => {
			const view = new OnboardingTerminalView(leaf, this);
			this.terminalView = view;
			return view;
		});

		this.addSettingTab(new GenerousLedgerSettingTab(this.app, this));

		this.registerEditorExtension([
			claudeIndicatorField,
			Prec.highest(keymap.of([{
				key: 'Enter',
				run: (view: EditorView) => this.handleEnterKey(view)
			}]))
		]);

		this.registerEvent(
			this.app.workspace.on('editor-change', (editor: Editor) => {
				this.updateVisualIndicator(editor);
			})
		);

		this.addCommand({
			id: 'ask-claude',
			name: 'Ask Claude about current paragraph',
			editorCallback: (editor: Editor, view: MarkdownView) => {
				const cmView = this.getEditorView(editor);
				if (cmView) {
					this.triggerClaude(cmView);
				}
			}
		});

		this.addCommand({
			id: 'start-onboarding',
			name: 'Begin onboarding',
			callback: async () => {
				await this.startTerminalOnboarding();
			}
		});

		this.addCommand({
			id: 'clear-session',
			name: 'Clear Claude conversation for this note',
			editorCallback: async (editor: Editor, view: MarkdownView) => {
				const file = view.file;
				if (file) {
					await this.sessionManager.clearSession(file);
					new Notice('Claude conversation cleared for this note.');
				}
			}
		});

		this.addRibbonIcon('message-square', 'Ask Claude', () => {
			const view = this.app.workspace.getActiveViewOfType(MarkdownView);
			if (!view) {
				new Notice('Open a markdown note first.');
				return;
			}
			const cmView = this.getEditorView(view.editor);
			if (cmView) {
				this.triggerClaude(cmView);
			}
		});

		console.log('Generous Ledger plugin loaded');
	}

	onunload() {
		this.currentProcess?.abort();
		this.app.workspace.detachLeavesOfType(TERMINAL_VIEW_TYPE);
		console.log('Generous Ledger plugin unloaded');
	}

	async loadSettings() {
		this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
	}

	async saveSettings() {
		const allData = (await this.loadData()) || {};
		allData.model = this.settings.model;
		allData.claudeCodePath = this.settings.claudeCodePath;
		await this.saveData(allData);
	}

	private async checkClaudeCodeSetup(): Promise<void> {
		const status = await checkClaudeCodeVersion(this.settings.claudeCodePath);

		if (!status.installed) {
			new Notice('Claude Code CLI not found. Install with: npm i -g @anthropic-ai/claude-code', 10000);
			return;
		}

		if (!status.compatible) {
			new Notice(`Claude Code v${status.version} may not be compatible. Run: npm update -g @anthropic-ai/claude-code`, 10000);
		}

		if (!status.authenticated) {
			new Notice('Claude Code not authenticated. Run "claude" in terminal to set up your API key.', 10000);
			return;
		}

		this.claudeCodeReady = true;
		console.log(`Claude Code ready: v${status.version}`);
	}

	private checkProfileExists(): void {
		// Wait for vault to be ready before checking
		this.app.workspace.onLayoutReady(() => {
			const profileIndex = this.app.vault.getAbstractFileByPath('profile/index.md');
			if (!profileIndex) {
				new Notice(
					'Welcome to Generous Ledger. Run "Start onboarding" from the command palette to begin.',
					15000
				);
			}
		});
	}

	private updateVisualIndicator(editor: Editor) {
		if (this.processingRequest) return;

		const view = this.getEditorView(editor);
		if (!view) return;

		const mentionPos = findClaudeMentionInView(view);
		view.dispatch({
			effects: setIndicatorState.of(
				mentionPos !== null ? { pos: mentionPos, state: 'ready' } : null
			)
		});
	}

	private handleEnterKey(view: EditorView): boolean {
		if (this.processingRequest) return false;

		const sel = view.state.selection.main;

		// Selection mode: if text is selected and contains @Claude, use the selection as the prompt
		if (sel.from !== sel.to) {
			const selectedText = view.state.sliceDoc(sel.from, sel.to);
			if (hasClaudeMention(selectedText)) {
				const selectionBounds: ParagraphBounds = {
					from: sel.from,
					to: sel.to,
					text: selectedText,
				};
				const mentionPos = findClaudeMentionInView(view);
				this.triggerClaudeAsync(view, selectionBounds, mentionPos);
				return true;
			}
		}

		const cursor = sel.head;
		const paragraph = getParagraphAtCursor(view.state, cursor);

		if (!paragraph) return false;

		// Standard @Claude trigger
		if (hasClaudeMention(paragraph.text)) {
			const mentionPos = findClaudeMentionInView(view);
			this.triggerClaudeAsync(view, paragraph, mentionPos);
			return true;
		}

		return false;
	}

	private triggerClaude(view: EditorView): void {
		if (this.processingRequest) {
			new Notice('Claude is already processing a request.');
			return;
		}

		const cursor = view.state.selection.main.head;
		const paragraph = getParagraphAtCursor(view.state, cursor);

		if (!paragraph) {
			new Notice('No paragraph found at cursor.');
			return;
		}

		const mentionPos = findClaudeMentionInView(view);
		this.triggerClaudeAsync(view, paragraph, mentionPos);
	}

	private async triggerClaudeAsync(view: EditorView, paragraph: ParagraphBounds, mentionPos: number | null) {
		if (this.processingRequest) return;

		const activeView = this.app.workspace.getActiveViewOfType(MarkdownView);
		if (!activeView) return;

		const editor = activeView.editor;
		const file = activeView.file;
		if (!file) return;

		if (!this.claudeCodeReady) {
			new Notice('Claude Code not ready. Check settings or install the CLI.');
			return;
		}

		const content = removeClaudeMentionFromText(paragraph.text);
		if (!content.trim()) {
			new Notice('Provide content for Claude to respond to.');
			return;
		}

		this.processingRequest = true;

		if (mentionPos !== null) {
			view.dispatch({
				effects: setIndicatorState.of({ pos: mentionPos, state: 'processing' })
			});
		}

		try {
			const sessionResult = await this.sessionManager.getSessionId(file);
			const vaultPath = (this.app.vault.adapter as any).basePath;

			const renderer = new ResponseRenderer();
			const cmView = this.getEditorView(editor);
			renderer.init(editor, cmView?.scrollDOM);

			const proc = new ClaudeCodeProcess();
			this.currentProcess = proc;

			const messages: StreamMessage[] = [];
			let lastRenderedText = '';

			proc.on('message', (msg: StreamMessage) => {
				messages.push(msg);
				if (msg.type === 'stream_event' || msg.type === 'assistant') {
					const streamText = extractStreamingText(messages);
					const contentText = extractTextContent(messages);
					const newText = streamText || contentText;
					if (newText && newText !== lastRenderedText) {
						lastRenderedText = newText;
						setTimeout(() => renderer.append(newText, editor), 0);
					}
				}

				const currentTool = extractCurrentToolUse(messages);
				if (currentTool && mentionPos !== null) {
					view.dispatch({
						effects: setIndicatorState.of({
							pos: mentionPos,
							state: 'processing',
							toolName: currentTool
						})
					});
				}
			});

			proc.on('close', async () => {
				const newSessionId = extractSessionId(messages);
				if (newSessionId) {
					await this.sessionManager.setSessionId(file, newSessionId);
				}

				const error = extractError(messages);
				if (error) {
					// error is displayed to user via renderError below
					renderer.finalize('', editor);
					this.renderError(editor, error);
				} else {
					const { thinking: streamThinking, text: streamText } = extractThinkingAndText(messages);
					const finalText = streamText || lastRenderedText || extractTextContent(messages);
					let thinkingContent = streamThinking || undefined;
					if (!thinkingContent && finalText) {
						const separated = separateThinkingFromAnswer(finalText);
						if (separated.thinking) {
							thinkingContent = separated.thinking;
							renderer.finalize(separated.answer, editor, thinkingContent);
						} else {
							renderer.finalize(finalText, editor);
						}
					} else {
						renderer.finalize(finalText, editor, thinkingContent);
					}
				}

				view.dispatch({ effects: setIndicatorState.of(null) });
				this.currentProcess = null;
				this.processingRequest = false;
			});

			proc.on('error', (error: Error) => {
				console.error('Claude Code error:', error);

				if (mentionPos !== null) {
					view.dispatch({
						effects: setIndicatorState.of({ pos: mentionPos, state: 'error' })
					});
				}

				const errorMessage = error instanceof Error ? error.message : 'Unknown error';
				new Notice(`Claude error: ${errorMessage}`);
				this.renderError(editor, errorMessage);

				this.currentProcess = null;
				this.processingRequest = false;
			});

			await proc.query(content, {
				cwd: vaultPath,
				sessionId: sessionResult.sessionId || undefined,
				model: this.settings.model,
				claudeCodePath: this.settings.claudeCodePath,
				timeoutMs: 15 * 60 * 1000,
			});

		} catch (error) {
			console.error('Claude request error:', error);

			if (mentionPos !== null) {
				view.dispatch({
					effects: setIndicatorState.of({ pos: mentionPos, state: 'error' })
				});
			}

			const errorMessage = error instanceof Error ? error.message : 'Unknown error';
			new Notice(`Claude error: ${errorMessage}`);
			this.renderError(editor, errorMessage);

			this.processingRequest = false;
		}
	}

	private renderError(editor: Editor, errorMessage: string): void {
		const cursor = editor.getCursor();
		editor.replaceRange(
			`\n\n> [!error] Claude Error\n> ${errorMessage}\n`,
			{ line: cursor.line, ch: editor.getLine(cursor.line).length }
		);
	}

	private async activateTerminalView(): Promise<OnboardingTerminalView> {
		const existing = this.app.workspace.getLeavesOfType(TERMINAL_VIEW_TYPE);
		if (existing.length > 0) {
			this.app.workspace.revealLeaf(existing[0]);
			this.terminalView = existing[0].view as OnboardingTerminalView;
			return this.terminalView;
		}
		const leaf = this.app.workspace.getLeaf('tab');
		await leaf.setViewState({ type: TERMINAL_VIEW_TYPE, active: true });
		this.app.workspace.revealLeaf(leaf);
		return this.terminalView!;
	}

	private async startTerminalOnboarding(): Promise<void> {
		if (!this.claudeCodeReady) {
			new Notice('Claude Code not ready. Check settings or install the CLI.');
			return;
		}

		const view = await this.activateTerminalView();
		view.enterFullscreen();

		// Check if profile already exists
		const profileIndex = this.app.vault.getAbstractFileByPath('profile/index.md');
		if (profileIndex) {
			view.printSystem('Profile already exists at profile/index.md.');
			view.printSystem('Type "redo" to start a new onboarding, or close this tab.');
			view.setInputEnabled(true);
			view.setSubmitHandler(async (text: string) => {
				if (text.trim().toLowerCase() === 'redo') {
					await this.terminalSession.clear();
					view.printSystem('Session cleared. Restarting onboarding...');
					view.setInputEnabled(false);
					setTimeout(() => this.beginTerminalInterview(view), 500);
				}
			});
			return;
		}

		// Check for existing session to resume
		const log = this.terminalSession.getLog();
		if (log.length > 0) {
			view.replayLog(log);
			view.printSystem('');
			view.printSystem('Session resumed.');
			view.setInputEnabled(true);
			view.setSubmitHandler((text: string) => this.sendTerminalMessage(text));
			return;
		}

		// Fresh start
		await this.beginTerminalInterview(view);
	}

	private async beginTerminalInterview(view: OnboardingTerminalView): Promise<void> {
		await this.terminalSession.start();

		// Boot sequence
		const bootLines = [
			'GENEROUS LEDGER v1.0',
			'PERSONAL STEWARD TERMINAL',
			'',
			'> Initializing...',
		];

		for (const line of bootLines) {
			view.printSystem(line);
			await new Promise(resolve => setTimeout(resolve, 200));
		}

		await new Promise(resolve => setTimeout(resolve, 400));
		view.printSystem('> Session established.');
		view.printSystem('');

		await this.terminalSession.appendLog({ role: 'system', text: 'GENEROUS LEDGER v1.0\nPERSONAL STEWARD TERMINAL\n\n> Initializing...\n> Session established.' });

		view.setSubmitHandler((text: string) => this.sendTerminalMessage(text));

		// Send initial onboarding prompt
		const onboardingPrompt = [
			'CONTEXT: You are a personal steward beginning service with a new principal.',
			'You manage a real person\'s commitments, relationships, and schedule.',
			'Read CLAUDE.md for your full operating instructions and docs/FRAMEWORK.md for your reasoning framework.',
			'',
			'Your responses appear in a terminal interface. Respond in plain text only — no markdown formatting, no headers, no bullet lists, no callout syntax.',
			'',
			'TASK: Begin the Onboarding Protocol defined in CLAUDE.md.',
			'Say the opening statement, then ask your first question about identity and station.',
			'',
			'VOICE: Competent, direct, modern. You are not a butler — do not use deferential or archaic language.',
			'You are not a therapist — do not validate, empathize, or build rapport.',
			'You serve with quiet competence. Your words should feel like a capable person learning what they need to know to do their job well.',
			'',
			'PACING: Ask in natural conversational clusters — two or three related questions grouped naturally is fine.',
			'Do not interrogate. Do not fire off a numbered list of questions.',
			'If the user gives a sparse answer, probe once, then accept it and move on.',
			'',
			'SECTIONS: The protocol defines five sections. Treat them as guidelines, not walls.',
			'If the user naturally moves into a later topic, follow the thread.',
			'When you are ready to shift focus, announce it in your own voice — do not use section numbers or labels.',
			'',
			'FILE CREATION: As you gather information, create profile files per the protocol.',
			'Do not announce that you are creating files. Do not ask for confirmation. Write them silently.',
			'',
			'When the interview is complete, offer one final open-ended question before closing.',
		].join('\n');

		await this.sendTerminalPrompt(onboardingPrompt);
	}

	private async sendTerminalMessage(text: string): Promise<void> {
		if (!this.terminalView) return;
		if (this.processingRequest) return;

		// Handle terminal commands
		const command = text.trim().toLowerCase();
		if (command === '/restart') {
			await this.handleRestart();
			return;
		}
		if (command === '/redo') {
			await this.handleRedo();
			return;
		}

		this.terminalView.printUser(text);
		this.terminalView.setInputEnabled(false);
		await this.terminalSession.appendLog({ role: 'user', text });

		const wrappedPrompt = [
			'[STEWARD TERMINAL — ongoing onboarding interview]',
			'Plain text only. No markdown. No bullet lists. No headers.',
			'Competent modern voice — not deferential, not clinical, not warm.',
			'Ask in natural clusters. Do not interrogate.',
			'If the answer was sparse, you may probe once — then move on.',
			'Follow interesting threads. Create profile files silently when ready.',
			'',
			text,
		].join('\n');

		await this.sendTerminalPrompt(wrappedPrompt);
	}

	private async handleRestart(): Promise<void> {
		if (!this.terminalView) return;

		this.terminalView.clearDisplay();
		this.terminalView.showSpinner();
		await this.terminalSession.clear();

		// Brief pause so the spinner is visible
		await new Promise(resolve => setTimeout(resolve, 600));

		this.terminalView.clearDisplay();
		await this.beginTerminalInterview(this.terminalView);
	}

	private async handleRedo(): Promise<void> {
		if (!this.terminalView) return;

		this.terminalView.printUser('');  // clears content and shows spinner
		const previousQuestion = await this.terminalSession.removeLastExchange();

		if (!previousQuestion) {
			this.terminalView.printSystem('Nothing to redo.');
			this.terminalView.setInputEnabled(true);
			return;
		}

		// Brief pause so the spinner is visible
		await new Promise(resolve => setTimeout(resolve, 600));

		this.terminalView.showQuestion(previousQuestion.text);
		this.terminalView.setInputEnabled(true);
	}

	private async sendTerminalPrompt(prompt: string): Promise<void> {
		if (!this.terminalView) return;

		this.processingRequest = true;
		const vaultPath = (this.app.vault.adapter as any).basePath;
		const sessionId = await this.terminalSession.getSessionId();

		const proc = new ClaudeCodeProcess();
		this.currentProcess = proc;

		const messages: StreamMessage[] = [];
		let lastStreamedLength = 0;

		proc.on('message', (msg: StreamMessage) => {
			messages.push(msg);

			if (msg.type === 'stream_event' || msg.type === 'assistant') {
				const fullText = extractStreamingText(messages) || extractTextContent(messages);
				if (fullText.length > lastStreamedLength) {
					const delta = fullText.slice(lastStreamedLength);
					lastStreamedLength = fullText.length;
					this.terminalView?.printSteward(delta);
				}
			}
		});

		proc.on('close', async () => {
			const newSessionId = extractSessionId(messages);
			if (newSessionId) {
				await this.terminalSession.setSessionId(newSessionId);
			}

			const error = extractError(messages);
			if (error) {
				this.terminalView?.finalizeStewardTurn();
				this.terminalView?.printSystem('ERROR: ' + error);
				this.terminalView?.setInputEnabled(true);
			} else {
				const finalText = extractStreamingText(messages) || extractTextContent(messages);
				this.terminalView?.finalizeStewardTurn();

				if (finalText) {
					await this.terminalSession.appendLog({ role: 'steward', text: finalText });
				}

				// Check if onboarding is complete
				const profileNowExists = this.app.vault.getAbstractFileByPath('profile/index.md');
				if (profileNowExists) {
					this.terminalView?.printSystem('');
					this.terminalView?.printSystem('ONBOARDING COMPLETE.');
					this.terminalView?.printSystem('Profile written to profile/index.md.');
					this.terminalView?.printSystem('This terminal may now be closed.');
					this.terminalView?.setInputEnabled(false);
					await this.terminalSession.clear();
				}
			}

			this.currentProcess = null;
			this.processingRequest = false;
		});

		proc.on('error', (error: Error) => {
			const errorMessage = error instanceof Error ? error.message : 'Unknown error';
			this.terminalView?.finalizeStewardTurn();
			this.terminalView?.printSystem('ERROR: ' + errorMessage);
			this.terminalView?.setInputEnabled(true);
			this.currentProcess = null;
			this.processingRequest = false;
		});

		const options: ClaudeCodeOptions = {
			cwd: vaultPath,
			model: this.settings.model,
			claudeCodePath: this.settings.claudeCodePath,
		};
		if (sessionId) {
			options.sessionId = sessionId;
		}

		proc.query(prompt, options);
	}

	private getEditorView(editor: Editor): EditorView | null {
		// @ts-ignore -- Obsidian internal API
		return editor.cm as EditorView;
	}
}
