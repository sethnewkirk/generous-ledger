import { EditorState, StateField, StateEffect } from '@codemirror/state';
import { Decoration, DecorationSet, EditorView } from '@codemirror/view';
import { ClaudeIndicatorWidget, IndicatorState } from './visual-indicator';

export const setIndicatorState = StateEffect.define<{
	pos: number;
	state: IndicatorState;
	toolName?: string;
} | null>();

export const claudeIndicatorField = StateField.define<DecorationSet>({
	create() {
		return Decoration.none;
	},
	update(decorations, tr) {
		decorations = decorations.map(tr.changes);

		for (const effect of tr.effects) {
			if (effect.is(setIndicatorState)) {
				if (effect.value === null) {
					decorations = Decoration.none;
				} else {
					const widget = Decoration.widget({
						widget: new ClaudeIndicatorWidget(effect.value.state, effect.value.toolName),
						side: 1
					});
					decorations = Decoration.set([widget.range(effect.value.pos)]);
				}
			}
		}

		return decorations;
	},
	provide: f => EditorView.decorations.from(f)
});

export function findClaudeMentionInView(view: EditorView): number | null {
	const doc = view.state.doc;
	const cursor = view.state.selection.main.head;
	const line = doc.lineAt(cursor);

	const match = line.text.match(/@claude\b/i);
	if (match && match.index !== undefined) {
		return line.from + match.index + match[0].length;
	}

	return null;
}

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

	let currentLineNum = line.number;
	while (currentLineNum > 1) {
		const prevLine = doc.line(currentLineNum - 1);
		if (prevLine.text.trim() === '') {
			break;
		}
		from = prevLine.from;
		currentLineNum--;
	}

	currentLineNum = line.number;
	while (currentLineNum < doc.lines) {
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
	let cleanText = text;
	if (cleanText.startsWith('---')) {
		const endOfFrontmatter = cleanText.indexOf('---', 3);
		if (endOfFrontmatter !== -1) {
			cleanText = cleanText.substring(endOfFrontmatter + 3).trim();
		}
	}

	return cleanText.replace(/@claude\b/gi, '').trim();
}

export function hasClaudeMention(text: string): boolean {
	return /@claude\b/i.test(text);
}
