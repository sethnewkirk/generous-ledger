import { Editor, MarkdownView, Notice, Plugin, TFile } from 'obsidian';
import { EditorView, keymap } from '@codemirror/view';
import { Prec } from '@codemirror/state';
import { GenerousLedgerSettings, GenerousLedgerSettingTab, DEFAULT_SETTINGS } from './settings';
import { ClaudeCodeProcess, checkClaudeCodeVersion } from './core/claude-code/process-manager';
import { SessionManager } from './core/claude-code/session-manager';
import { extractTextContent, extractStreamingText, extractSessionId, extractCurrentToolUse, StreamMessage } from './core/claude-code/stream-parser';
import { SkillsInstaller } from './core/skills/skills-installer';
import { buildFormatContext } from './core/format/format-detector';
import { createRenderer } from './core/format/format-renderer';
import { getParagraphAtCursor, removeClaudeMentionFromText, hasClaudeMention } from './features/inline-assistant/paragraphExtractor';
import { claudeIndicatorField, setIndicatorState, findClaudeMentionInView } from './features/inline-assistant/claudeDetector';

export default class GenerousLedgerPlugin extends Plugin {
	settings: GenerousLedgerSettings;
	private sessionManager: SessionManager;
	private currentProcess: ClaudeCodeProcess | null = null;
	private claudeCodeReady: boolean = false;
	private processingRequest = false;

