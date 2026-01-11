import { EditorState } from '@codemirror/state';

export interface ParagraphBounds {
	from: number;
	to: number;
	text: string;
}

export function getParagraphAtCursor(state: EditorState, pos: number): ParagraphBounds | null {
	const doc = state.doc;
	const line = doc.lineAt(pos);

	let from = line.from;
	let to = line.to;

	// Scan backward to find paragraph start (empty line or start of document)
	let currentLineNum = line.number;
	while (currentLineNum > 1) {
		const prevLine = doc.line(currentLineNum - 1);
		if (prevLine.text.trim() === '') {
			break;
		}
		from = prevLine.from;
		currentLineNum--;
	}

	// Scan forward to find paragraph end (empty line or end of document)
	currentLineNum = line.number;
	while (currentLineNum < doc.lines) {
		// Check if there's a next line before accessing it
		if (currentLineNum + 1 > doc.lines) {
			break;
		}
		const nextLine = doc.line(currentLineNum + 1);
		if (nextLine.text.trim() === '') {
			break;
		}
		to = nextLine.to;
		currentLineNum++;
	}

	const text = doc.sliceString(from, to);

	return { from, to, text };
}

export function removeClaudeMentionFromText(text: string): string {
	// Remove YAML frontmatter if present (starts and ends with ---)
	let cleanText = text;
	if (cleanText.startsWith('---')) {
		const endOfFrontmatter = cleanText.indexOf('---', 3);
		if (endOfFrontmatter !== -1) {
			cleanText = cleanText.substring(endOfFrontmatter + 3).trim();
		}
	}

	// Remove @Claude or @claude (case-insensitive) from the text
	return cleanText.replace(/@claude\b/gi, '').trim();
}

export function hasClaudeMention(text: string): boolean {
	return /@claude\b/i.test(text);
}
