import type { NoteIntent, StewardThread } from './chat-types';
import { buildPolicyPacket, type PolicyIntentTag, type PolicyWriteIntent } from './policy-loader';
import type { AssistantProvider } from './provider-types';

export const ONBOARDING_COMPLETE_TOKEN = '<!-- ONBOARDING_COMPLETE -->';
const MAX_CONTEXT_CHARS = 2200;
const MAX_CONTEXT_FILES = 4;

function formatNoteContext(noteIntent: NoteIntent): string {
	const start = noteIntent.anchorStart.line + 1;
	const end = noteIntent.anchorEnd.line + 1;
	const lineLabel = start === end ? `${start}` : `${start}-${end}`;

	return [
		'ATTACHED NOTE CONTEXT',
		`Source note: ${noteIntent.notePath}`,
		`Lines: ${lineLabel}`,
		`Trigger source: ${noteIntent.triggerSource}`,
		'Attached text:',
		noteIntent.selectedText.trim(),
	].join('\n');
}

function renderSection(name: string, content: string): string {
	return `<${name}>\n${content.trim()}\n</${name}>`;
}

function truncateForPrompt(text: string, maxChars: number): string {
	const normalized = text.trim();
	if (normalized.length <= maxChars) {
		return normalized;
	}
	return `${normalized.slice(0, maxChars - 3).trimEnd()}...`;
}

