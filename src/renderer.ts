import { Editor } from 'obsidian';

function separateThinkingFromAnswer(content: string): { thinking: string | null; answer: string } {
	const paragraphs = content.split(/\n\n+/).filter(p => p.trim());

	if (paragraphs.length <= 1) {
		return { thinking: null, answer: content };
	}

	if (paragraphs.length === 2 && content.length < 100) {
		return { thinking: null, answer: content };
	}

	const answer = paragraphs[paragraphs.length - 1];
	const thinking = paragraphs.slice(0, -1).join('\n\n');

	return { thinking, answer };
}

export interface InsertPosition {
	line: number;
	ch: number;
}

export class ResponseRenderer {
	private insertPos: InsertPosition | null = null;

	init(editor: Editor): InsertPosition | null {
		const cursor = editor.getCursor();
		const insertLine = cursor.line + 1;

		editor.replaceRange(
			'\n\n> [!claude] Claude\n> ',
			{ line: cursor.line, ch: editor.getLine(cursor.line).length }
		);

		this.insertPos = { line: insertLine + 2, ch: 2 };
		return this.insertPos;
	}

	append(text: string, editor: Editor): void {
		if (!this.insertPos) return;

		const formatted = text
			.split('\n')
			.map(line => line.trim() ? `> ${line}` : '>')
			.join('\n');

		const currentLine = editor.lastLine();
		editor.replaceRange(
			formatted,
			this.insertPos,
			{ line: currentLine, ch: editor.getLine(currentLine).length }
		);
	}

	finalize(finalContent: string, editor: Editor): void {
		if (!this.insertPos) return;

		const { thinking, answer } = separateThinkingFromAnswer(finalContent);

		let formatted: string;

		if (thinking) {
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
			formatted = finalContent
				.split('\n')
				.map(line => line.trim() ? `> ${line}` : '>')
				.join('\n');
		}

		const currentLine = editor.lastLine();
		editor.replaceRange(
			formatted + '\n',
			this.insertPos,
			{ line: currentLine, ch: editor.getLine(currentLine).length }
		);
	}
}
