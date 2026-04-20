import { buildCodexArgs, extractCodexError, extractCodexFinalText, extractCodexThreadId } from '../codex-process';

describe('codex process helpers', () => {
	test('builds codex exec args for a fresh request', () => {
		expect(buildCodexArgs('Reply now', { cwd: '/vault' })).toEqual([
			'-a',
			'never',
			'exec',
			'-C',
			'/vault',
			'--json',
			'--skip-git-repo-check',
			'--sandbox',
			'workspace-write',
			'--',
			'Reply now',
		]);
	});

	test('builds codex exec resume args when a session exists', () => {
		expect(buildCodexArgs('Continue', {
			cwd: '/vault',
			sessionId: 'thread_123',
			model: 'gpt-5.4',
		})).toEqual([
			'-a',
			'never',
			'exec',
			'-C',
			'/vault',
			'resume',
			'--json',
			'--skip-git-repo-check',
			'--model',
			'gpt-5.4',
			'thread_123',
			'--',
			'Continue',
		]);
	});

	test('protects prompts that begin with dashes from being parsed as flags', () => {
		expect(buildCodexArgs('--help', { cwd: '/vault' })).toEqual([
			'-a',
			'never',
			'exec',
			'-C',
			'/vault',
			'--json',
			'--skip-git-repo-check',
			'--sandbox',
			'workspace-write',
			'--',
			'--help',
		]);
	});

	test('extracts thread ids and final text from json events', () => {
		const events = [
			{ type: 'thread.started', thread_id: 'thread_abc' },
			{ type: 'item.completed', item: { type: 'agent_message', text: 'first' } },
			{ type: 'item.completed', item: { type: 'agent_message', text: 'final answer' } },
		];

		expect(extractCodexThreadId(events)).toBe('thread_abc');
		expect(extractCodexFinalText(events)).toBe('final answer');
	});

	test('prefers stderr text when reporting errors', () => {
		expect(extractCodexError('warning\nfatal problem\n', 1)).toBe('fatal problem');
		expect(extractCodexError('', 7)).toBe('Codex exited with code 7');
		expect(extractCodexError('', 0)).toBeNull();
	});

	test('ignores benign stderr warnings on successful runs', () => {
		const stderr = [
			'Reading additional input from stdin...',
			'2026-04-17T03:13:35.998474Z  WARN codex_core::plugins::manifest: ignoring interface.defaultPrompt: prompt must be at most 128 characters',
			'2026-04-17T03:13:36.576904Z  WARN codex_core::shell_snapshot: Failed to delete shell snapshot',
		].join('\n');

		expect(extractCodexError(stderr, 0, 'Yes. What do you need me to work on?')).toBeNull();
	});
});