function extractWikilinks(text: string): string[] {
	const matches = text.matchAll(/\[\[([^[\]|#]+)(?:[#|][^\]]+)?\]\]/g);
	const targets = new Set<string>();
	for (const match of matches) {
		const target = match[1]?.trim();
		if (target) {
			targets.add(target);
		}
	}
	return [...targets];
}

async function readContextFile(adapter: {
	exists(path: string, sensitive?: boolean): Promise<boolean>;
	read(path: string): Promise<string>;
}, path: string): Promise<string | null> {
	if (!(await adapter.exists(path))) {
		return null;
	}
	const body = truncateForPrompt(await adapter.read(path), MAX_CONTEXT_CHARS);
	return `<FILE path="${path}">\n${body}\n</FILE>`;
}

async function loadChatRetrievedContext(adapter: {
	exists(path: string, sensitive?: boolean): Promise<boolean>;
	read(path: string): Promise<string>;
}, noteIntent?: NoteIntent | null): Promise<string> {
	const candidatePaths = ['profile/index.md', 'profile/current.md'];
	for (const wikilinkTarget of extractWikilinks(noteIntent?.selectedText ?? '')) {
		candidatePaths.push(`profile/people/${wikilinkTarget}.md`);
		candidatePaths.push(`profile/commitments/${wikilinkTarget}.md`);
	}

	const rendered: string[] = [];
	for (const path of candidatePaths) {
		if (rendered.length >= MAX_CONTEXT_FILES) {
			break;
		}
		const section = await readContextFile(adapter, path);
		if (section) {
			rendered.push(section);
		}
	}

	return rendered.length > 0
		? renderSection('RETRIEVED_CONTEXT', rendered.join('\n\n'))
		: renderSection('RETRIEVED_CONTEXT', 'No compiled profile context was available.');
}

function inferChatWriteIntent(userText: string, noteIntent?: NoteIntent | null): PolicyWriteIntent {
	const normalized = userText.toLowerCase();
	if (noteIntent) {
		return 'note_writeback';
	}
	if (/\b(profile|person|people|commitment|current\.md|patterns)\b/.test(normalized)) {
		return 'profile';
	}
	if (/\b(remember|memory|claim|event|follow[- ]?up|obligation)\b/.test(normalized)) {
		return 'memory';
	}
	return 'none';
}

function inferIntentTags(userText: string, noteIntent?: NoteIntent | null): PolicyIntentTag[] {
	const normalized = userText.toLowerCase();
	const tags = new Set<PolicyIntentTag>();

	if (noteIntent) {
		tags.add('file_writing');
	}
	if (/\b(friend|wife|husband|father|mother|brother|sister|family|relationship|message|email|max|kate|caleb)\b/.test(normalized)) {
		tags.add('relationship');
	}
	if (/\b(recommend|recommendation|buy|choose|which should|what should i get)\b/.test(normalized)) {
		tags.add('recommendation');
	}
	if (/\b(plan|planning|schedule|organize|roadmap|next step|priorit)/.test(normalized)) {
		tags.add('planning');
	}
	if (/\b(right|wrong|moral|immoral|sin|should i|ought)\b/.test(normalized)) {
		tags.add('moral_guidance');
	}

	return [...tags];
}

export async function buildChatPrompt(adapter: {
	exists(path: string, sensitive?: boolean): Promise<boolean>;
	read(path: string): Promise<string>;
}, params: {
	provider: AssistantProvider;
	userText: string;
	noteIntent?: NoteIntent | null;
}): Promise<string> {
	const policyPacket = await buildPolicyPacket(adapter, {
		surface: 'chat',
		workflow: params.noteIntent ? 'note_chat' : 'general_chat',
		provider: params.provider,
		writeIntent: inferChatWriteIntent(params.userText, params.noteIntent),
		intentTags: inferIntentTags(params.userText, params.noteIntent),
	});

	const sections = [
		policyPacket.markdown,
		await loadChatRetrievedContext(adapter, params.noteIntent),
	];

	if (params.noteIntent) {
		sections.push(renderSection('ATTACHED_SOURCE_CONTEXT', formatNoteContext(params.noteIntent)));
	}

	sections.push(
		renderSection('INTERACTION_RULES', [
			'You are responding inside the Obsidian Steward Chat pane.',
			'Use normal concise prose. Do not use callout syntax unless the user explicitly asks for it.',
			'Do not edit the current note directly. The plugin will offer explicit note write-back actions.',
			'You may update other vault files, especially profile/ and memory/, when the rules warrant it.',
		].join('\n')),
		renderSection('USER_REQUEST', params.userText)
	);

	return sections.join('\n');
}

export async function buildOnboardingPrompt(
	adapter: {
		exists(path: string, sensitive?: boolean): Promise<boolean>;
		read(path: string): Promise<string>;
	},
	provider: AssistantProvider,
	thread: StewardThread,
	latestUserText?: string
): Promise<string> {
	const policyPacket = await buildPolicyPacket(adapter, {
		surface: 'onboarding',
		workflow: 'onboarding',
		provider,
		writeIntent: 'profile',
		intentTags: ['planning', 'file_writing'],
	});
	const transcript = thread.turns
		.filter((turn) => turn.role === 'user' || turn.role === 'assistant')
		.map((turn) => `${turn.role === 'user' ? 'USER' : 'STEWARD'}: ${turn.text}`)
		.join('\n\n');

	const sections = [
		policyPacket.markdown,
		renderSection('SETUP_RULES', [
			`Provider: ${provider}`,
			'You are Steward beginning service with a new principal inside the Obsidian setup view.',
			'Conduct the onboarding protocol.',
			'Ask one bounded question at a time and keep responses short.',
			'Create profile files at section transitions, not after every answer.',
			'When onboarding is complete, append exactly this token on its own line after your final question:',
			ONBOARDING_COMPLETE_TOKEN,
		].join('\n')),
	];

	if (transcript) {
		sections.push(renderSection('TRANSCRIPT_SO_FAR', transcript));
	} else {
		sections.push(renderSection('INITIAL_ACTION', 'Begin with the opening line from the onboarding protocol and then ask the first question.'));
	}

	if (latestUserText) {
		sections.push(renderSection('NEW_USER_MESSAGE', latestUserText));
	}

	return sections.join('\n');
}

export function parseOnboardingCompletion(text: string): { cleanedText: string; completed: boolean } {
	if (!text.includes(ONBOARDING_COMPLETE_TOKEN)) {
		return { cleanedText: text.trim(), completed: false };
	}

	return {
		cleanedText: text.replace(ONBOARDING_COMPLETE_TOKEN, '').trim(),
		completed: true,
	};
}
