import { Editor, MarkdownView, Notice, Plugin, TFile } from 'obsidian';
import { EditorView, keymap } from '@codemirror/view';
import { Prec } from '@codemirror/state';
import { GenerousLedgerSettings, GenerousLedgerSettingTab, DEFAULT_SETTINGS } from './settings';
import { ClaudeCodeProcess, checkClaudeCodeVersion } from './claude-process';
import { SessionManager } from './session-manager';
import { StreamMessage, extractStreamingText, extractTextContent, extractSessionId, extractError, extractCurrentToolUse } from './stream-parser';
import { ResponseRenderer } from './renderer';
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

	async onload() {
		await this.loadSettings();
		this.sessionManager = new SessionManager(this.app);
		await this.checkClaudeCodeSetup();
		this.checkProfileExists();

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
				await this.startOnboarding();
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
		console.log('Generous Ledger plugin unloaded');
	}

	async loadSettings() {
		this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
	}

	async saveSettings() {
		await this.saveData(this.settings);
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

		const cursor = view.state.selection.main.head;
		const paragraph = getParagraphAtCursor(view.state, cursor);

		if (!paragraph) return false;

		// Standard @Claude trigger
		if (hasClaudeMention(paragraph.text)) {
			const mentionPos = findClaudeMentionInView(view);
			this.triggerClaudeAsync(view, paragraph, mentionPos);
			return true;
		}

		// Onboarding mode: trigger without @Claude in Onboarding.md
		const activeFile = this.app.workspace.getActiveViewOfType(MarkdownView)?.file;
		if (activeFile?.path === 'Onboarding.md') {
			const text = paragraph.text.trim();
			// Don't trigger on empty lines, callout blocks, frontmatter, or headings
			if (text && !text.startsWith('>') && !text.startsWith('---') && !text.startsWith('#')) {
				this.triggerClaudeAsync(view, paragraph, null);
				return true;
			}
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
			renderer.init(editor);

			const proc = new ClaudeCodeProcess();
			this.currentProcess = proc;

			const messages: StreamMessage[] = [];
			let lastRenderedText = '';

			proc.on('message', (msg: StreamMessage) => {
				messages.push(msg);
				if (msg.type === 'result' || msg.subtype === 'error_during_execution') {
					console.log('[GL] RESULT MSG:', JSON.stringify(msg));
				} else {
					console.log('[GL] msg type:', msg.type, 'subtype:', msg.subtype);
				}

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
					console.error('[GL] execution error:', error);
					renderer.finalize('', editor);
					this.renderError(editor, error);
				} else {
					const finalText = lastRenderedText || extractTextContent(messages);
					renderer.finalize(finalText, editor);
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

	private async startOnboarding(): Promise<void> {
		const onboardingPath = 'Onboarding.md';

		// Always start fresh — delete any existing onboarding file to clear stale session IDs
		const existing = this.app.vault.getAbstractFileByPath(onboardingPath);
		if (existing instanceof TFile) {
			await this.app.vault.delete(existing);
		}
		await this.app.vault.create(onboardingPath,
			'---\nclaude_session_id:\n---\n# Onboarding\n'
		);

		const file = this.app.vault.getAbstractFileByPath(onboardingPath);
		if (file instanceof TFile) {
			const leaf = this.app.workspace.getLeaf(false);
			await leaf.openFile(file);

			const onboardingPrompt = [
				'CONTEXT: You are a personal steward — not a game assistant, not an RPG character, not a creative writing partner.',
				'You manage a real person\'s commitments, relationships, and schedule. Read CLAUDE.md for your full operating instructions.',
				'You are responding inside an Obsidian note. Your response is rendered as a callout block — do NOT use the Write tool on this file.',
				'\n\n',
				'TASK: Begin the Onboarding Protocol defined in CLAUDE.md. Say the opening statement exactly as written there, then ask the FIRST question only (identity and station).',
				'This is about the real human using this vault. Ask about their actual life — name, vocation, household, church tradition.',
				'\n\n',
				'CONSTRAINTS:',
				'- Do NOT explore the vault or read any notes.',
				'- Do NOT create any files yet.',
				'- Do NOT use any tools except Read on CLAUDE.md and docs/FRAMEWORK.md.',
				'- Ask exactly ONE question, then stop and wait.',
				'- Use a formal, competent tone. No fantasy language, no roleplay.',
			].join('\n');

			// Give the editor time to initialize, then send the prompt directly
			setTimeout(() => {
				this.sendPromptToEditor(file, onboardingPrompt);
			}, 500);
		}
	}

	private async sendPromptToEditor(file: TFile, prompt: string): Promise<void> {
		if (this.processingRequest) {
			new Notice('Claude is already processing a request.');
			return;
		}

		if (!this.claudeCodeReady) {
			new Notice('Claude Code not ready. Check settings or install the CLI.');
			return;
		}

		const activeView = this.app.workspace.getActiveViewOfType(MarkdownView);
		if (!activeView || activeView.file !== file) return;

		const editor = activeView.editor;
		this.processingRequest = true;

		try {
			const sessionResult = await this.sessionManager.getSessionId(file);
			const vaultPath = (this.app.vault.adapter as any).basePath;

			const renderer = new ResponseRenderer();
			renderer.init(editor);

			const proc = new ClaudeCodeProcess();
			this.currentProcess = proc;

			const messages: StreamMessage[] = [];
			let lastRenderedText = '';

			proc.on('message', (msg: StreamMessage) => {
				messages.push(msg);

				if (msg.type === 'stream_event' || msg.type === 'assistant') {
					const newText = extractStreamingText(messages) || extractTextContent(messages);
					if (newText && newText !== lastRenderedText) {
						lastRenderedText = newText;
						setTimeout(() => renderer.append(newText, editor), 0);
					}
				}
			});

			proc.on('close', async () => {
				const newSessionId = extractSessionId(messages);
				if (newSessionId) {
					await this.sessionManager.setSessionId(file, newSessionId);
				}

				const error = extractError(messages);
				if (error) {
					console.error('[GL] execution error:', error);
					renderer.finalize('', editor);
					this.renderError(editor, error);
				} else {
					const finalText = lastRenderedText || extractTextContent(messages);
					renderer.finalize(finalText, editor);
				}
				this.currentProcess = null;
				this.processingRequest = false;
			});

			proc.on('error', (error: Error) => {
				console.error('Claude Code error:', error);
				const errorMessage = error instanceof Error ? error.message : 'Unknown error';
				new Notice(`Claude error: ${errorMessage}`);
				this.renderError(editor, errorMessage);
				this.currentProcess = null;
				this.processingRequest = false;
			});

			await proc.query(prompt, {
				cwd: vaultPath,
				sessionId: sessionResult.sessionId || undefined,
				model: this.settings.model,
				claudeCodePath: this.settings.claudeCodePath,
				timeoutMs: 15 * 60 * 1000,
			});

		} catch (error) {
			console.error('Claude request error:', error);
			const errorMessage = error instanceof Error ? error.message : 'Unknown error';
			new Notice(`Claude error: ${errorMessage}`);
			this.renderError(editor, errorMessage);
			this.processingRequest = false;
		}
	}

	private getEditorView(editor: Editor): EditorView | null {
		// @ts-ignore -- Obsidian internal API
		return editor.cm as EditorView;
	}
}
