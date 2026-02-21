import { ItemView, WorkspaceLeaf } from 'obsidian';
import type GenerousLedgerPlugin from './main';
import type { ConversationEntry } from './terminal-session';

export const TERMINAL_VIEW_TYPE = 'generous-ledger-terminal';

export class OnboardingTerminalView extends ItemView {
	plugin: GenerousLedgerPlugin;

	private screenEl: HTMLElement;
	private contentEl_: HTMLElement;
	private inputEl: HTMLInputElement;
	private spinnerEl: HTMLElement;
	private cursorEl: HTMLElement;
	private systemEl: HTMLElement;

	private pendingText = '';
	private currentLineEl: HTMLElement | null = null;
	private typewriterRunning = false;
	private typewriterTimer: number | null = null;
	private isTyping = false;
	private inputActive = false;
	private onSubmit: ((text: string) => void) | null = null;
	private pendingFinalize = false;
	private escapeHandler: ((e: KeyboardEvent) => void) | null = null;

	private static readonly CHAR_DELAY_MS = 18;

	constructor(leaf: WorkspaceLeaf, plugin: GenerousLedgerPlugin) {
		super(leaf);
		this.plugin = plugin;
	}

	getViewType(): string {
		return TERMINAL_VIEW_TYPE;
	}

	getDisplayText(): string {
		return 'Steward Terminal';
	}

	getIcon(): string {
		return 'terminal';
	}

	async onOpen(): Promise<void> {
		const container = this.containerEl.children[1] as HTMLElement;
		container.empty();
		container.addClass('gl-terminal');

		this.screenEl = container.createDiv({ cls: 'gl-terminal__screen' });

		// System messages area (top, for boot sequence)
		this.systemEl = this.screenEl.createDiv({ cls: 'gl-terminal__system' });

		// Centered content area — holds the current question OR the user's answer
		this.contentEl_ = this.screenEl.createDiv({ cls: 'gl-terminal__content' });

		// Hidden input element — captures keystrokes
		this.inputEl = this.screenEl.createEl('input', {
			cls: 'gl-terminal__hidden-input',
			attr: { type: 'text', spellcheck: 'false', autocomplete: 'off' },
		});

		// Loading spinner (hidden by default)
		this.spinnerEl = this.screenEl.createDiv({ cls: 'gl-terminal__spinner gl-spinner--hidden' });
		this.spinnerEl.createSpan({ cls: 'gl-terminal__spinner-char', text: '/' });

		// Blinking cursor (used during typewriter)
		this.cursorEl = container.createSpan({ cls: 'gl-terminal__cursor gl-cursor--hidden' });

		// When user starts typing, transition from question to answer mode
		this.inputEl.addEventListener('input', () => {
			if (!this.inputActive || this.isTyping) return;
			this.showAnswerMode();
		});

		this.inputEl.addEventListener('keydown', (e: KeyboardEvent) => {
			if (e.key === 'Enter' && !e.shiftKey) {
				e.preventDefault();
				const text = this.inputEl.value.trim();
				if (text && this.onSubmit && !this.isTyping) {
					this.inputEl.value = '';
					this.onSubmit(text);
				}
			}
		});

		// Click anywhere on screen focuses input
		this.screenEl.addEventListener('click', () => {
			if (this.inputActive) this.inputEl.focus();
		});

		this.setInputEnabled(false);
	}

	async onClose(): Promise<void> {
		this.exitFullscreen();
		if (this.typewriterTimer !== null) {
			window.clearTimeout(this.typewriterTimer);
			this.typewriterTimer = null;
		}
		this.typewriterRunning = false;
		this.pendingText = '';
	}

	// --- Public API ---

	enterFullscreen(): void {
		document.body.addClass('gl-terminal-fullscreen');
		this.escapeHandler = (e: KeyboardEvent) => {
			if (e.key === 'Escape') {
				this.exitFullscreen();
			}
		};
		document.addEventListener('keydown', this.escapeHandler);
		this.inputEl?.focus();
	}

	exitFullscreen(): void {
		document.body.removeClass('gl-terminal-fullscreen');
		if (this.escapeHandler) {
			document.removeEventListener('keydown', this.escapeHandler);
			this.escapeHandler = null;
		}
	}

	printSteward(chunk: string): void {
		// Hide spinner when steward text starts arriving
		this.spinnerEl.addClass('gl-spinner--hidden');
		this.contentEl_.removeClass('gl-content--answer');
		this.contentEl_.addClass('gl-content--question');

		this.pendingText += chunk;
		if (!this.typewriterRunning) {
			this.isTyping = true;
			this.showCursor();
			this.drainTypewriter();
		}
	}

	finalizeStewardTurn(): void {
		// If typewriter is still draining, let it finish naturally
		if (this.typewriterRunning || this.pendingText.length > 0) {
			this.pendingFinalize = true;
			return;
		}

		this.completeStewardTurn();
	}

