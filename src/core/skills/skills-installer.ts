import { App, requestUrl } from 'obsidian';

const SKILLS_REPO = 'kepano/obsidian-skills';
const SKILLS_BRANCH = 'main';
const SKILLS_TO_INSTALL = ['obsidian-markdown', 'json-canvas', 'obsidian-bases'];

export class SkillsInstaller {
	constructor(private app: App) {}

	async ensureSkillsInstalled(): Promise<void> {
		const vaultPath = (this.app.vault.adapter as any).basePath;
		const skillsDir = `${vaultPath}/.claude/skills`;

		for (const skill of SKILLS_TO_INSTALL) {
			const skillPath = `${skillsDir}/${skill}/SKILL.md`;
			if (!await this.app.vault.adapter.exists(skillPath)) {
				await this.installSkill(skill, skillsDir);
			}
		}
	}

	private async installSkill(skillName: string, skillsDir: string): Promise<void> {
		const url = `https://raw.githubusercontent.com/${SKILLS_REPO}/${SKILLS_BRANCH}/skills/${skillName}/SKILL.md`;

		try {
			const response = await requestUrl({ url });
			const skillDir = `${skillsDir}/${skillName}`;

			await this.app.vault.adapter.mkdir(skillDir);
			await this.app.vault.adapter.write(`${skillDir}/SKILL.md`, response.text);

			console.log(`Installed skill: ${skillName}`);
		} catch (error) {
			console.error(`Failed to install skill ${skillName}:`, error);
		}
	}
}
