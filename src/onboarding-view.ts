import { ItemView, Notice, WorkspaceLeaf } from 'obsidian';
import type GenerousLedgerPlugin from './main';
import type { StewardThread, StewardTurn } from './chat-types';

export const STEWARD_ONBOARDING_VIEW_TYPE = 'generous-ledger-onboarding';

export class StewardOnboardingView extends ItemView {
	private plugin: GenerousLedgerPlugin;
	private thread: StewardThread | null = null;
	private messagesEl!: HTMLElement;
	private composerEl!: HTMLTextAreaElement;
	private sendButtonEl!: HTMLButtonElement;
	private statusEl!: HTMLElement;
	private streamingAssistantEl: HTMLElement | null = null;

	constructor(leaf: WorkspaceLeaf, plugin: GenerousLedgerPlugin) {
		super(leaf);
		this.plugin = plugin;
	}

	getViewType(): string {
		return STEWARD_ONBOARDING_VIEW_TYPE;
	}

	getDisplayText(): string {
		return 'Steward Setup';
	}

	getIcon(): string {
		return 'clipboard-list';
	}

	async onOpen(): Promise<void> {
		const container = this.containerEl.children[1] as HTMLElement;
		container.empty();
		container.addClass('gl-setup');

		const header = container.createDiv({ cls: 'gl-setup__header' });
		header.createEl('h2', { text: 'Steward Setup' });
		header.createEl('p', {
			text: 'This guided interview helps Steward learn your life, commitments, and current state.',
		});

		const controlRow = container.createDiv({ cls: 'gl-setup__controls' });
		const restartButton = controlRow.createEl('button', { text: 'Restart onboarding' });
		restartButton.addEventListener('click', async () => {
			const thread = await this.plugin.restartOnboarding();
			this.setThread(thread);
		});

		const redoButton = controlRow.createEl('button', { text: 'Redo last answer' });
		redoButton.addEventListener('click', async () => {
			const thread = await this.plugin.redoOnboarding();
			this.setThread(thread);
			if (thread.turns.length === 0 && thread.status !== 'completed') {
				await this.sendSystemOpen();
			}
		});

		const openChatButton = controlRow.createEl('button', { text: 'Open Steward Chat' });
		openChatButton.addEventListener('click', async () => {
			await this.plugin.openStewardChat();
		});

		this.messagesEl = container.createDiv({ cls: 'gl-setup__messages' });
		const composerWrap = container.createDiv({ cls: 'gl-setup__composer-wrap' });
		this.statusEl = composerWrap.createDiv({ cls: 'gl-setup__status' });
		this.composerEl = composerWrap.createEl('textarea', {
			cls: 'gl-setup__composer',
			attr: {
				rows: '3',
				placeholder: 'Answer Steward...',
			},
		});
		this.composerEl.addEventListener('keydown', async (event: KeyboardEvent) => {
			if (event.key === 'Enter' && !event.shiftKey) {
				event.preventDefault();
				await this.sendComposerText();
			}
		});

		this.sendButtonEl = composerWrap.createEl('button', { text: 'Send', cls: 'mod-cta' });
		this.sendButtonEl.addEventListener('click', async () => {
			await this.sendComposerText();
		});

		try {
			const thread = await this.plugin.getOrCreateOnboardingThread();
			this.setThread(thread);

			if (thread.turns.length === 0) {
				await this.sendSystemOpen();
			}
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Choose a provider before onboarding.';
			this.messagesEl.createDiv({ cls: 'gl-setup__empty', text: message });
			this.composerEl.disabled = true;
			this.sendButtonEl.disabled = true;
		}
	}

	setThread(thread: StewardThread): void {
		this.thread = thread;
		this.render();
	}

	updateStreamingText(text: string): void {
		if (!this.streamingAssistantEl) {
			this.streamingAssistantEl = this.createMessageCard('assistant', '');
		}
		this.streamingAssistantEl.querySelector('.gl-setup__message-body')!.textContent = text;
		this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
	}

	clearStreamingText(): void {
		if (this.streamingAssistantEl) {
			this.streamingAssistantEl.remove();
			this.streamingAssistantEl = null;
		}
	}

	setBusy(busy: boolean, statusText = ''): void {
		const disabled = busy || this.thread?.status === 'completed';
		this.composerEl.disabled = disabled;
		this.sendButtonEl.disabled = disabled;
		this.statusEl.textContent = statusText;
	}

	private async sendSystemOpen(): Promise<void> {
		if (!this.thread) {
			return;
		}
		this.setBusy(true, 'Starting onboarding...');
		try {
			const updated = await this.plugin.sendOnboardingMessage(this.thread, null, {
				onAssistantText: (text) => this.updateStreamingText(text),
			});
			this.clearStreamingText();
			this.setThread(updated);
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Unknown error';
			new Notice(`Onboarding error: ${message}`, 10000);
		} finally {
			this.setBusy(false);
		}
	}

	private async sendComposerText(): Promise<void> {
		const text = this.composerEl.value.trim();
		if (!text || !this.thread) {
			return;
		}

		this.composerEl.value = '';
		this.setBusy(true, 'Steward is thinking...');

		try {
			const updated = await this.plugin.sendOnboardingMessage(this.thread, text, {
				onAssistantText: (nextText) => this.updateStreamingText(nextText),
			});
			this.clearStreamingText();
			this.setThread(updated);
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Unknown error';
			new Notice(`Onboarding error: ${message}`, 10000);
		} finally {
			this.setBusy(false);
		}
	}

	private render(): void {
		this.messagesEl.empty();
		if (!this.thread) {
			this.messagesEl.createDiv({ cls: 'gl-setup__empty', text: 'Choose a provider before onboarding.' });
			return;
		}

		for (const turn of this.thread.turns) {
			this.createMessageCard(turn.role, turn.text);
		}

		this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
		if (this.thread.status === 'completed') {
			this.statusEl.textContent = 'Onboarding complete. You can move into Steward Chat now.';
			this.composerEl.disabled = true;
			this.sendButtonEl.disabled = true;
		}
	}

	private createMessageCard(role: StewardTurn['role'], text: string): HTMLElement {
		const card = this.messagesEl.createDiv({ cls: `gl-setup__message gl-setup__message--${role}` });
		card.createDiv({ cls: 'gl-setup__message-role', text: role === 'assistant' ? 'Steward' : role === 'user' ? 'You' : 'System' });
		card.createDiv({ cls: 'gl-setup__message-body', text });
		return card;
	}
}
