import { spawn, ChildProcess, execSync } from 'child_process';
import { EventEmitter } from 'events';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';

export interface CodexExecOptions {
	cwd: string;
	sessionId?: string;
	model?: string;
	codexPath?: string;
	timeoutMs?: number;
}

export interface CodexEventItem {
	id?: string;
	type?: string;
	text?: string;
	[key: string]: unknown;
}

export interface CodexExecEvent {
	type: string;
	thread_id?: string;
	item?: CodexEventItem;
	[key: string]: unknown;
}

export interface CodexStatus {
	installed: boolean;
	ready: boolean;
	version?: string;
	problem?: string;
}

const DEFAULT_TIMEOUT = 15 * 60 * 1000;

export class CodexExecProcess extends EventEmitter {
	private process: ChildProcess | null = null;
	private stderrBuffer = '';

	async query(prompt: string, options: CodexExecOptions): Promise<void> {
		const codexPath = options.codexPath && options.codexPath !== 'codex'
			? options.codexPath
			: findCodexPath();

		this.process = spawn(codexPath, buildCodexArgs(prompt, options), {
			env: {
				...process.env,
				PATH: `${process.env.PATH}:/usr/local/bin:/opt/homebrew/bin:${process.env.HOME}/.local/bin`
			},
			stdio: ['ignore', 'pipe', 'pipe']
		});

		let stdoutBuffer = '';
		this.process.stdout?.on('data', (chunk: Buffer) => {
			stdoutBuffer += chunk.toString();
			const lines = stdoutBuffer.split('\n');
			stdoutBuffer = lines.pop() || '';

			for (const line of lines) {
				const trimmed = line.trim();
				if (!trimmed.startsWith('{')) {
					continue;
				}

				try {
					const message = JSON.parse(trimmed) as CodexExecEvent;
					this.emit('message', message);
				} catch (error) {
					console.error('Failed to parse Codex JSON:', trimmed.substring(0, 120), error);
				}
			}
		});

		this.process.stderr?.on('data', (chunk: Buffer) => {
			this.stderrBuffer += chunk.toString();
		});

		this.process.on('close', (code) => {
			this.emit('close', code);
		});

		this.process.on('error', (error) => {
			console.error('Codex process error:', error);
			this.emit('error', error);
		});

		const timeout = options.timeoutMs || DEFAULT_TIMEOUT;
		const timeoutId = setTimeout(() => {
			this.abort();
			this.emit('error', new Error(`Request timed out after ${timeout / 60000} minutes`));
		}, timeout);

		this.process.on('close', () => clearTimeout(timeoutId));
	}

	getStderr(): string {
		return this.stderrBuffer;
	}

	abort(): void {
		this.process?.kill('SIGTERM');
	}
}

export function buildCodexArgs(prompt: string, options: CodexExecOptions): string[] {
	const args = ['-a', 'never', 'exec', '-C', options.cwd];

	if (options.sessionId) {
		args.push('resume');
	}

	args.push('--json', '--skip-git-repo-check');

	if (!options.sessionId) {
		args.push('--sandbox', 'workspace-write');
	}

	if (options.model) {
		args.push('--model', options.model);
	}

	if (options.sessionId) {
		args.push(options.sessionId, '--', prompt);
	} else {
		args.push('--', prompt);
	}

	return args;
}

export function extractCodexThreadId(events: CodexExecEvent[]): string | null {
	for (const event of events) {
		if (event.type === 'thread.started' && typeof event.thread_id === 'string' && event.thread_id) {
			return event.thread_id;
		}
	}

	return null;
}

export function extractCodexFinalText(events: CodexExecEvent[]): string {
	let finalText = '';

	for (const event of events) {
		if (
			event.type === 'item.completed' &&
			event.item?.type === 'agent_message' &&
			typeof event.item.text === 'string'
		) {
			finalText = event.item.text;
		}
	}

	return finalText;
}

function isBenignCodexStderr(line: string): boolean {
	return (
		line === 'Reading additional input from stdin...' ||
		line.includes(' WARN ') ||
		line.includes('warn codex_') ||
		line.includes('shell snapshot')
	);
}

export function extractCodexError(stderrText: string, exitCode?: number | null, finalText = ''): string | null {
	const stderrLines = stderrText
		.split('\n')
		.map((line) => line.trim())
		.filter(Boolean);

	const actionableLines = stderrLines.filter((line) => !isBenignCodexStderr(line));

	if (exitCode === 0 && finalText.trim()) {
		return actionableLines.length > 0 ? actionableLines[actionableLines.length - 1] : null;
	}

	if (actionableLines.length > 0) {
		return actionableLines[actionableLines.length - 1];
	}

	if (exitCode && exitCode !== 0) {
		return `Codex exited with code ${exitCode}`;
	}

	return null;
}

function ensureWritablePath(targetPath: string): boolean {
	try {
		fs.accessSync(targetPath, fs.constants.W_OK);
		return true;
	} catch {
		return false;
	}
}

function getCodexStateProblem(): string | null {
	const codexRoot = path.join(os.homedir(), '.codex');
	const sessionsDir = path.join(codexRoot, 'sessions');

	if (fs.existsSync(codexRoot) && !ensureWritablePath(codexRoot)) {
		return `Codex cannot write to ${codexRoot}. Fix the directory ownership or permissions.`;
	}

	if (!fs.existsSync(codexRoot) && !ensureWritablePath(os.homedir())) {
		return `Codex cannot create ${codexRoot}. Ensure your home directory is writable.`;
	}

	if (fs.existsSync(sessionsDir) && !ensureWritablePath(sessionsDir)) {
		return `Codex cannot write session files in ${sessionsDir}. Fix the directory ownership or permissions.`;
	}

	return null;
}

function findCodexPath(): string {
	const locations = [
		'/Applications/Codex.app/Contents/Resources/codex',
		`${process.env.HOME}/.local/bin/codex`,
		'/usr/local/bin/codex',
		'/opt/homebrew/bin/codex',
	];

	for (const location of locations) {
		try {
			if (fs.existsSync(location)) {
				return location;
			}
		} catch {
			// ignore
		}
	}

	try {
		return execSync('which codex', { encoding: 'utf-8' }).trim();
	} catch {
		return 'codex';
	}
}

export async function checkCodexExecStatus(codexPath?: string): Promise<CodexStatus> {
	try {
		const binaryPath = codexPath && codexPath !== 'codex'
			? codexPath
			: findCodexPath();

		const version = execSync(`"${binaryPath}" --version`, { encoding: 'utf-8' }).trim();
		const stateProblem = getCodexStateProblem();

		if (stateProblem) {
			return {
				installed: true,
				ready: false,
				version,
				problem: stateProblem,
			};
		}

		return {
			installed: true,
			ready: true,
			version,
		};
	} catch (error) {
		console.error('Codex check failed:', error);
		return {
			installed: false,
			ready: false,
			problem: 'Codex CLI not found. Install Codex or set the Codex path in settings.',
		};
	}
}
