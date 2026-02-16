import { spawn, ChildProcess, execSync } from 'child_process';
import { EventEmitter } from 'events';

export interface ClaudeCodeOptions {
	cwd: string;
	sessionId?: string;
	model?: string;
	claudeCodePath?: string;
	timeoutMs?: number;
}

const DEFAULT_TIMEOUT = 15 * 60 * 1000;

export class ClaudeCodeProcess extends EventEmitter {
	private process: ChildProcess | null = null;

	async query(prompt: string, options: ClaudeCodeOptions): Promise<void> {
		const args = [
			'-p', prompt,
			'--output-format', 'stream-json',
			'--verbose',
			'--include-partial-messages',
			'--permission-mode', 'bypassPermissions',
		];

		if (options.sessionId) {
			args.push('--resume', options.sessionId);
		}

		if (options.model) {
			args.push('--model', options.model);
		}

		const claudePath = options.claudeCodePath && options.claudeCodePath !== 'claude'
			? options.claudeCodePath
			: findClaudePath();

		this.process = spawn(claudePath, args, {
			cwd: options.cwd,
			env: {
				...process.env,
				PATH: `${process.env.PATH}:/usr/local/bin:/opt/homebrew/bin:${process.env.HOME}/.local/bin`
			},
			stdio: ['pipe', 'pipe', 'pipe']
		});

		this.process.stdin?.end();

		let buffer = '';

		this.process.stdout?.on('data', (chunk: Buffer) => {
			const data = chunk.toString();
			buffer += data;
			const lines = buffer.split('\n');
			buffer = lines.pop() || '';

			for (const line of lines) {
				if (line.trim()) {
					try {
						const message = JSON.parse(line);
						this.emit('message', message);
					} catch (e) {
						console.error('Failed to parse JSON:', line.substring(0, 100), e);
					}
				}
			}
		});

		this.process.stderr?.on('data', (chunk: Buffer) => {
			console.error('[GL] stderr:', chunk.toString());
		});

		this.process.on('close', (code) => {
			console.log('[GL] process exited with code:', code);
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

function findClaudePath(): string {
	const locations = [
		`${process.env.HOME}/.local/bin/claude`,
		'/usr/local/bin/claude',
		'/opt/homebrew/bin/claude',
	];

	for (const loc of locations) {
		try {
			const fs = require('fs');
			if (fs.existsSync(loc)) {
				return loc;
			}
		} catch { /* skip */ }
	}

	try {
		return execSync('which claude', { encoding: 'utf-8' }).trim();
	} catch {
		return 'claude';
	}
}

export async function checkClaudeCodeVersion(claudeCodePath?: string): Promise<{
	installed: boolean;
	version?: string;
	compatible: boolean;
	authenticated?: boolean;
}> {
	try {
		const claudePath = claudeCodePath && claudeCodePath !== 'claude'
			? claudeCodePath
			: findClaudePath();

		const versionOutput = execSync(`"${claudePath}" --version`, { encoding: 'utf-8' });
		const version = versionOutput.match(/\d+\.\d+\.\d+/)?.[0];

		if (!version) {
			return { installed: true, compatible: false };
		}

		try {
			execSync(`"${claudePath}" -p "ping" --max-turns 1`, { encoding: 'utf-8', timeout: 10000 });
			return { installed: true, version, compatible: true, authenticated: true };
		} catch {
			return { installed: true, version, compatible: true, authenticated: false };
		}
	} catch (error) {
		console.error('Claude Code check failed:', error);
		return { installed: false, compatible: false };
	}
}
