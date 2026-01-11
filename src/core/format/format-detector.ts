import { App, TFile } from 'obsidian';

export type ObsidianFormat = 'markdown' | 'canvas' | 'base';

export interface FormatContext {
	format: ObsidianFormat;
	file: TFile;
	content: string;
	nodeId?: string;
	connectedNodes?: string[];
	insertPosition?: { line: number; ch: number };
}

export function detectFormat(file: TFile): ObsidianFormat {
	const ext = file.extension.toLowerCase();

	switch (ext) {
		case 'canvas':
			return 'canvas';
		case 'base':
			return 'base';
		default:
			return 'markdown';
	}
}

export async function buildFormatContext(
	app: App,
	file: TFile,
	cursorPosition?: { line: number; ch: number }
): Promise<FormatContext> {
	const format = detectFormat(file);
	const content = await app.vault.read(file);

	const context: FormatContext = { format, file, content };

	if (format === 'canvas' && cursorPosition) {
		try {
			const canvas = JSON.parse(content);
			context.nodeId = findNodeAtPosition(canvas, cursorPosition);
			context.connectedNodes = findConnectedNodes(canvas, context.nodeId);
		} catch (e) {
			console.error('Error parsing canvas:', e);
		}
	}

	return context;
}

function findNodeAtPosition(canvas: any, position: { line: number; ch: number }): string | undefined {
	// Simplified: In actual implementation, would need canvas API
	// For now, return the first text node that contains @Claude
	const nodes = canvas.nodes || [];
	for (const node of nodes) {
		if (node.type === 'text' && node.text && node.text.includes('@Claude')) {
			return node.id;
		}
	}
	return undefined;
}

function findConnectedNodes(canvas: any, nodeId?: string): string[] {
	if (!nodeId) return [];

	const edges = canvas.edges || [];
	const connected: string[] = [];

	for (const edge of edges) {
		if (edge.fromNode === nodeId) {
			connected.push(edge.toNode);
		}
		if (edge.toNode === nodeId) {
			connected.push(edge.fromNode);
		}
	}

	return connected;
}
