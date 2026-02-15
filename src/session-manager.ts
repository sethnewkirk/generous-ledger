import { App, TFile, Notice } from 'obsidian';

export interface SessionResult {
	sessionId: string | null;
	wasInvalid: boolean;
}

export class SessionManager {
	constructor(private app: App) {}

	async getSessionId(file: TFile): Promise<SessionResult> {
		const cache = this.app.metadataCache.getFileCache(file);
		const storedId = cache?.frontmatter?.claude_session_id;

		if (!storedId) {
			return { sessionId: null, wasInvalid: false };
		}

		if (typeof storedId !== 'string' || storedId.length < 10) {
			new Notice('Invalid Claude session ID in frontmatter. Starting new conversation.');
			await this.clearSession(file);
			return { sessionId: null, wasInvalid: true };
		}

		return { sessionId: storedId, wasInvalid: false };
	}

	async setSessionId(file: TFile, sessionId: string): Promise<void> {
		await this.app.fileManager.processFrontMatter(file, (frontmatter) => {
			frontmatter.claude_session_id = sessionId;
		});
	}

	async clearSession(file: TFile): Promise<void> {
		await this.app.fileManager.processFrontMatter(file, (frontmatter) => {
			delete frontmatter.claude_session_id;
		});
	}
}
