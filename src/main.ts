import { Editor, MarkdownView, Notice, Plugin } from 'obsidian';
import { EditorView, keymap } from '@codemirror/view';
import { Prec } from '@codemirror/state';
import { GenerousLedgerSettings, GenerousLedgerSettingTab, DEFAULT_SETTINGS } from './settings';
import { ClaudeClient } from './core/api/claudeClient';
import { getParagraphAtCursor, removeClaudeMentionFromText, hasClaudeMention } from './features/inline-assistant/paragraphExtractor';
import { initClaudeResponse, appendClaudeResponse, finalizeClaudeResponse, renderClaudeError } from './features/inline-assistant/responseRenderer';
import { claudeIndicatorField, setIndicatorState, findClaudeMentionInView } from './features/inline-assistant/claudeDetector';

export default class GenerousLedgerPlugin extends Plugin {
	settings: GenerousLedgerSettings;
	claudeClient: ClaudeClient | null = null;
	private processingRequest = false;

	async onload() {
		await this.loadSettings();

		// Initialize Claude client if API key is available
		if (this.settings.apiKey) {
			this.initializeClaudeClient();
		}

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

		console.log('Generous Ledger plugin loaded');
	}

	onunload() {
		console.log('Generous Ledger plugin unloaded');
	}

	async loadSettings() {
		this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
	}

	async saveSettings() {
		await this.saveData(this.settings);
		if (this.settings.apiKey) {
			this.initializeClaudeClient();
		}
	}

	private initializeClaudeClient() {
		this.claudeClient = new ClaudeClient({
			apiKey: this.settings.apiKey,
			model: this.settings.model,
			maxTokens: this.settings.maxTokens,
			systemPrompt: this.settings.systemPrompt
		});
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

		// Check if API key is configured
		if (!this.settings.apiKey) {
			new Notice('Please set your Anthropic API key in Generous Ledger settings');
			return;
		}

		if (!this.claudeClient) {
			this.initializeClaudeClient();
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
			// Initialize response area with opening span
			let cursor = initClaudeResponse({ editor, paragraphEnd: paragraph.to });

			// Stream response chunks with typing effect
			for await (const chunk of this.claudeClient!.streamMessage(content)) {
				// Verify we're still in the same view
				const currentView = this.app.workspace.getActiveViewOfType(MarkdownView);
				if (!currentView || currentView !== activeView) {
					new Notice('Document changed during request. Response may be incomplete.');
					break;
				}

				// Append chunk to document
				cursor = appendClaudeResponse({ editor, cursor, text: chunk });
			}

			// Finalize response with closing span
			finalizeClaudeResponse({ editor, cursor });

			// Clear the indicator
			view.dispatch({
				effects: setIndicatorState.of(null)
			});

		} catch (error) {
			console.error('Claude API error:', error);

			// Update indicator to error state using stored position (if found)
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
			renderClaudeError({
				editor,
				paragraphEnd: paragraph.to,
				error: errorMessage,
				response: ''
			});
		} finally {
			this.processingRequest = false;
		}
	}

	private getEditorView(editor: Editor): EditorView | null {
		// Access the CodeMirror 6 EditorView from Obsidian's Editor
		// @ts-ignore - Obsidian's internal API
		return editor.cm as EditorView;
	}
}