	private completeStewardTurn(): void {
		this.pendingFinalize = false;
		this.typewriterRunning = false;
		this.pendingText = '';
		this.currentLineEl = null;
		this.isTyping = false;
		this.hideCursor();
		this.setInputEnabled(true);
		this.inputEl.focus();
	}

	printUser(text: string): void {
		// Clear content and show loading spinner
		this.contentEl_.empty();
		this.contentEl_.removeClass('gl-content--question', 'gl-content--answer');
		this.showSpinner();
		this.inputActive = false;
	}

	printSystem(text: string): void {
		const line = document.createElement('div');
		line.addClass('gl-terminal__line');
		line.dataset.role = 'system';
		line.textContent = text;
		this.systemEl.appendChild(line);
	}

	showSpinner(): void {
		this.spinnerEl.removeClass('gl-spinner--hidden');
	}

	setInputEnabled(enabled: boolean): void {
		this.inputEl.disabled = !enabled;
		this.inputActive = enabled;
		if (enabled) {
			this.inputEl.value = '';
		}
	}

	setSubmitHandler(fn: (text: string) => void): void {
		this.onSubmit = fn;
	}

	clearDisplay(): void {
		this.systemEl.empty();
		this.contentEl_.empty();
		this.contentEl_.removeClass('gl-content--question', 'gl-content--answer');
		this.spinnerEl.addClass('gl-spinner--hidden');
		this.hideCursor();
		this.pendingText = '';
		this.currentLineEl = null;
		this.isTyping = false;
		if (this.typewriterTimer !== null) {
			window.clearTimeout(this.typewriterTimer);
			this.typewriterTimer = null;
		}
		this.typewriterRunning = false;
	}

	showQuestion(text: string): void {
		this.contentEl_.empty();
		this.contentEl_.addClass('gl-content--question');
		this.contentEl_.removeClass('gl-content--answer');
		const lines = text.split('\n');
		for (const lineText of lines) {
			if (lineText.trim()) {
				const line = this.createLine('steward');
				line.textContent = lineText;
				this.contentEl_.appendChild(line);
			}
		}
		this.inputEl.value = '';
		this.inputEl.focus();
	}

	replayLog(entries: ConversationEntry[]): void {
		// For resume, show only the last steward message centered
		for (let i = entries.length - 1; i >= 0; i--) {
			if (entries[i].role === 'steward') {
				this.contentEl_.empty();
				this.contentEl_.addClass('gl-content--question');
				const lines = entries[i].text.split('\n');
				for (const lineText of lines) {
					if (lineText.trim()) {
						const line = this.createLine('steward');
						line.textContent = lineText;
						this.contentEl_.appendChild(line);
					}
				}
				break;
			}
		}
	}

	// --- Private helpers ---

	private showAnswerMode(): void {
		if (this.contentEl_.hasClass('gl-content--answer')) return;

		// Fade out question, show answer input area
		this.contentEl_.empty();
		this.contentEl_.removeClass('gl-content--question');
		this.contentEl_.addClass('gl-content--answer');

		// Create a visible echo of what the user is typing
		const echoEl = document.createElement('div');
		echoEl.addClass('gl-terminal__echo');
		this.contentEl_.appendChild(echoEl);

		// Mirror input to echo element
		const updateEcho = () => {
			echoEl.textContent = '> ' + this.inputEl.value;
		};
		this.inputEl.addEventListener('input', updateEcho);
		updateEcho();
	}

	private createLine(role: 'steward' | 'user' | 'system'): HTMLElement {
		const line = document.createElement('div');
		line.addClass('gl-terminal__line');
		line.dataset.role = role;
		return line;
	}

	private drainTypewriter(): void {
		this.typewriterRunning = true;

		const tick = () => {
			if (this.pendingText.length === 0) {
				this.typewriterRunning = false;
				if (this.pendingFinalize) {
					this.completeStewardTurn();
				}
				return;
			}

			const char = this.pendingText[0];
			this.pendingText = this.pendingText.slice(1);

			if (char === '\n') {
				this.currentLineEl = null;
			} else {
				if (!this.currentLineEl) {
					this.currentLineEl = this.createLine('steward');
					this.contentEl_.appendChild(this.currentLineEl);
				}
				this.currentLineEl.textContent += char;
			}

			this.positionCursor();
			this.typewriterTimer = window.setTimeout(tick, OnboardingTerminalView.CHAR_DELAY_MS);
		};

		tick();
	}

	private flushPendingText(): void {
		for (const char of this.pendingText) {
			if (char === '\n') {
				this.currentLineEl = null;
			} else {
				if (!this.currentLineEl) {
					this.currentLineEl = this.createLine('steward');
					this.contentEl_.appendChild(this.currentLineEl);
				}
				this.currentLineEl.textContent += char;
			}
		}
	}

	private showCursor(): void {
		this.cursorEl.removeClass('gl-cursor--hidden');
		this.positionCursor();
	}

	private hideCursor(): void {
		this.cursorEl.addClass('gl-cursor--hidden');
	}

	private positionCursor(): void {
		if (this.currentLineEl) {
			this.currentLineEl.appendChild(this.cursorEl);
		}
	}
}
