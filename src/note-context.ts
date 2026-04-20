import { TFile, type Editor } from 'obsidian';
import type { NoteIntent, NoteTriggerSource } from './chat-types';
import { DEFAULT_ASSISTANT_HANDLE } from './assistant-handle';
import { removeAssistantMentionFromText } from './trigger';

export interface SourcePosition {
	line: number;
	ch: number;
}

export interface SourceRange {
	from: SourcePosition;
	to: SourcePosition;
}

function comparePositions(left: SourcePosition, right: SourcePosition): number {
	if (left.line !== right.line) {
		return left.line - right.line;
	}
	return left.ch - right.ch;
}

function normalizeRange(range: SourceRange): SourceRange {
	return comparePositions(range.from, range.to) <= 0
		? range
		: { from: range.to, to: range.from };
}

function positionToOffset(text: string, pos: SourcePosition): number {
	const lines = text.split('\n');
	let offset = 0;

	for (let index = 0; index < pos.line; index += 1) {
		offset += (lines[index] ?? '').length + 1;
	}

	return offset + pos.ch;
}

function offsetToPosition(text: string, offset: number): SourcePosition {
	const slice = text.slice(0, offset);
	const lines = slice.split('\n');
	const line = lines.length - 1;
	const ch = lines[lines.length - 1]?.length ?? 0;
	return { line, ch };
}

export function createNoteIntent(
	file: TFile,
	selectedText: string,
	promptText: string,
	range: SourceRange,
	triggerSource: NoteTriggerSource
): NoteIntent {
	const normalizedRange = normalizeRange(range);
	return {
		notePath: file.path,
		selectedText,
		promptText,
		anchorStart: normalizedRange.from,
		anchorEnd: normalizedRange.to,
		triggerSource,
		capturedAt: new Date().toISOString(),
	};
}

export function buildCalloutMarkdown(text: string, assistantHandle = DEFAULT_ASSISTANT_HANDLE): string {
	const body = text
		.trim()
		.split('\n')
		.map((line) => line.trim() ? `> ${line}` : '>')
		.join('\n');
	return `> [!steward] ${assistantHandle}\n${body}`;
}

export function insertCalloutIntoNoteText(
	documentText: string,
	intent: NoteIntent,
	responseText: string,
	assistantHandle = DEFAULT_ASSISTANT_HANDLE
): string {
	const startOffset = positionToOffset(documentText, intent.anchorStart);
	const endOffset = positionToOffset(documentText, intent.anchorEnd);
	const selectedText = documentText.slice(startOffset, endOffset);
	const cleanedSelection = removeAssistantMentionFromText(selectedText, assistantHandle) || intent.promptText;
	const callout = buildCalloutMarkdown(responseText, assistantHandle);

	return `${documentText.slice(0, startOffset)}${cleanedSelection}\n\n${callout}${documentText.slice(endOffset)}`;
}

export function replaceSelectionInNoteText(documentText: string, intent: NoteIntent, replacement: string): string {
	const startOffset = positionToOffset(documentText, intent.anchorStart);
	const endOffset = positionToOffset(documentText, intent.anchorEnd);
	return `${documentText.slice(0, startOffset)}${replacement.trim()}${documentText.slice(endOffset)}`;
}

export function selectionStillMatches(documentText: string, intent: NoteIntent): boolean {
	const startOffset = positionToOffset(documentText, intent.anchorStart);
	const endOffset = positionToOffset(documentText, intent.anchorEnd);
	return documentText.slice(startOffset, endOffset) === intent.selectedText;
}

export function buildLinkedNotePath(sourcePath: string): string {
	const lastSlash = sourcePath.lastIndexOf('/');
	const directory = lastSlash === -1 ? '' : `${sourcePath.slice(0, lastSlash + 1)}`;
	const baseName = sourcePath.slice(lastSlash + 1).replace(/\.md$/i, '');
	const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
	return `${directory}${baseName} - Steward Reply ${timestamp}.md`;
}

export function buildLinkedNoteContent(sourcePath: string, responseText: string): string {
	const sourceName = sourcePath.split('/').pop()?.replace(/\.md$/i, '') || sourcePath;
	return [
		'# Steward Reply',
		'',
		`Source: [[${sourceName}]]`,
		'',
		responseText.trim(),
		'',
	].join('\n');
}

export function getSelectionRangeFromEditor(editor: Editor): SourceRange {
	const selection = editor.listSelections()[0];
	return {
		from: selection.anchor,
		to: selection.head,
	};
}

export function getRangeForOffsets(documentText: string, fromOffset: number, toOffset: number): SourceRange {
	return {
		from: offsetToPosition(documentText, fromOffset),
		to: offsetToPosition(documentText, toOffset),
	};
}
