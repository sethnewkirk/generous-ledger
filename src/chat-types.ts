import type { AssistantProvider } from './provider-types';

export type StewardThreadKind = 'chat' | 'onboarding';
export type StewardThreadStatus = 'active' | 'completed';
export type StewardTurnRole = 'user' | 'assistant' | 'system';
export type NoteTriggerSource = 'mention' | 'command' | 'ribbon';
export type NoteWritebackAction = 'insert-callout' | 'replace-selection' | 'create-linked-note';

export interface NoteAnchorPosition {
	line: number;
	ch: number;
}

export interface NoteIntent {
	notePath: string;
	selectedText: string;
	promptText: string;
	anchorStart: NoteAnchorPosition;
	anchorEnd: NoteAnchorPosition;
	triggerSource: NoteTriggerSource;
	capturedAt: string;
}

export interface ActivitySummary {
	attachedContext: {
		notePath: string;
		triggerSource: NoteTriggerSource;
		lineRange: string;
	} | null;
	changedFiles: string[];
	profileUpdates: string[];
	memoryUpdates: string[];
	otherUpdates: string[];
	currentNoteViolation: boolean;
	availableActions: NoteWritebackAction[];
}

export interface StewardTurn {
	turnId: string;
	role: StewardTurnRole;
	text: string;
	createdAt: string;
	noteIntent?: NoteIntent | null;
	activitySummary?: ActivitySummary | null;
}

export interface StewardThread {
	threadId: string;
	threadKind: StewardThreadKind;
	status: StewardThreadStatus;
	provider: AssistantProvider;
	title: string;
	createdAt: string;
	updatedAt: string;
	runtimeSessionId: string | null;
	turns: StewardTurn[];
	sourceContext: NoteIntent | null;
	onboardingCompletedAt: string | null;
}

export interface StewardThreadSummary {
	threadId: string;
	threadKind: StewardThreadKind;
	status: StewardThreadStatus;
	provider: AssistantProvider;
	title: string;
	createdAt: string;
	updatedAt: string;
	sourceNotePath: string | null;
}

export interface StewardThreadIndex {
	version: 1;
	threads: StewardThreadSummary[];
}
