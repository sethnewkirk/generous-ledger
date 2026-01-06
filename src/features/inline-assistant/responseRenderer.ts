import { Editor } from 'obsidian';

export interface RenderOptions {
	editor: Editor;
	paragraphEnd: number;
	response: string;
}

export function renderClaudeResponse(options: RenderOptions): void {
	const { editor, paragraphEnd, response } = options;

	// Find the line where the paragraph ends
	const endPos = editor.offsetToPos(paragraphEnd);

	// Move to the end of the paragraph
	const cursor = {
		line: endPos.line,
		ch: editor.getLine(endPos.line).length
	};

	// Insert two newlines and then the callout
	// Handle empty lines in response properly
	const formattedResponse = response
		.split('\n')
		.map(line => line.trim() ? `> ${line}` : '>')
		.join('\n');

	const callout = `\n\n> [!claude] Claude's Response\n${formattedResponse}`;

	editor.replaceRange(callout, cursor);
}

export function renderClaudeError(options: RenderOptions & { error: string }): void {
	const { editor, paragraphEnd, error } = options;

	const endPos = editor.offsetToPos(paragraphEnd);
	const cursor = {
		line: endPos.line,
		ch: editor.getLine(endPos.line).length
	};

	const errorCallout = `\n\n> [!error] Claude Error\n> ${error}`;

	editor.replaceRange(errorCallout, cursor);
}
