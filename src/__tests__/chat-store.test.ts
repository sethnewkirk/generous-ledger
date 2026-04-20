import { StewardThreadStore } from '../chat-store';
import type { StewardThread } from '../chat-types';

class MemoryAdapter {
	private files = new Map<string, string>();
	private folders = new Set<string>();

	async exists(path: string): Promise<boolean> {
		return this.files.has(path) || this.folders.has(path);
	}

	async read(path: string): Promise<string> {
		const value = this.files.get(path);
		if (value === undefined) {
			throw new Error(`Missing file: ${path}`);
		}
		return value;
	}

	async write(path: string, data: string): Promise<void> {
		this.files.set(path, data);
	}

	async mkdir(path: string): Promise<void> {
		this.folders.add(path);
	}
}

function buildThread(overrides: Partial<StewardThread> = {}): StewardThread {
	return {
		threadId: overrides.threadId ?? 'thread_1',
		threadKind: overrides.threadKind ?? 'chat',
		status: overrides.status ?? 'active',
		provider: overrides.provider ?? 'codex',
		title: overrides.title ?? 'Example thread',
		createdAt: overrides.createdAt ?? '2026-04-16T10:00:00.000Z',
		updatedAt: overrides.updatedAt ?? '2026-04-16T10:00:00.000Z',
		runtimeSessionId: overrides.runtimeSessionId ?? null,
		turns: overrides.turns ?? [],
		sourceContext: overrides.sourceContext ?? null,
		onboardingCompletedAt: overrides.onboardingCompletedAt ?? null,
	};
}

describe('StewardThreadStore', () => {
	test('creates and loads threads from the hidden store', async () => {
		const store = new StewardThreadStore(new MemoryAdapter());
		const thread = await store.createThread({
			threadKind: 'chat',
			status: 'active',
			provider: 'codex',
			title: 'New chat',
			runtimeSessionId: null,
			turns: [],
			sourceContext: null,
			onboardingCompletedAt: null,
		});

		const loaded = await store.loadThread(thread.threadId);
		expect(loaded?.threadKind).toBe('chat');
		expect(loaded?.title).toBe('New chat');
		expect((await store.listThreads('chat', 'codex'))).toHaveLength(1);
	});

	test('updates the index when an imported thread is saved', async () => {
		const store = new StewardThreadStore(new MemoryAdapter());
		await store.upsertImportedThread(buildThread({
			threadId: 'thread_alpha',
			title: 'Alpha',
			updatedAt: '2026-04-16T08:00:00.000Z',
		}));
		await store.upsertImportedThread(buildThread({
			threadId: 'thread_beta',
			title: 'Beta',
			updatedAt: '2026-04-16T09:00:00.000Z',
		}));

		const summaries = await store.listThreads('chat', 'codex');
		expect(summaries.map((summary) => summary.threadId)).toEqual(['thread_beta', 'thread_alpha']);
		expect((await store.getLatestThread('chat', 'codex'))?.threadId).toBe('thread_beta');
	});
});
