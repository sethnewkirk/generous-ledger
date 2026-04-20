import { ClaudeCodeProcess } from './claude-process';
import { CodexExecEvent, CodexExecProcess, extractCodexError, extractCodexFinalText, extractCodexThreadId } from './codex-process';
import { StreamMessage, extractError, extractSessionId, extractStreamingText, extractTextContent } from './stream-parser';
import type { AssistantProvider } from './provider-types';

export interface RuntimeCallbacks {
	onText?: (fullText: string) => void;
	onToolUse?: (toolName: string | null) => void;
}

export interface RuntimeOptions {
	provider: AssistantProvider;
	prompt: string;
	cwd: string;
	sessionId?: string;
	model?: string;
	binaryPath?: string;
	timeoutMs?: number;
}

export interface RuntimeResult {
	text: string;
	sessionId: string | null;
	error: string | null;
}

export async function runProviderTurn(
	options: RuntimeOptions,
	callbacks: RuntimeCallbacks = {}
): Promise<RuntimeResult> {
	if (options.provider === 'claude') {
		return runClaudeTurn(options, callbacks);
	}

	return runCodexTurn(options, callbacks);
}

async function runClaudeTurn(
	options: RuntimeOptions,
	callbacks: RuntimeCallbacks
): Promise<RuntimeResult> {
	const proc = new ClaudeCodeProcess();
	const messages: StreamMessage[] = [];
	let lastText = '';

	return new Promise<RuntimeResult>((resolve, reject) => {
		proc.on('message', (message: StreamMessage) => {
			messages.push(message);
			if (message.type === 'stream_event' || message.type === 'assistant') {
				const nextText = extractStreamingText(messages) || extractTextContent(messages);
				if (nextText && nextText !== lastText) {
					lastText = nextText;
					callbacks.onText?.(nextText);
				}
			}
		});

		proc.on('close', () => {
			const error = extractError(messages);
			resolve({
				text: lastText || extractTextContent(messages),
				sessionId: extractSessionId(messages),
				error,
			});
		});

		proc.on('error', (error: Error) => {
			reject(error);
		});

		void proc.query(options.prompt, {
			cwd: options.cwd,
			sessionId: options.sessionId,
			model: options.model,
			claudeCodePath: options.binaryPath,
			timeoutMs: options.timeoutMs,
		});
	});
}

async function runCodexTurn(
	options: RuntimeOptions,
	callbacks: RuntimeCallbacks
): Promise<RuntimeResult> {
	const proc = new CodexExecProcess();
	const events: CodexExecEvent[] = [];

	return new Promise<RuntimeResult>((resolve, reject) => {
		proc.on('message', (event: CodexExecEvent) => {
			events.push(event);
			const nextText = extractCodexFinalText(events);
			if (nextText) {
				callbacks.onText?.(nextText);
			}
		});

		proc.on('close', (exitCode: number | null) => {
			const finalText = extractCodexFinalText(events);
			resolve({
				text: finalText,
				sessionId: extractCodexThreadId(events),
				error: extractCodexError(proc.getStderr(), exitCode, finalText),
			});
		});

		proc.on('error', (error: Error) => {
			reject(error);
		});

		void proc.query(options.prompt, {
			cwd: options.cwd,
			sessionId: options.sessionId,
			model: options.model,
			codexPath: options.binaryPath,
			timeoutMs: options.timeoutMs,
		});
	});
}
