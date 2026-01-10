import { Editor, EditorPosition } from 'obsidian';

export interface RenderOptions {
	editor: Editor;
	paragraphEnd: number;
	response: string;
}

export interface StreamInitOptions {
	editor: Editor;
	paragraphEnd: number;
}

export interface StreamAppendOptions {
	editor: Editor;
	cursor: EditorPosition;
	text: string;
}

export interface StreamFinalizeOptions {
	editor: Editor;
	cursor: EditorPosition;
}

// Legacy non-streaming render (kept for compatibility)
export function renderClaudeResponse(options: RenderOptions): void {
	const { editor, paragraphEnd, response } = options;

	const endPos = editor.offsetToPos(paragraphEnd);
	const cursor = {
		line: endPos.line,
		ch: editor.getLine(endPos.line).length
	};

	// Format with separator and blockquote
	const formattedResponse = response
		.split('\n')
		.map(line => `> ${line}`)
		.join('\n');

	editor.replaceRange(`\n\n---\n${formattedResponse}`, cursor);
}

// Initialize streaming response - inserts separator and blockquote start
export function initClaudeResponse(options: StreamInitOptions): EditorPosition {
	const { editor, paragraphEnd } = options;

	const endPos = editor.offsetToPos(paragraphEnd);
	const cursor = {
		line: endPos.line,
		ch: editor.getLine(endPos.line).length
	};

	// Insert: \n\n---\n>
	const openingText = '\n\n---\n> ';
	editor.replaceRange(openingText, cursor);

	// Return new cursor position after the opening
	return {
		line: cursor.line + 3, // After two newlines and separator line
		ch: 2 // After "> "
	};
}

// Append text chunk during streaming
export function appendClaudeResponse(options: StreamAppendOptions): EditorPosition {
	const { editor, cursor, text } = options;

	// Handle newlines by prefixing continuation lines with "> "
	const formattedText = text.replace(/\n/g, '\n> ');
	editor.replaceRange(formattedText, cursor);

	// Calculate new cursor position
	const lines = formattedText.split('\n');
	if (lines.length === 1) {
		// Single line - just advance ch
		return {
			line: cursor.line,
			ch: cursor.ch + formattedText.length
		};
	} else {
		// Multiple lines - move to end of last line
		return {
			line: cursor.line + lines.length - 1,
			ch: lines[lines.length - 1].length
		};
	}
}

// Finalize streaming response - nothing needed for blockquote
export function finalizeClaudeResponse(options: StreamFinalizeOptions): void {
	// No closing tag needed for blockquote format
}

export function renderClaudeError(options: RenderOptions & { error: string }): void {
	const { editor, paragraphEnd, error } = options;

	const endPos = editor.offsetToPos(paragraphEnd);
	const cursor = {
		line: endPos.line,
		ch: editor.getLine(endPos.line).length
	};

	// Use same format with Error prefix in bold
	const errorText = `\n\n---\n> **Error:** ${error}`;
	editor.replaceRange(errorText, cursor);
}
