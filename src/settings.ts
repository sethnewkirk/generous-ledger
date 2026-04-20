import { App, PluginSettingTab, Setting } from 'obsidian';
import { DEFAULT_ASSISTANT_HANDLE, normalizeAssistantHandle } from './assistant-handle';
import { AssistantProvider } from './provider-types';
import type GenerousLedgerPlugin from './main';

export interface GenerousLedgerSettings {
	provider: AssistantProvider | null;
	assistantHandle: string;
	codexPath: string;
	claudePath: string;
	codexModel: string;
	claudeModel: string;
}

export const DEFAULT_SETTINGS: GenerousLedgerSettings = {
	provider: null,
	assistantHandle: DEFAULT_ASSISTANT_HANDLE,
	codexPath: 'codex',
	claudePath: 'claude',
	codexModel: '',
	claudeModel: 'claude-sonnet-4-5-20250929',
};

const PROVIDER_OPTIONS = [
	{ value: '', label: 'Select a provider' },
	{ value: 'codex', label: 'Codex' },
	{ value: 'claude', label: 'Claude' },
];

export class GenerousLedgerSettingTab extends PluginSettingTab {
	plugin: GenerousLedgerPlugin;

	constructor(app: App, plugin: GenerousLedgerPlugin) {
		super(app, plugin);
		this.plugin = plugin;
	}

	display(): void {
		const { containerEl } = this;
		containerEl.empty();

		containerEl.createEl('h2', { text: 'Generous Ledger Settings' });

		containerEl.createEl('p', {
			text: 'Configure Steward to run through either Codex or Claude.',
			cls: 'setting-item-description'
		});

		new Setting(containerEl)
			.setName('Provider')
			.setDesc('Choose which runtime powers Steward for note interactions and onboarding.')
			.addDropdown(dropdown => {
				PROVIDER_OPTIONS.forEach(option => {
					dropdown.addOption(option.value, option.label);
				});
				return dropdown
					.setValue(this.plugin.settings.provider ?? '')
					.onChange(async (value) => {
						this.plugin.settings.provider = value === '' ? null : value as AssistantProvider;
						await this.plugin.saveSettings();
					});
			});

		new Setting(containerEl)
			.setName('Assistant Handle')
			.setDesc('Primary mention trigger. Steward is the default. Legacy @Claude and @Codex remain supported.')
			.addText(text => text
				.setPlaceholder(DEFAULT_ASSISTANT_HANDLE)
				.setValue(this.plugin.settings.assistantHandle)
				.onChange(async (value) => {
					this.plugin.settings.assistantHandle = normalizeAssistantHandle(value);
					await this.plugin.saveSettings();
				}));

		new Setting(containerEl)
			.setName('Codex Path')
			.setDesc('Path to the Codex CLI binary. Leave as "codex" to use PATH.')
			.addText(text => text
				.setPlaceholder('codex')
				.setValue(this.plugin.settings.codexPath)
				.onChange(async (value) => {
					this.plugin.settings.codexPath = value || 'codex';
					await this.plugin.saveSettings();
				}));

		new Setting(containerEl)
			.setName('Codex Model')
			.setDesc('Optional Codex model override. Leave blank to use the CLI default.')
			.addText(text => text
				.setPlaceholder('gpt-5.4')
				.setValue(this.plugin.settings.codexModel)
				.onChange(async (value) => {
					this.plugin.settings.codexModel = value.trim();
					await this.plugin.saveSettings();
				}));

		new Setting(containerEl)
			.setName('Claude Path')
			.setDesc('Path to the Claude CLI binary. Leave as "claude" to use PATH.')
			.addText(text => text
				.setPlaceholder('claude')
				.setValue(this.plugin.settings.claudePath)
				.onChange(async (value) => {
					this.plugin.settings.claudePath = value || 'claude';
					await this.plugin.saveSettings();
				}));

		new Setting(containerEl)
			.setName('Claude Model')
			.setDesc('Optional Claude model override. Leave blank to use the CLI default.')
			.addText(text => text
				.setPlaceholder('claude-sonnet-4-5-20250929')
				.setValue(this.plugin.settings.claudeModel)
				.onChange(async (value) => {
					this.plugin.settings.claudeModel = value.trim();
					await this.plugin.saveSettings();
				}));
	}
}
