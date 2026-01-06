import { App, PluginSettingTab, Setting } from 'obsidian';
import GenerousLedgerPlugin from './main';

export interface GenerousLedgerSettings {
	apiKey: string;
	model: 'claude-sonnet-4-20250514' | 'claude-opus-4-5-20250514';
	maxTokens: number;
	systemPrompt: string;
}

export const DEFAULT_SETTINGS: GenerousLedgerSettings = {
	apiKey: '',
	model: 'claude-sonnet-4-20250514',
	maxTokens: 4096,
	systemPrompt: 'You are a helpful AI assistant integrated into Obsidian. Provide clear, concise, and accurate responses.'
};

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

		new Setting(containerEl)
			.setName('Anthropic API Key')
			.setDesc('Enter your Anthropic API key. Get one at https://console.anthropic.com/')
			.addText(text => text
				.setPlaceholder('sk-ant-...')
				.setValue(this.plugin.settings.apiKey)
				.onChange(async (value) => {
					this.plugin.settings.apiKey = value;
					await this.plugin.saveSettings();
				})
				.inputEl.setAttribute('type', 'password'));

		new Setting(containerEl)
			.setName('Model')
			.setDesc('Choose which Claude model to use (Sonnet is faster, Opus is more capable)')
			.addDropdown(dropdown => dropdown
				.addOption('claude-sonnet-4-20250514', 'Claude Sonnet 4')
				.addOption('claude-opus-4-5-20250514', 'Claude Opus 4.5')
				.setValue(this.plugin.settings.model)
				.onChange(async (value) => {
					this.plugin.settings.model = value as GenerousLedgerSettings['model'];
					await this.plugin.saveSettings();
				}));

		new Setting(containerEl)
			.setName('Max Tokens')
			.setDesc('Maximum length of Claude\'s responses (1000-8000)')
			.addSlider(slider => slider
				.setLimits(1000, 8000, 500)
				.setValue(this.plugin.settings.maxTokens)
				.setDynamicTooltip()
				.onChange(async (value) => {
					this.plugin.settings.maxTokens = value;
					await this.plugin.saveSettings();
				}));

		new Setting(containerEl)
			.setName('System Prompt')
			.setDesc('Customize how Claude behaves (optional)')
			.addTextArea(text => text
				.setPlaceholder('You are a helpful assistant...')
				.setValue(this.plugin.settings.systemPrompt)
				.onChange(async (value) => {
					this.plugin.settings.systemPrompt = value;
					await this.plugin.saveSettings();
				}));
	}
}
