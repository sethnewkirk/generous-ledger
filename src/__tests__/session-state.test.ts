import { clearStoredSessionId, getStoredSessionId, setStoredSessionId } from '../session-state';

describe('session state helpers', () => {
	test('reads legacy Claude session ids', () => {
		expect(getStoredSessionId({ claude_session_id: 'session_1234567890' }, 'claude')).toEqual({
			sessionId: 'session_1234567890',
			wasInvalid: false,
		});
	});

	test('flags invalid stored session data', () => {
		expect(getStoredSessionId({ steward_sessions: { codex: 123 } }, 'codex')).toEqual({
			sessionId: null,
			wasInvalid: true,
		});
	});

	test('stores provider-specific sessions and removes the legacy key on write', () => {
		const frontmatter: Record<string, unknown> = {
			claude_session_id: 'legacy_1234567890',
		};

		setStoredSessionId(frontmatter, 'claude', 'claude_1234567890');
		setStoredSessionId(frontmatter, 'codex', 'codex_1234567890');

		expect(frontmatter).toEqual({
			steward_sessions: {
				claude: 'claude_1234567890',
				codex: 'codex_1234567890',
			},
		});
	});

	test('clears one provider without disturbing the other', () => {
		const frontmatter: Record<string, unknown> = {
			steward_sessions: {
				claude: 'claude_1234567890',
				codex: 'codex_1234567890',
			},
		};

		clearStoredSessionId(frontmatter, 'claude');

		expect(frontmatter).toEqual({
			steward_sessions: {
				codex: 'codex_1234567890',
			},
		});
	});
});
