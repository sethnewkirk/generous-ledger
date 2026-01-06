import { Editor, MarkdownView, Notice, Plugin } from 'obsidian';
import { EditorView } from '@codemirror/view';
import { GenerousLedgerSettings, GenerousLedgerSettingTab, DEFAULT_SETTINGS } from './settings';
import { ClaudeClient } from './core/api/claudeClient';
import { getParagraphAtCursor, removeClaudeMentionFromText, hasClaudeMention } from './features/inline-assistant/paragraphExtractor';
import { renderClaudeResponse, renderClaudeError } from './features/inline-assistant/responseRenderer';
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

		// Register CodeMirror extension for visual indicators
		this.registerEditorExtension([claudeIndicatorField]);

		// Register Enter key handler
		this.registerDomEvent(document, 'keydown', (evt: KeyboardEvent) => {
			if (evt.key === 'Enter' && !evt.shiftKey) {
				this.handleEnterKey(evt);
			}
		});

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

	private async handleEnterKey(evt: KeyboardEvent) {
		if (this.processingRequest) return;

		const activeView = this.app.workspace.getActiveViewOfType(MarkdownView);
		if (!activeView) return;

		const editor = activeView.editor;
		const view = this.getEditorView(editor);
		if (!view) return;

		const cursor = editor.getCursor();
		const cursorOffset = editor.posToOffset(cursor);
		const paragraph = getParagraphAtCursor(view.state, cursorOffset);

		if (!paragraph || !hasClaudeMention(paragraph.text)) {
			return;
		}

		// Prevent default Enter behavior
		evt.preventDefault();
		evt.stopPropagation();

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

		// Update indicator to processing
		let mentionPos = findClaudeMentionInView(view);
		if (mentionPos !== null) {
			view.dispatch({
				effects: setIndicatorState.of({
					pos: mentionPos,
					state: 'processing'
				})
			});
		}

		this.processingRequest = true;

		try {
			// Send to Claude API
			const response = await this.claudeClient!.sendMessage(content);

			// Verify we're still in the same view
			const currentView = this.app.workspace.getActiveViewOfType(MarkdownView);
			if (!currentView || currentView !== activeView) {
				new Notice('Document changed during request. Response not inserted.');
				return;
			}

			// Clear the indicator
			view.dispatch({
				effects: setIndicatorState.of(null)
			});

			// Render the response
			renderClaudeResponse({
				editor,
				paragraphEnd: paragraph.to,
				response
			});

		} catch (error) {
			console.error('Claude API error:', error);

			// Recalculate mention position in case document changed
			mentionPos = findClaudeMentionInView(view);
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
