import { spawn, ChildProcess, execSync } from 'child_process';
import { EventEmitter } from 'events';

export interface ClaudeCodeOptions {
	workingDirectory: string;
	sessionId?: string;
	systemPrompt?: string;
	model?: string;
	timeoutMs?: number;
}

const REQUIRED_CLI_VERSION = '1.0.0';
const DEFAULT_TIMEOUT = 15 * 60 * 1000; // 15 minutes

export class ClaudeCodeProcess extends EventEmitter {
	private process: ChildProcess | null = null;

	async query(prompt: string, options: ClaudeCodeOptions): Promise<void> {
		const args = [
			'-p', prompt,
			'--output-format', 'stream-json',
			'--verbose',  // Required for stream-json with -p
			'--include-partial-messages',  // Get character-by-character streaming
			'--permission-mode', 'bypassPermissions',
		];

		if (options.sessionId) {
			args.push('--resume', options.sessionId);
		}

		if (options.systemPrompt) {
			args.push('--system-prompt', options.systemPrompt);
		}

		if (options.model) {
			args.push('--model', options.model);
		}

		console.log('Spawning Claude Code with args:', args);
		console.log('Working directory:', options.workingDirectory);

		// Find claude CLI
		const claudePath = findClaudePath();
		console.log('Using Claude path:', claudePath);

		this.process = spawn(claudePath, args, {
			cwd: options.workingDirectory,
			env: {
				...process.env,
				PATH: `${process.env.PATH}:/usr/local/bin:/opt/homebrew/bin:${process.env.HOME}/.local/bin`
			},
			stdio: ['pipe', 'pipe', 'pipe']  // Explicitly pipe stdin, stdout, stderr
		});

		// Close stdin immediately since we're using -p mode
		this.process.stdin?.end();
		console.log('Claude Code process spawned, stdin closed');

		let buffer = '';

		this.process.stdout?.on('data', (chunk: Buffer) => {
			const data = chunk.toString();
			console.log('Claude Code stdout chunk received:', data.substring(0, 200));
			buffer += data;
			const lines = buffer.split('\n');
			buffer = lines.pop() || '';

			for (const line of lines) {
				if (line.trim()) {
					try {
						const message = JSON.parse(line);
						console.log('Parsed message type:', message.type);
						this.emit('message', message);
					} catch (e) {
						console.error('Failed to parse JSON:', line.substring(0, 100), e);
					}
				}
			}
		});

		this.process.stderr?.on('data', (chunk: Buffer) => {
			console.error('Claude Code stderr:', chunk.toString());
		});

		this.process.on('close', (code) => {
			console.log('Claude Code process closed with code:', code);
			this.emit('close', code);
		});

		this.process.on('error', (error) => {
			console.error('Claude Code process error:', error);
			this.emit('error', error);
		});

		const timeout = options.timeoutMs || DEFAULT_TIMEOUT;
		const timeoutId = setTimeout(() => {
			this.abort();
			this.emit('error', new Error(`Request timed out after ${timeout / 60000} minutes`));
		}, timeout);

		this.process.on('close', () => clearTimeout(timeoutId));
	}

	abort(): void {
		this.process?.kill('SIGTERM');
	}
}

// Shared function to find Claude CLI path
function findClaudePath(): string {
	const locations = [
		`${process.env.HOME}/.local/bin/claude`,
		'/usr/local/bin/claude',
		'/opt/homebrew/bin/claude',
	];

	// Try locations directly
	for (const path of locations) {
		try {
			const fs = require('fs');
			if (fs.existsSync(path)) {
				return path;
			}
		} catch {}
	}

	// Fall back to 'which' command
	try {
		return execSync('which claude', { encoding: 'utf-8' }).trim();
	} catch {
		return 'claude';
	}
}

export async function checkClaudeCodeVersion(): Promise<{
	installed: boolean;
	version?: string;
	compatible: boolean;
	authenticated?: boolean;
}> {
	try {
		const claudePath = findClaudePath();
		console.log('Checking Claude Code at:', claudePath);

		const versionOutput = execSync(`"${claudePath}" --version`, { encoding: 'utf-8' });
		const version = versionOutput.match(/\d+\.\d+\.\d+/)?.[0];

		if (!version) {
			return { installed: true, compatible: false };
		}

		try {
			execSync(`"${claudePath}" -p "ping" --max-turns 1`, { encoding: 'utf-8', timeout: 5000 });
			return { installed: true, version, compatible: true, authenticated: true };
		} catch {
			return { installed: true, version, compatible: true, authenticated: false };
		}
	} catch (error) {
		console.error('Claude Code check failed:', error);
		return { installed: false, compatible: false };
	}
}
