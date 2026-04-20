import { AssistantProvider } from './provider-types';

export interface SessionLookupResult {
	sessionId: string | null;
	wasInvalid: boolean;
}

const LEGACY_SESSION_KEY = 'claude_session_id';
const SESSION_MAP_KEY = 'steward_sessions';

function isValidSessionId(value: unknown): value is string {
	return typeof value === 'string' && value.length >= 10;
}

function getSessionMap(frontmatter: Record<string, unknown> | null | undefined): Record<string, string> {
	const raw = frontmatter?.[SESSION_MAP_KEY];
	if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
		return {};
	}

	const sessions: Record<string, string> = {};
	for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
		if (isValidSessionId(value)) {
			sessions[key] = value;
		}
	}

	return sessions;
}

export function getStoredSessionId(
	frontmatter: Record<string, unknown> | null | undefined,
	provider: AssistantProvider
): SessionLookupResult {
	const sessions = getSessionMap(frontmatter);
	if (provider in sessions) {
		return { sessionId: sessions[provider], wasInvalid: false };
	}

	const rawSessions = frontmatter?.[SESSION_MAP_KEY];
	if (rawSessions && typeof rawSessions === 'object' && !Array.isArray(rawSessions)) {
		const rawValue = (rawSessions as Record<string, unknown>)[provider];
		if (rawValue !== undefined && !isValidSessionId(rawValue)) {
			return { sessionId: null, wasInvalid: true };
		}
	}

	if (provider === 'claude') {
		const legacy = frontmatter?.[LEGACY_SESSION_KEY];
		if (legacy === undefined) {
			return { sessionId: null, wasInvalid: false };
		}

		if (isValidSessionId(legacy)) {
			return { sessionId: legacy, wasInvalid: false };
		}

		return { sessionId: null, wasInvalid: true };
	}

	return { sessionId: null, wasInvalid: false };
}

export function setStoredSessionId(
	frontmatter: Record<string, unknown>,
	provider: AssistantProvider,
	sessionId: string
): void {
	const sessions = getSessionMap(frontmatter);
	sessions[provider] = sessionId;
	frontmatter[SESSION_MAP_KEY] = sessions;
	delete frontmatter[LEGACY_SESSION_KEY];
}

export function clearStoredSessionId(
	frontmatter: Record<string, unknown>,
	provider?: AssistantProvider
): void {
	if (!provider) {
		delete frontmatter[SESSION_MAP_KEY];
		delete frontmatter[LEGACY_SESSION_KEY];
		return;
	}

	const sessions = getSessionMap(frontmatter);
	delete sessions[provider];

	if (Object.keys(sessions).length > 0) {
		frontmatter[SESSION_MAP_KEY] = sessions;
	} else {
		delete frontmatter[SESSION_MAP_KEY];
	}

	if (provider === 'claude') {
		delete frontmatter[LEGACY_SESSION_KEY];
	}
}