	async onload() {
		await this.loadSettings();

		this.sessionManager = new SessionManager(this.app);

		// Check Claude Code CLI availability, version, and auth
		await this.checkClaudeCodeSetup();

		// Install obsidian-skills if not present
		const skillsInstaller = new SkillsInstaller(this.app);
		await skillsInstaller.ensureSkillsInstalled();

		// Add settings tab
		this.addSettingTab(new GenerousLedgerSettingTab(this.app, this));

		// Register CodeMirror extensions for visual indicators and Enter key handling
		this.registerEditorExtension([
			claudeIndicatorField,
			Prec.highest(keymap.of([
				{
					key: 'Enter',
					run: (view: EditorView) => {
						return this.handleEnterKeyCodeMirror(view);
					}
				}
			]))
		]);

		// Update visual indicator as user types
		this.registerEvent(
			this.app.workspace.on('editor-change', (editor: Editor) => {
				this.updateVisualIndicator(editor);
			})
		);

		// Add clear session command
		this.addCommand({
			id: 'clear-claude-session',
			name: 'Clear Claude conversation for this note',
			editorCallback: async (editor: Editor, view: MarkdownView) => {
				const file = view.file;
				if (file) {
					await this.sessionManager.clearSession(file);
					new Notice('Claude conversation cleared for this note');
				}
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
		const status = await checkClaudeCodeVersion();

		if (!status.installed) {
			new Notice('Claude Code CLI not found.\n\nInstall with: npm i -g @anthropic-ai/claude-code', 10000);
			return;
		}

		if (!status.compatible) {
			new Notice(`Claude Code version ${status.version} may not be compatible.\n\nPlease update: npm update -g @anthropic-ai/claude-code`, 10000);
		}

		if (!status.authenticated) {
			new Notice('Claude Code not authenticated.\n\nRun "claude" in terminal to set up your API key.', 10000);
			return;
		}

		this.claudeCodeReady = true;
		console.log(`Claude Code ready: v${status.version}`);
	}

	private updateVisualIndicator(editor: Editor) {
		// Don't update indicators while processing a request
		if (this.processingRequest) {
			return;
		}

		const view = this.getEditorView(editor);
		if (!view) return;

		const mentionPos = findClaudeMentionInView(view);

		if (mentionPos !== null) {
			view.dispatch({
				effects: setIndicatorState.of({
					pos: mentionPos,
					state: 'ready'
				})
			});
		} else {
			view.dispatch({
				effects: setIndicatorState.of(null)
			});
		}
	}

	private handleEnterKeyCodeMirror(view: EditorView): boolean {
		if (this.processingRequest) {
			return false;
		}

		const cursor = view.state.selection.main.head;
		const paragraph = getParagraphAtCursor(view.state, cursor);

		if (!paragraph || !hasClaudeMention(paragraph.text)) {
			return false; // Let default Enter behavior proceed
		}

		// Find and store the mention position BEFORE any changes
		const mentionPos = findClaudeMentionInView(view);

		// Launch async handler (don't block the keymap)
		this.handleEnterAsync(view, paragraph, mentionPos);

		return true; // Prevent default Enter behavior
	}

	private async handleEnterAsync(view: EditorView, paragraph: any, mentionPos: number | null) {
		if (this.processingRequest) return;

		const activeView = this.app.workspace.getActiveViewOfType(MarkdownView);
		if (!activeView) return;

		const editor = activeView.editor;
		const file = activeView.file;
		if (!file) return;

		// Check if Claude Code is ready
		if (!this.claudeCodeReady) {
			new Notice('Claude Code not ready. Check plugin settings or install Claude Code CLI.');
			return;
		}

		// Extract the paragraph content without @Claude
		const content = removeClaudeMentionFromText(paragraph.text);

		if (!content.trim()) {
			new Notice('Please provide content for Claude to respond to');
			return;
		}

		// Set processing flag BEFORE updating indicator to prevent race condition
		this.processingRequest = true;

		// Update indicator to processing using the stored position (if found)
		if (mentionPos !== null) {
			view.dispatch({
				effects: setIndicatorState.of({
					pos: mentionPos,
					state: 'processing'
				})
			});
		}

		try {
			// Get session ID for conversation continuity
			const sessionResult = await this.sessionManager.getSessionId(file);
			const vaultPath = (this.app.vault.adapter as any).basePath;

			// Detect format and build context
			const formatContext = await buildFormatContext(this.app, file, editor.getCursor());

			// Create format-appropriate renderer
			const renderer = createRenderer(this.app, formatContext);
			const insertPos = await renderer.initResponse(editor);

			// Create and configure Claude Code process
			const process = new ClaudeCodeProcess();
			this.currentProcess = process;

			const messages: StreamMessage[] = [];
			let lastRenderedText = '';

			process.on('message', (msg: StreamMessage) => {
				messages.push(msg);

				// Render on stream_event deltas for character-by-character streaming
				if (msg.type === 'stream_event') {
					const newText = extractStreamingText(messages);
					if (newText !== lastRenderedText) {
						lastRenderedText = newText;
						// Defer to next tick to avoid editor layout errors
						setTimeout(() => {
							renderer.appendContent(newText, editor, insertPos || undefined);
						}, 0);
					}
				}

				// Update visual indicator with current tool (if any)
				const currentTool = extractCurrentToolUse(messages);
				if (currentTool) {
					this.updateIndicatorWithTool(view, mentionPos, currentTool);
				}
			});

			process.on('close', async () => {
				// Save session ID for conversation continuity
				const newSessionId = extractSessionId(messages);
				if (newSessionId) {
					await this.sessionManager.setSessionId(file, newSessionId);
				}

				// Finalize response with the final text (clears streaming and shows final answer)
				await renderer.finalizeResponse(lastRenderedText, editor, insertPos || undefined);

				// Clear the indicator
				view.dispatch({
					effects: setIndicatorState.of(null)
				});

				this.currentProcess = null;
				this.processingRequest = false;
			});

			process.on('error', (error: Error) => {
				console.error('Claude Code error:', error);

				// Update indicator to error state
				if (mentionPos !== null) {
					view.dispatch({
						effects: setIndicatorState.of({
							pos: mentionPos,
							state: 'error'
						})
					});
				}

				const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
				new Notice(`Claude error: ${errorMessage}`);

				// Render error in document
				this.renderClaudeError(editor, paragraph.to, errorMessage);

				this.currentProcess = null;
				this.processingRequest = false;
			});

			// Start the Claude Code query
			await process.query(content, {
				workingDirectory: vaultPath,
				sessionId: sessionResult.sessionId || undefined,
				systemPrompt: this.settings.systemPrompt,
				model: this.settings.model,
				timeoutMs: 15 * 60 * 1000,  // 15 minutes
			});

		} catch (error) {
			console.error('Claude request error:', error);

			// Update indicator to error state
			if (mentionPos !== null) {
				view.dispatch({
					effects: setIndicatorState.of({
						pos: mentionPos,
						state: 'error'
					})
				});
			}

			const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
			new Notice(`Claude error: ${errorMessage}`);

			// Render error in document
			this.renderClaudeError(editor, paragraph.to, errorMessage);

			this.processingRequest = false;
		}
	}

	private updateIndicatorWithTool(view: EditorView, mentionPos: number | null, toolName: string): void {
		if (mentionPos !== null) {
			view.dispatch({
				effects: setIndicatorState.of({
					pos: mentionPos,
					state: 'processing',
					toolName
				})
			});
		}
	}

	private renderClaudeError(editor: Editor, paragraphEnd: number, errorMessage: string): void {
		const cursor = editor.getCursor();
		const insertLine = cursor.line + 1;

		editor.replaceRange(
			`\n\n> [!error] Claude Error\n> ${errorMessage}\n`,
			{ line: cursor.line, ch: editor.getLine(cursor.line).length }
		);
	}

	private getEditorView(editor: Editor): EditorView | null {
		// Access the CodeMirror 6 EditorView from Obsidian's Editor
		// @ts-ignore - Obsidian's internal API
		return editor.cm as EditorView;
	}
}
