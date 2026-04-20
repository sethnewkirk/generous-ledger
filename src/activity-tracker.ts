import * as fs from 'fs';
import * as path from 'path';
import type { ActivitySummary, NoteIntent, NoteWritebackAction } from './chat-types';

export interface ActivitySnapshot {
	files: Map<string, string>;
}

function relativePosix(basePath: string, absolutePath: string): string {
	return path.relative(basePath, absolutePath).split(path.sep).join('/');
}

function scanDirectory(basePath: string, absoluteDir: string, files: Map<string, string>): void {
	if (!fs.existsSync(absoluteDir)) {
		return;
	}

	for (const entry of fs.readdirSync(absoluteDir, { withFileTypes: true })) {
		const absolutePath = path.join(absoluteDir, entry.name);
		if (entry.isDirectory()) {
			scanDirectory(basePath, absolutePath, files);
			continue;
		}

		const stat = fs.statSync(absolutePath);
		files.set(relativePosix(basePath, absolutePath), `${stat.mtimeMs}:${stat.size}`);
	}
}

export function captureActivitySnapshot(vaultPath: string, trackedPaths: string[]): ActivitySnapshot {
	const files = new Map<string, string>();
	const uniquePaths = Array.from(new Set(trackedPaths.filter(Boolean)));

	for (const trackedPath of uniquePaths) {
		const absolutePath = path.join(vaultPath, trackedPath);
		if (!fs.existsSync(absolutePath)) {
			continue;
		}

		const stat = fs.statSync(absolutePath);
		if (stat.isDirectory()) {
			scanDirectory(vaultPath, absolutePath, files);
		} else {
			files.set(trackedPath, `${stat.mtimeMs}:${stat.size}`);
		}
	}

	return { files };
}

export function diffActivitySnapshots(before: ActivitySnapshot, after: ActivitySnapshot): string[] {
	const changed = new Set<string>();

	for (const [filePath, signature] of before.files.entries()) {
		if (after.files.get(filePath) !== signature) {
			changed.add(filePath);
		}
	}

	for (const [filePath, signature] of after.files.entries()) {
		if (before.files.get(filePath) !== signature) {
			changed.add(filePath);
		}
	}

	return Array.from(changed).sort();
}

function getLineRange(noteIntent: NoteIntent): string {
	const start = noteIntent.anchorStart.line + 1;
	const end = noteIntent.anchorEnd.line + 1;
	return start === end ? `${start}` : `${start}-${end}`;
}

export function buildActivitySummary(
	noteIntent: NoteIntent | null,
	changedFiles: string[],
	availableActions: NoteWritebackAction[]
): ActivitySummary {
	const profileUpdates = changedFiles.filter((filePath) => filePath.startsWith('profile/'));
	const memoryUpdates = changedFiles.filter((filePath) => filePath.startsWith('memory/'));
	const otherUpdates = changedFiles.filter((filePath) => !filePath.startsWith('profile/') && !filePath.startsWith('memory/'));
	const currentNoteViolation = noteIntent ? changedFiles.includes(noteIntent.notePath) : false;

	return {
		attachedContext: noteIntent ? {
			notePath: noteIntent.notePath,
			triggerSource: noteIntent.triggerSource,
			lineRange: getLineRange(noteIntent),
		} : null,
		changedFiles,
		profileUpdates,
		memoryUpdates,
		otherUpdates,
		currentNoteViolation,
		availableActions,
	};
}
