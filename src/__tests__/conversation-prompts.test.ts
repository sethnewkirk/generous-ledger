import { buildChatPrompt, buildOnboardingPrompt, ONBOARDING_COMPLETE_TOKEN, parseOnboardingCompletion } from '../conversation-prompts';
import type { StewardThread } from '../chat-types';
import path from 'path';
import { promises as fs } from 'fs';

const REPO_ROOT = path.resolve(__dirname, '..', '..');

const adapter = {
	async exists(targetPath: string): Promise<boolean> {
		try {
			await fs.access(path.join(REPO_ROOT, targetPath));
			return true;
		} catch {
			return false;
		}
	},
	async read(targetPath: string): Promise<string> {
		return fs.readFile(path.join(REPO_ROOT, targetPath), 'utf8');
	},
};

const noteIntent = {
	notePath: 'Inbox.md',
	selectedText: '@Steward Please help me follow up with [[Max]].',
	promptText: 'Please help me follow up with [[Max]].',
	anchorStart: { line: 4, ch: 0 },
	anchorEnd: { line: 4, ch: 40 },
	triggerSource: 'mention' as const,
	capturedAt: '2026-04-16T10:02:00.000Z',
};

function buildThread(): StewardThread {
	return {
		threadId: 'thread_onboarding',
		threadKind: 'onboarding',
		status: 'active',
		provider: 'codex',
		title: 'Onboarding',
		createdAt: '2026-04-16T10:00:00.000Z',
		updatedAt: '2026-04-16T10:00:00.000Z',
		runtimeSessionId: null,
		sourceContext: null,
		onboardingCompletedAt: null,
		turns: [
			{
				turnId: 'turn_1',
				role: 'assistant',
				text: 'Who are you and what season of life are you in?',
				createdAt: '2026-04-16T10:00:00.000Z',
				noteIntent: null,
				activitySummary: null,
			},
			{
				turnId: 'turn_2',
				role: 'user',
				text: 'I am Seth and I am trying to get my life organized.',
				createdAt: '2026-04-16T10:01:00.000Z',
				noteIntent: null,
				activitySummary: null,
			},
		],
	};
}

describe('conversation prompts', () => {
	test('builds chat prompts with policy and retrieved context first', async () => {
		const prompt = await buildChatPrompt(adapter, {
			provider: 'codex',
			userText: 'Please help me follow up with [[Max]].',
			noteIntent,
		});

		expect(prompt).toContain('<POLICY_PACKET>');
		expect(prompt).toContain('<RETRIEVED_CONTEXT>');
		expect(prompt).toContain('<ATTACHED_SOURCE_CONTEXT>');
		expect(prompt).toContain('<USER_REQUEST>');
		expect(prompt.indexOf('<POLICY_PACKET>')).toBeLessThan(prompt.indexOf('<USER_REQUEST>'));
	});

	test('builds onboarding prompts from the stored transcript', async () => {
		const prompt = await buildOnboardingPrompt(adapter, 'codex', buildThread());
		expect(prompt).toContain('<POLICY_PACKET>');
		expect(prompt).toContain('<TRANSCRIPT_SO_FAR>');
		expect(prompt).toContain('USER: I am Seth and I am trying to get my life organized.');
		expect(prompt).toContain(ONBOARDING_COMPLETE_TOKEN);
		expect(prompt).not.toContain('Read the runtime entrypoint plus docs/FRAMEWORK.md and docs/STEWARD_SPEC.md before meaningful work.');
	});

	test('detects and strips the onboarding completion token', () => {
		const result = parseOnboardingCompletion(`One last question.\n${ONBOARDING_COMPLETE_TOKEN}`);
		expect(result.completed).toBe(true);
		expect(result.cleanedText).toBe('One last question.');
	});
});
