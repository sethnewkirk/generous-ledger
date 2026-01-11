import { App, TFile, Editor } from 'obsidian';
import { FormatContext } from './format-detector';

export interface ResponseRenderer {
	initResponse(editor?: Editor): Promise<{ line: number; ch: number } | null>;
	appendContent(content: string, editor?: Editor, insertPos?: { line: number; ch: number }): Promise<void>;
	finalizeResponse(finalContent: string, editor?: Editor, insertPos?: { line: number; ch: number }): Promise<void>;
}

export function createRenderer(app: App, context: FormatContext): ResponseRenderer {
	switch (context.format) {
		case 'canvas':
			return new CanvasRenderer(app, context);
		case 'base':
			return new BaseRenderer(app, context);
		default:
			return new MarkdownRenderer(app, context);
	}
}

// Helper to separate thinking from answer
function separateThinkingFromAnswer(content: string): { thinking: string | null; answer: string } {
	// Split by double newlines to get paragraphs
	const paragraphs = content.split(/\n\n+/).filter(p => p.trim());

	// If only one paragraph or very short, no thinking to collapse
	if (paragraphs.length <= 1) {
		return { thinking: null, answer: content };
	}

	// If two paragraphs but both short, treat as single answer
	if (paragraphs.length === 2 && content.length < 100) {
		return { thinking: null, answer: content };
	}

	// Multiple paragraphs: last is answer, rest is thinking
	const answer = paragraphs[paragraphs.length - 1];
	const thinking = paragraphs.slice(0, -1).join('\n\n');

	return { thinking, answer };
}

class MarkdownRenderer implements ResponseRenderer {
	constructor(private app: App, private context: FormatContext) {}

	async initResponse(editor?: Editor): Promise<{ line: number; ch: number } | null> {
		if (!editor) return null;

		const cursor = editor.getCursor();
		const insertLine = cursor.line + 1;

		editor.replaceRange(
			'\n\n> [!claude] Claude\n> ',
			{ line: cursor.line, ch: editor.getLine(cursor.line).length }
		);

		return { line: insertLine + 2, ch: 2 };
	}

	async appendContent(content: string, editor?: Editor, insertPos?: { line: number; ch: number }): Promise<void> {
		if (!editor || !insertPos) return;

		const formatted = content
			.split('\n')
			.map(line => line.trim() ? `> ${line}` : '>')
			.join('\n');

		const currentLine = editor.lastLine();
		editor.replaceRange(
			formatted,
			insertPos,
			{ line: currentLine, ch: editor.getLine(currentLine).length }
		);
	}

	async finalizeResponse(finalContent: string, editor?: Editor, insertPos?: { line: number; ch: number }): Promise<void> {
		if (!editor || !insertPos) return;

		// Separate thinking from answer
		const { thinking, answer } = separateThinkingFromAnswer(finalContent);

		let formatted: string;

		if (thinking) {
			// Use nested collapsible callout for thinking
			const thinkingLines = thinking.split('\n').map(line => `> > ${line}`);
			const answerLines = answer.split('\n').map(line => line.trim() ? `> ${line}` : '>');

			const parts = [
				'> > [!note]- Thinking',
				...thinkingLines,
				'>',
				...answerLines
			];

			formatted = parts.join('\n');
		} else {
			// No thinking to collapse, just format the answer
			formatted = finalContent
				.split('\n')
				.map(line => line.trim() ? `> ${line}` : '>')
				.join('\n');
		}

		// Replace all content from insertPos to end with final content
		const currentLine = editor.lastLine();
		editor.replaceRange(
			formatted + '\n',
			insertPos,
			{ line: currentLine, ch: editor.getLine(currentLine).length }
		);
	}
}

class CanvasRenderer implements ResponseRenderer {
	private responseNodeId: string | null = null;

	constructor(private app: App, private context: FormatContext) {}

	async initResponse(): Promise<{ line: number; ch: number } | null> {
		try {
			const canvas = JSON.parse(this.context.content);
			const promptNode = canvas.nodes.find((n: any) => n.id === this.context.nodeId);

			if (!promptNode) return null;

			this.responseNodeId = generateCanvasId();
			const responseNode = {
				id: this.responseNodeId,
				type: 'text',
				text: '',
				x: promptNode.x + promptNode.width + 50,
				y: promptNode.y,
				width: 400,
				height: 200,
			};

			const edge = {
				id: generateCanvasId(),
				fromNode: this.context.nodeId,
				toNode: this.responseNodeId,
				fromSide: 'right',
				toSide: 'left',
			};

			canvas.nodes.push(responseNode);
			canvas.edges.push(edge);

			await this.app.vault.modify(this.context.file, JSON.stringify(canvas, null, 2));
			return null;
		} catch (e) {
			console.error('Error initializing canvas response:', e);
			return null;
		}
	}

	async appendContent(content: string): Promise<void> {
		try {
			const canvasContent = await this.app.vault.read(this.context.file);
			const canvas = JSON.parse(canvasContent);

			const responseNode = canvas.nodes.find((n: any) => n.id === this.responseNodeId);
			if (responseNode) {
				responseNode.text = content;
				await this.app.vault.modify(this.context.file, JSON.stringify(canvas, null, 2));
			}
		} catch (e) {
			console.error('Error appending to canvas:', e);
		}
	}

	async finalizeResponse(finalContent: string): Promise<void> {
		// Replace node content with final text
		if (!this.responseNodeId) return;

		try {
			const canvasContent = await this.app.vault.read(this.context.file);
			const canvas = JSON.parse(canvasContent);

			const responseNode = canvas.nodes.find((n: any) => n.id === this.responseNodeId);
			if (responseNode) {
				responseNode.text = finalContent;
				await this.app.vault.modify(this.context.file, JSON.stringify(canvas, null, 2));
			}
		} catch (e) {
			console.error('Error finalizing canvas response:', e);
		}
	}
}

class BaseRenderer implements ResponseRenderer {
	constructor(private app: App, private context: FormatContext) {}

	async initResponse(): Promise<{ line: number; ch: number } | null> {
		// For .base files, we might create a companion .md note
		// or prepare to modify the YAML config
		return null;
	}

	async appendContent(content: string): Promise<void> {
		// Could update YAML config or write to companion note
		// For now, create a companion markdown note
		try {
			const baseName = this.context.file.basename;
			const companionPath = this.context.file.parent?.path
				? `${this.context.file.parent.path}/${baseName}-response.md`
				: `${baseName}-response.md`;

			await this.app.vault.create(companionPath, content);
		} catch (e) {
			// File might already exist, that's okay
		}
	}

	async finalizeResponse(finalContent: string): Promise<void> {
		// Write final content to companion note
		try {
			const baseName = this.context.file.basename;
			const companionPath = this.context.file.parent?.path
				? `${this.context.file.parent.path}/${baseName}-response.md`
				: `${baseName}-response.md`;

			// Check if file exists, if so modify it, otherwise create it
			const existingFile = this.app.vault.getAbstractFileByPath(companionPath);
			if (existingFile) {
				await this.app.vault.modify(existingFile as TFile, finalContent);
			} else {
				await this.app.vault.create(companionPath, finalContent);
			}
		} catch (e) {
			console.error('Error finalizing base response:', e);
		}
	}
}

function generateCanvasId(): string {
	return [...Array(16)].map(() => Math.floor(Math.random() * 16).toString(16)).join('');
}
