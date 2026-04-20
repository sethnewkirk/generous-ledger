import { buildLinkedNoteContent, buildLinkedNotePath, createNoteIntent, insertCalloutIntoNoteText, replaceSelectionInNoteText, selectionStillMatches } from '../note-context';

describe('note context helpers', () => {
	test('inserts a steward callout without mutating the note until write-back time', () => {
		const original = '## Daily Note\n\nThink this through @Steward';
		const intent = createNoteIntent(
			{ path: 'Notes/Daily.md' } as any,
			'Think this through @Steward',
			'Think this through',
			{
				from: { line: 2, ch: 0 },
				to: { line: 2, ch: 25 },
			},
			'mention'
		);

		const nextText = insertCalloutIntoNoteText(original, intent, 'Here is the answer.', 'Steward');
		expect(nextText).toContain('Think this through');
		expect(nextText).toContain('> [!steward] Steward');
		expect(nextText).toContain('> Here is the answer.');
	});

	test('replaces the original selection when requested', () => {
		const original = 'alpha beta gamma';
		const intent = createNoteIntent(
			{ path: 'Notes/Alpha.md' } as any,
			'beta',
			'beta',
			{
				from: { line: 0, ch: 6 },
				to: { line: 0, ch: 10 },
			},
			'command'
		);

		expect(replaceSelectionInNoteText(original, intent, 'delta')).toBe('alpha delta gamma');
	});

	test('guards write-back when the source selection drifted', () => {
		const intent = createNoteIntent(
			{ path: 'Notes/Alpha.md' } as any,
			'beta',
			'beta',
			{
				from: { line: 0, ch: 6 },
				to: { line: 0, ch: 10 },
			},
			'command'
		);

		expect(selectionStillMatches('alpha beta gamma', intent)).toBe(true);
		expect(selectionStillMatches('alpha theta gamma', intent)).toBe(false);
	});

	test('creates linked-note content with a backlink to the source', () => {
		const path = buildLinkedNotePath('Notes/Daily.md');
		expect(path).toContain('Daily - Steward Reply');
		expect(buildLinkedNoteContent('Notes/Daily.md', 'Carry this forward.')).toContain('Source: [[Daily]]');
	});
});
