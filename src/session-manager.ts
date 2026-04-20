import { App, TFile, Notice } from 'obsidian';
import { AssistantProvider } from './provider-types';
import { clearStoredSessionId, getStoredSessionId, SessionLookupResult, setStoredSessionId } from './session-state';

export class SessionManager {
	constructor(private app: App) {}

	async getSessionId(file: TFile, provider: AssistantProvider): Promise<SessionLookupResult> {
		const cache = this.app.metadataCache.getFileCache(file);
		const result = getStoredSessionId(cache?.frontmatter as Record<string, unknown> | undefined, provider);

		if (result.wasInvalid) {
			new Notice(`Invalid ${provider === 'claude' ? 'Claude' : 'Codex'} session data in frontmatter. Starting a new conversation.`);
			await this.clearSession(file, provider);
		}

		return result;
	}

	async setSessionId(file: TFile, provider: AssistantProvider, sessionId: string): Promise<void> {
		await this.app.fileManager.processFrontMatter(file, (frontmatter) => {
			setStoredSessionId(frontmatter as Record<string, unknown>, provider, sessionId);
		});
	}

	async clearSession(file: TFile, provider?: AssistantProvider): Promise<void> {
		await this.app.fileManager.processFrontMatter(file, (frontmatter) => {
			clearStoredSessionId(frontmatter as Record<string, unknown>, provider);
		});
	}
}
