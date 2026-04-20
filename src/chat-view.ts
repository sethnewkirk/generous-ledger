import { ItemView, Notice, WorkspaceLeaf } from 'obsidian';
import type GenerousLedgerPlugin from './main';
import type { ActivitySummary, NoteIntent, NoteWritebackAction, StewardThread, StewardTurn } from './chat-types';
import { getProviderDisplayName } from './provider-types';

export const STEWARD_CHAT_VIEW_TYPE = 'generous-ledger-chat';

export class StewardChatView extends ItemView {
	private plugin: GenerousLedgerPlugin;
	private thread: StewardThread | null = null;
	private rootEl!: HTMLElement;
	private threadSelectEl!: HTMLSelectElement;
	private providerEl!: HTMLElement;
	private contextEl!: HTMLElement;
	private messagesEl!: HTMLElement;
	private composerEl!: HTMLTextAreaElement;
	private sendButtonEl!: HTMLButtonElement;
	private statusEl!: HTMLElement;
	private streamingAssistantEl: HTMLElement | null = null;
	private busy = false;

	constructor(leaf: WorkspaceLeaf, plugin: GenerousLedgerPlugin) {
		super(leaf);
		this.plugin = plugin;
	}

	getViewType(): string {
		return STEWARD_CHAT_VIEW_TYPE;
	}

	getDisplayText(): string {
		return 'Steward Chat';
	}

	getIcon(): string {
		return 'messages-square';
	}

