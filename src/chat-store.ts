import type { AssistantProvider } from './provider-types';
import type { StewardThread, StewardThreadIndex, StewardThreadKind, StewardThreadSummary } from './chat-types';

interface VaultAdapterLike {
	exists(path: string, sensitive?: boolean): Promise<boolean>;
	read(path: string): Promise<string>;
	write(path: string, data: string): Promise<void>;
	mkdir(path: string): Promise<void>;
}

const STORE_ROOT = '.steward/chat';
const THREADS_ROOT = `${STORE_ROOT}/threads`;
const INDEX_PATH = `${STORE_ROOT}/index.json`;

export function createThreadId(): string {
	return `thread_${crypto.randomUUID()}`;
}

export function createThreadTitle(text?: string, fallback = 'New chat'): string {
	const normalized = (text || '')
		.replace(/\s+/g, ' ')
		.trim();
	if (!normalized) {
		return fallback;
	}

	return normalized.length > 72
		? `${normalized.slice(0, 69).trimEnd()}...`
		: normalized;
}

function getDefaultIndex(): StewardThreadIndex {
	return {
		version: 1,
		threads: [],
	};
}

export class StewardThreadStore {
	constructor(private adapter: VaultAdapterLike) {}

	getStoreRoot(): string {
		return STORE_ROOT;
	}

	getThreadPath(threadId: string): string {
		return `${THREADS_ROOT}/${threadId}.json`;
	}

	async ensureStore(): Promise<void> {
		await this.ensureFolder('.steward');
		await this.ensureFolder(STORE_ROOT);
		await this.ensureFolder(THREADS_ROOT);

		if (!(await this.adapter.exists(INDEX_PATH))) {
			await this.adapter.write(INDEX_PATH, JSON.stringify(getDefaultIndex(), null, 2));
		}
	}

	async createThread(thread: Omit<StewardThread, 'threadId' | 'createdAt' | 'updatedAt'>): Promise<StewardThread> {
		await this.ensureStore();
		const now = new Date().toISOString();
		const storedThread: StewardThread = {
			...thread,
			threadId: createThreadId(),
			createdAt: now,
			updatedAt: now,
		};
		await this.saveThread(storedThread);
		return storedThread;
	}

	async loadThread(threadId: string): Promise<StewardThread | null> {
		await this.ensureStore();
		const threadPath = this.getThreadPath(threadId);
		if (!(await this.adapter.exists(threadPath))) {
			return null;
		}

		const raw = await this.adapter.read(threadPath);
		return JSON.parse(raw) as StewardThread;
	}

	async saveThread(thread: StewardThread): Promise<void> {
		await this.ensureStore();
		thread.updatedAt = new Date().toISOString();
		await this.adapter.write(this.getThreadPath(thread.threadId), JSON.stringify(thread, null, 2));

		const index = await this.loadIndex();
		const summary = this.toSummary(thread);
		const nextThreads = index.threads.filter((entry) => entry.threadId !== thread.threadId);
		nextThreads.push(summary);
		nextThreads.sort((left, right) => {
			const updatedCompare = right.updatedAt.localeCompare(left.updatedAt);
			if (updatedCompare !== 0) {
				return updatedCompare;
			}
			if (left.threadId === thread.threadId) {
				return -1;
			}
			if (right.threadId === thread.threadId) {
				return 1;
			}
			return right.createdAt.localeCompare(left.createdAt);
		});

		await this.adapter.write(INDEX_PATH, JSON.stringify({
			version: 1,
			threads: nextThreads,
		} satisfies StewardThreadIndex, null, 2));
	}

	async listThreads(kind?: StewardThreadKind, provider?: AssistantProvider): Promise<StewardThreadSummary[]> {
		const index = await this.loadIndex();
		return index.threads.filter((entry) => {
			if (kind && entry.threadKind !== kind) {
				return false;
			}
			if (provider && entry.provider !== provider) {
				return false;
			}
			return true;
		});
	}

	async getLatestThread(kind: StewardThreadKind, provider?: AssistantProvider): Promise<StewardThread | null> {
		const summaries = await this.listThreads(kind, provider);
		if (summaries.length === 0) {
			return null;
		}
		return this.loadThread(summaries[0].threadId);
	}

	async upsertImportedThread(thread: StewardThread): Promise<void> {
		await this.ensureStore();
		await this.saveThread(thread);
	}

	private async loadIndex(): Promise<StewardThreadIndex> {
		await this.ensureStore();
		const raw = await this.adapter.read(INDEX_PATH);
		const parsed = JSON.parse(raw) as Partial<StewardThreadIndex>;
		return {
			version: 1,
			threads: Array.isArray(parsed.threads) ? parsed.threads : [],
		};
	}

	private toSummary(thread: StewardThread): StewardThreadSummary {
		return {
			threadId: thread.threadId,
			threadKind: thread.threadKind,
			status: thread.status,
			provider: thread.provider,
			title: thread.title,
			createdAt: thread.createdAt,
			updatedAt: thread.updatedAt,
			sourceNotePath: thread.sourceContext?.notePath ?? null,
		};
	}

	private async ensureFolder(path: string): Promise<void> {
		if (!(await this.adapter.exists(path))) {
			await this.adapter.mkdir(path);
		}
	}
}
