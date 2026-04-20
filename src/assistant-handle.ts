export const DEFAULT_ASSISTANT_HANDLE = 'Steward';
export const DEFAULT_LEGACY_MENTION_ALIASES = ['Claude', 'Codex'];

export interface MentionMatch {
	index: number;
	matchText: string;
}

export function normalizeAssistantHandle(handle?: string): string {
	return handle?.trim() || DEFAULT_ASSISTANT_HANDLE;
}

export function getAssistantMentionAliases(handle?: string): string[] {
	const normalized = normalizeAssistantHandle(handle);
	const aliases = [normalized, ...DEFAULT_LEGACY_MENTION_ALIASES];
	const seen = new Set<string>();

	return aliases.filter((alias) => {
		const key = alias.trim().toLowerCase();
		if (!key || seen.has(key)) {
			return false;
		}
		seen.add(key);
		return true;
	});
}

export function escapeRegex(value: string): string {
	return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function buildAssistantMentionPattern(handle?: string): RegExp {
	const aliases = getAssistantMentionAliases(handle)
		.map(escapeRegex)
		.join('|');
	return new RegExp(`@(?:${aliases})\\b`, 'i');
}

export function findAssistantMention(text: string, handle?: string): MentionMatch | null {
	const match = text.match(buildAssistantMentionPattern(handle));
	if (!match || match.index === undefined) {
		return null;
	}

	return {
		index: match.index,
		matchText: match[0],
	};
}
