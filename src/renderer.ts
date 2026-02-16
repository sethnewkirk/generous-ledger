import { Editor } from 'obsidian';

export interface InsertPosition {
	line: number;
	ch: number;
}

export class ResponseRenderer {
	private insertPos: InsertPosition | null = null;
	private scrollDOM: HTMLElement | null = null;

	init(editor: Editor, scrollDOM?: HTMLElement | null): InsertPosition | null {
		const cursor = editor.getCursor();
		const insertLine = cursor.line + 1;

		this.scrollDOM = scrollDOM ?? null;

		editor.replaceRange(
			'\n\n> [!claude] Claude\n> ',
			{ line: cursor.line, ch: editor.getLine(cursor.line).length }
		);

		this.insertPos = { line: insertLine + 2, ch: 2 };
		return this.insertPos;
	}

	private isNearBottom(): boolean {
		if (!this.scrollDOM) return true;
		const { scrollTop, scrollHeight, clientHeight } = this.scrollDOM;
		return scrollHeight - scrollTop - clientHeight < 150;
	}

	append(text: string, editor: Editor): void {
		if (!this.insertPos) return;

		const formatted = text
			.split('\n')
			.map(line => line.trim() ? `> ${line}` : '>')
			.join('\n');

		const wasNearBottom = this.isNearBottom();
		const savedScrollTop = this.scrollDOM?.scrollTop;

		const currentLine = editor.lastLine();
		editor.replaceRange(
			formatted,
			this.insertPos,
			{ line: currentLine, ch: editor.getLine(currentLine).length }
		);

		if (wasNearBottom) {
			editor.scrollIntoView({
				from: { line: editor.lastLine(), ch: 0 },
				to: { line: editor.lastLine(), ch: 0 }
			});
		} else if (this.scrollDOM && savedScrollTop !== undefined) {
			this.scrollDOM.scrollTop = savedScrollTop;
		}
	}

	finalize(text: string, editor: Editor, thinking?: string): void {
		if (!this.insertPos) return;

		let formatted: string;

		if (thinking && thinking.trim()) {
			const thinkingLines = thinking.split('\n').map(line => line.trim() ? `> *${line}*` : '>');
			const answerLines = text.split('\n').map(line => line.trim() ? `> ${line}` : '>');

			const parts = [
				...thinkingLines,
				'>',
				'> ---',
				'>',
				...answerLines,
			];

			formatted = parts.join('\n');
		} else {
			formatted = text
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

		editor.scrollIntoView({
			from: { line: editor.lastLine(), ch: 0 },
			to: { line: editor.lastLine(), ch: 0 }
		});
	}
}
