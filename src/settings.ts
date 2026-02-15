import { App, PluginSettingTab, Setting } from 'obsidian';
import type GenerousLedgerPlugin from './main';

export interface GenerousLedgerSettings {
	model: string;
	claudeCodePath: string;
}

export const DEFAULT_SETTINGS: GenerousLedgerSettings = {
	model: 'claude-sonnet-4-5-20250929',
	claudeCodePath: 'claude',
};

const MODEL_OPTIONS = [
	{ value: 'claude-sonnet-4-5-20250929', label: 'Claude Sonnet 4.5 (Faster)' },
	{ value: 'claude-opus-4-6-20250612', label: 'Claude Opus 4.6 (More Capable)' },
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
			text: 'Uses Claude Code CLI. Install with: npm i -g @anthropic-ai/claude-code',
			cls: 'setting-item-description'
		});

		new Setting(containerEl)
			.setName('Model')
			.setDesc('Sonnet 4.5 is faster; Opus 4.6 is more capable.')
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
			.setName('Claude Code path')
			.setDesc('Path to Claude Code CLI binary. Leave as "claude" to use PATH.')
			.addText(text => text
				.setPlaceholder('claude')
				.setValue(this.plugin.settings.claudeCodePath)
				.onChange(async (value) => {
					this.plugin.settings.claudeCodePath = value || 'claude';
					await this.plugin.saveSettings();
				}));
	}
}
