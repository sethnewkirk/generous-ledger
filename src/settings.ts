import { App, PluginSettingTab, Setting } from 'obsidian';
import GenerousLedgerPlugin from './main';

export interface GenerousLedgerSettings {
	model: string;
	maxTokens: number;
	systemPrompt: string;
	claudeCodePath: string;
	additionalFlags: string[];
}

export const DEFAULT_SETTINGS: GenerousLedgerSettings = {
	model: 'claude-sonnet-4-20250514',
	maxTokens: 4096,
	systemPrompt: 'You are a helpful AI assistant integrated into Obsidian. Provide clear, concise, and accurate responses.',
	claudeCodePath: 'claude',
	additionalFlags: [],
};

export const MODEL_OPTIONS = [
	{ value: 'claude-sonnet-4-20250514', label: 'Claude Sonnet 4 (Faster)' },
	{ value: 'claude-opus-4-20250514', label: 'Claude Opus 4 (More Capable)' },
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
			text: 'This plugin uses Claude Code CLI. Make sure you have it installed: npm i -g @anthropic-ai/claude-code',
			cls: 'setting-item-description'
		});

		new Setting(containerEl)
			.setName('Model')
			.setDesc('Choose which Claude model to use (Sonnet is faster, Opus is more capable)')
			.addDropdown(dropdown => {
				MODEL_OPTIONS.forEach(option => {
					dropdown.addOption(option.value, option.label);
				});
				return dropdown
					.setValue(this.plugin.settings.model)
					.onChange(async (value) => {
						this.plugin.settings.model = value;
						await this.plugin.saveSettings();
					});
			});

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

		containerEl.createEl('h3', { text: 'Advanced Settings' });

		new Setting(containerEl)
			.setName('Claude Code Path')
			.setDesc('Path to Claude Code CLI (leave as "claude" to use PATH)')
			.addText(text => text
				.setPlaceholder('claude')
				.setValue(this.plugin.settings.claudeCodePath)
				.onChange(async (value) => {
					this.plugin.settings.claudeCodePath = value || 'claude';
					await this.plugin.saveSettings();
				}));

		new Setting(containerEl)
			.setName('Additional CLI Flags')
			.setDesc('Extra flags to pass to Claude Code (comma-separated, for advanced users)')
			.addText(text => text
				.setPlaceholder('--flag1, --flag2')
				.setValue(this.plugin.settings.additionalFlags.join(', '))
				.onChange(async (value) => {
					this.plugin.settings.additionalFlags = value
						.split(',')
						.map(f => f.trim())
						.filter(f => f.length > 0);
					await this.plugin.saveSettings();
				}));
	}
}
