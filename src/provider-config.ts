import { DEFAULT_ASSISTANT_HANDLE, normalizeAssistantHandle } from './assistant-handle';
import { AssistantProvider, isAssistantProvider } from './provider-types';

export function normalizeConfiguredProvider(value: unknown): AssistantProvider | null {
	return isAssistantProvider(value) ? value : null;
}

export function getProviderBinaryPath(
	provider: AssistantProvider,
	paths: { claudePath: string; codexPath: string; }
): string {
	if (provider === 'claude') {
		return paths.claudePath?.trim() || 'claude';
	}
	return paths.codexPath?.trim() || 'codex';
}

export function getProviderModel(
	provider: AssistantProvider,
	models: { claudeModel?: string; codexModel?: string; }
): string | undefined {
	const raw = provider === 'claude' ? models.claudeModel : models.codexModel;
	const trimmed = raw?.trim();
	return trimmed ? trimmed : undefined;
}

export function getMissingProviderNotice(): string {
	return 'Choose Codex or Claude in Generous Ledger settings to activate Steward.';
}

export function getConfiguredHandle(handle?: string): string {
	return normalizeAssistantHandle(handle || DEFAULT_ASSISTANT_HANDLE);
}
