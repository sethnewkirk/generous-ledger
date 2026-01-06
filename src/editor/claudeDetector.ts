import {
	ViewPlugin,
	ViewUpdate,
	Decoration,
	DecorationSet,
	EditorView
} from '@codemirror/view';
import { StateField, StateEffect } from '@codemirror/state';
import { ClaudeIndicatorWidget, IndicatorState } from './visualIndicator';

// State effect to update indicator state
export const setIndicatorState = StateEffect.define<{
	pos: number;
	state: IndicatorState;
} | null>();

// State field to track Claude mention decorations
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
						widget: new ClaudeIndicatorWidget(effect.value.state),
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

	// Check current line for @claude (case-insensitive)
	const match = line.text.match(/@claude\b/i);
	if (match && match.index !== undefined) {
		return line.from + match.index + match[0].length;
	}

	return null;
}
