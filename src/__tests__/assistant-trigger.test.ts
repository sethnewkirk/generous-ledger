import { buildAssistantMentionPattern, findAssistantMention, getAssistantMentionAliases } from '../assistant-handle';
import { hasAssistantMention, removeAssistantMentionFromText } from '../trigger';

describe('assistant mention handling', () => {
	test('uses Steward as the default handle', () => {
		expect(getAssistantMentionAliases()).toEqual(['Steward', 'Claude', 'Codex']);
		expect(buildAssistantMentionPattern().test('Need a response @Steward')).toBe(true);
	});

	test('supports a configurable handle plus legacy aliases', () => {
		expect(hasAssistantMention('Ping @Navigator', 'Navigator')).toBe(true);
		expect(hasAssistantMention('Legacy @Claude still works', 'Navigator')).toBe(true);
		expect(hasAssistantMention('Legacy @Codex still works', 'Navigator')).toBe(true);
	});

	test('finds mention position and matched text', () => {
		expect(findAssistantMention('Status update for @Steward')).toEqual({
			index: 18,
			matchText: '@Steward',
		});
	});

	test('removes the configured or legacy trigger from text', () => {
		expect(removeAssistantMentionFromText('What matters most today? @Steward', 'Steward')).toBe('What matters most today?');
		expect(removeAssistantMentionFromText('Please review this @Codex', 'Steward')).toBe('Please review this');
	});

	test('removes frontmatter before stripping the mention', () => {
		const text = ['---', 'title: Example', '---', '', 'Review this paragraph @Steward'].join('\n');
		expect(removeAssistantMentionFromText(text, 'Steward')).toBe('Review this paragraph');
	});
});