	async onOpen(): Promise<void> {
		const container = this.containerEl.children[1] as HTMLElement;
		container.empty();
		container.addClass('gl-chat');
		this.rootEl = container;

		const header = container.createDiv({ cls: 'gl-chat__header' });
		const titleGroup = header.createDiv({ cls: 'gl-chat__title-group' });
		titleGroup.createEl('h2', { text: 'Steward Chat' });
		this.providerEl = titleGroup.createDiv({ cls: 'gl-chat__provider' });

		const controls = header.createDiv({ cls: 'gl-chat__controls' });
		this.threadSelectEl = controls.createEl('select', { cls: 'gl-chat__thread-select' });
		this.threadSelectEl.addEventListener('change', async () => {
			const threadId = this.threadSelectEl.value;
			if (!threadId) {
				return;
			}
			const thread = await this.plugin.loadChatThread(threadId);
			if (thread) {
				this.setThread(thread);
			}
		});

		const newThreadButton = controls.createEl('button', { text: 'New chat', cls: 'mod-cta' });
		newThreadButton.addEventListener('click', async () => {
			const thread = await this.plugin.createFreshChatThread();
			this.setThread(thread);
			await this.refreshThreadOptions();
		});

		this.contextEl = container.createDiv({ cls: 'gl-chat__context' });
		this.messagesEl = container.createDiv({ cls: 'gl-chat__messages' });

		const composerWrap = container.createDiv({ cls: 'gl-chat__composer-wrap' });
		this.statusEl = composerWrap.createDiv({ cls: 'gl-chat__status' });
		const composerRow = composerWrap.createDiv({ cls: 'gl-chat__composer-row' });
		this.composerEl = composerRow.createEl('textarea', {
			cls: 'gl-chat__composer',
			attr: {
				rows: '3',
				placeholder: 'Talk to Steward...',
			},
		});
		this.composerEl.addEventListener('keydown', async (event: KeyboardEvent) => {
			if (event.key === 'Enter' && !event.shiftKey) {
				event.preventDefault();
				await this.sendComposerText();
			}
		});

		this.sendButtonEl = composerRow.createEl('button', { text: 'Send', cls: 'mod-cta' });
		this.sendButtonEl.addEventListener('click', async () => {
			await this.sendComposerText();
		});

		await this.refreshThreadOptions();
		const thread = await this.plugin.getDefaultChatThread();
		if (thread) {
			this.setThread(thread);
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
		this.streamingAssistantEl.querySelector('.gl-chat__message-body')!.textContent = text;
		this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
	}

	clearStreamingText(): void {
		if (this.streamingAssistantEl) {
			this.streamingAssistantEl.remove();
			this.streamingAssistantEl = null;
		}
	}

	setBusy(busy: boolean, statusText = ''): void {
		this.busy = busy;
		this.composerEl.disabled = busy;
		this.sendButtonEl.disabled = busy;
		this.statusEl.textContent = statusText;
	}

	async submitMessage(text: string, noteIntent?: NoteIntent | null): Promise<void> {
		if (!text.trim()) {
			return;
		}

		const thread = this.thread ?? await this.plugin.getDefaultChatThread();
		if (!thread) {
			new Notice('Choose a provider before sending a message.');
			return;
		}

		this.setBusy(true, 'Steward is thinking...');
		this.clearStreamingText();

		try {
			const updatedThread = await this.plugin.sendChatMessage(thread, text, noteIntent ?? null, {
				onAssistantText: (nextText) => this.updateStreamingText(nextText),
			});
			this.clearStreamingText();
			this.setThread(updatedThread);
			await this.refreshThreadOptions();
		} catch (error) {
			this.clearStreamingText();
			const message = error instanceof Error ? error.message : 'Unknown error';
			new Notice(`Steward chat error: ${message}`, 10000);
		} finally {
			this.setBusy(false, '');
		}
	}

	private async sendComposerText(): Promise<void> {
		const text = this.composerEl.value.trim();
		if (!text) {
			return;
		}

		this.composerEl.value = '';
		await this.submitMessage(text);
	}

	private async refreshThreadOptions(): Promise<void> {
		const summaries = await this.plugin.listChatThreads();
		const currentValue = this.thread?.threadId ?? this.threadSelectEl.value;
		this.threadSelectEl.innerHTML = '';

		for (const summary of summaries) {
			const option = this.threadSelectEl.createEl('option', {
				value: summary.threadId,
				text: summary.title,
			});
			if (summary.threadId === currentValue) {
				option.selected = true;
			}
		}
	}

	private render(): void {
		this.renderProvider();
		this.renderContext();
		this.renderMessages();
	}

	private renderProvider(): void {
		const provider = this.plugin.getActiveProvider();
		this.providerEl.textContent = provider
			? `Provider: ${getProviderDisplayName(provider)}`
			: 'Provider not configured';
	}

	private renderContext(): void {
		this.contextEl.empty();
		if (!this.thread?.sourceContext) {
			this.contextEl.createSpan({ text: 'No note context attached.' });
			return;
		}

		const context = this.thread.sourceContext;
		const start = context.anchorStart.line + 1;
		const end = context.anchorEnd.line + 1;
		const lineText = start === end ? `line ${start}` : `lines ${start}-${end}`;
		this.contextEl.createSpan({
			text: `Attached note: ${context.notePath} (${lineText}, via ${context.triggerSource})`,
		});
	}

	private renderMessages(): void {
		this.messagesEl.empty();
		if (!this.thread) {
			this.messagesEl.createDiv({ cls: 'gl-chat__empty', text: 'Open a provider-backed chat to begin.' });
			return;
		}

		for (const turn of this.thread.turns) {
			const card = this.createMessageCard(turn.role, turn.text);
			if (turn.role === 'assistant' && turn.activitySummary) {
				card.appendChild(this.renderActivitySummary(turn, turn.activitySummary));
			}
		}

		this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
	}

	private createMessageCard(role: StewardTurn['role'], text: string): HTMLElement {
		const card = this.messagesEl.createDiv({ cls: `gl-chat__message gl-chat__message--${role}` });
		card.createDiv({ cls: 'gl-chat__message-role', text: role === 'assistant' ? 'Steward' : role === 'user' ? 'You' : 'System' });
		card.createDiv({ cls: 'gl-chat__message-body', text });
		return card;
	}

	private renderActivitySummary(turn: StewardTurn, summary: ActivitySummary): HTMLElement {
		const wrap = document.createElement('div');
		wrap.addClass('gl-chat__activity');

		if (summary.attachedContext) {
			wrap.createDiv({
				cls: 'gl-chat__activity-line',
				text: `Context: ${summary.attachedContext.notePath} (lines ${summary.attachedContext.lineRange})`,
			});
		}

		if (summary.profileUpdates.length > 0) {
			wrap.createDiv({
				cls: 'gl-chat__activity-line',
				text: `Profile updated: ${summary.profileUpdates.join(', ')}`,
			});
		}

		if (summary.memoryUpdates.length > 0) {
			wrap.createDiv({
				cls: 'gl-chat__activity-line',
				text: `Memory updated: ${summary.memoryUpdates.join(', ')}`,
			});
		}

		if (summary.otherUpdates.length > 0) {
			wrap.createDiv({
				cls: 'gl-chat__activity-line',
				text: `Other changes: ${summary.otherUpdates.join(', ')}`,
			});
		}

		if (summary.currentNoteViolation) {
			wrap.createDiv({
				cls: 'gl-chat__activity-line gl-chat__activity-line--warning',
				text: 'Warning: the source note changed during this turn.',
			});
		}

		if (turn.noteIntent && summary.availableActions.length > 0) {
			const actionsRow = wrap.createDiv({ cls: 'gl-chat__actions' });
			for (const action of summary.availableActions) {
				const label = getActionLabel(action);
				const button = actionsRow.createEl('button', { text: label });
				button.addEventListener('click', async () => {
					await this.plugin.applyNoteWriteback(turn, action);
				});
			}
		}

		return wrap;
	}
}

function getActionLabel(action: NoteWritebackAction): string {
	switch (action) {
		case 'insert-callout':
			return 'Insert as callout';
		case 'replace-selection':
			return 'Replace selection';
		case 'create-linked-note':
			return 'Create linked note';
	}
}
