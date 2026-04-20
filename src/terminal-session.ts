import type GenerousLedgerPlugin from './main';
import { AssistantProvider } from './provider-types';
import { normalizeConfiguredProvider } from './provider-config';

export interface ConversationEntry {
	role: 'steward' | 'user' | 'system';
	text: string;
}

export interface TerminalSessionData {
	sessionId: string | null;
	provider: AssistantProvider | null;
	log: ConversationEntry[];
	startedAt: string | null;
}

const DEFAULT_SESSION: TerminalSessionData = {
	sessionId: null,
	provider: null,
	log: [],
	startedAt: null,
};

export class TerminalSessionStore {
	private plugin: GenerousLedgerPlugin;
	private cache: TerminalSessionData | null = null;

	constructor(plugin: GenerousLedgerPlugin) {
		this.plugin = plugin;
	}

	async load(): Promise<TerminalSessionData> {
		const allData = (await this.plugin.loadData()) || {};
		const rawSession = allData.terminalSession || {};
		const session: TerminalSessionData = {
			...DEFAULT_SESSION,
			...rawSession,
			provider: normalizeConfiguredProvider(rawSession.provider),
		};
		this.cache = session;
		return session;
	}

	private async save(): Promise<void> {
		if (!this.cache) return;
		const allData = (await this.plugin.loadData()) || {};
		allData.terminalSession = this.cache;
		await this.plugin.saveData(allData);
	}

	async getSessionId(): Promise<string | null> {
		if (!this.cache) await this.load();
		return this.cache!.sessionId;
	}

	getProvider(): AssistantProvider | null {
		return this.cache?.provider ?? null;
	}

	async setSessionId(id: string): Promise<void> {
		if (!this.cache) await this.load();
		this.cache!.sessionId = id;
		await this.save();
	}

	async setProvider(provider: AssistantProvider | null): Promise<void> {
		if (!this.cache) await this.load();
		this.cache!.provider = provider;
		await this.save();
	}

	getLog(): ConversationEntry[] {
		return this.cache?.log || [];
	}

	async appendLog(entry: ConversationEntry): Promise<void> {
		if (!this.cache) await this.load();
		this.cache!.log.push(entry);
		await this.save();
	}

	async removeLastExchange(): Promise<ConversationEntry | null> {
		if (!this.cache) await this.load();
		const log = this.cache!.log;

		// Remove last steward entry and last user entry
		// Find last steward
		let lastStewardIdx = -1;
		for (let i = log.length - 1; i >= 0; i--) {
			if (log[i].role === 'steward') { lastStewardIdx = i; break; }
		}
		// Find last user entry before it
		let lastUserIdx = -1;
		for (let i = lastStewardIdx - 1; i >= 0; i--) {
			if (log[i].role === 'user') { lastUserIdx = i; break; }
		}

		if (lastStewardIdx === -1) return null;

		// Remove from the earlier index first
		if (lastUserIdx !== -1 && lastUserIdx < lastStewardIdx) {
			log.splice(lastStewardIdx, 1);
			log.splice(lastUserIdx, 1);
		} else {
			log.splice(lastStewardIdx, 1);
		}

		await this.save();

		// Return the previous steward entry (the question to re-show)
		for (let i = log.length - 1; i >= 0; i--) {
			if (log[i].role === 'steward') return log[i];
		}
		return null;
	}

	async clear(): Promise<void> {
		this.cache = { ...DEFAULT_SESSION };
		await this.save();
	}

	async start(): Promise<void> {
		if (!this.cache) await this.load();
		this.cache!.startedAt = new Date().toISOString();
		await this.save();
	}
}
