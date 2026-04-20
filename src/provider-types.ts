export type AssistantProvider = 'claude' | 'codex';

export const SUPPORTED_PROVIDERS: AssistantProvider[] = ['claude', 'codex'];

export function isAssistantProvider(value: unknown): value is AssistantProvider {
	return value === 'claude' || value === 'codex';
}

export function getProviderDisplayName(provider: AssistantProvider): string {
	return provider === 'claude' ? 'Claude' : 'Codex';
}

export function getRuntimeEntrypointName(provider: AssistantProvider): string {
	return provider === 'claude' ? 'CLAUDE.md' : 'AGENTS.md';
}
