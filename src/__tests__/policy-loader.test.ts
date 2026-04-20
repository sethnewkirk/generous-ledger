import path from 'path';
import { promises as fs } from 'fs';
import { buildPolicyPacket } from '../policy-loader';

const REPO_ROOT = path.resolve(__dirname, '..', '..');

const adapter = {
	async exists(targetPath: string): Promise<boolean> {
		try {
			await fs.access(path.join(REPO_ROOT, targetPath));
			return true;
		} catch {
			return false;
		}
	},
	async read(targetPath: string): Promise<string> {
		return fs.readFile(path.join(REPO_ROOT, targetPath), 'utf8');
	},
};

describe('policy loader', () => {
	test('loads the general chat bundle without routine modules', async () => {
		const packet = await buildPolicyPacket(adapter, {
			surface: 'chat',
			workflow: 'general_chat',
			provider: 'codex',
			writeIntent: 'none',
		});

		expect(packet.fallbackMode).toBe('none');
		expect(packet.moduleIds).toEqual(expect.arrayContaining([
			'framework.role_boundaries',
			'framework.communication',
			'spec.shared_operating_rules',
			'spec.interaction_mode',
		]));
		expect(packet.moduleIds).not.toContain('spec.daily_briefing');
		expect(packet.markdown).toContain('<POLICY_PACKET>');
	});

	test('loads note chat with note handoff rules', async () => {
		const packet = await buildPolicyPacket(adapter, {
			surface: 'chat',
			workflow: 'note_chat',
			provider: 'codex',
			writeIntent: 'note_writeback',
			intentTags: ['file_writing'],
		});

		expect(packet.moduleIds).toContain('spec.note_handoff');
		expect(packet.moduleIds).not.toContain('spec.weekly_review');
	});

	test('falls back to the broader workflow bundle when a requested module is missing', async () => {
		const brokenAdapter = {
			async exists(targetPath: string): Promise<boolean> {
				if (targetPath === 'docs/spec/note-handoff.md') {
					return false;
				}
				return adapter.exists(targetPath);
			},
			async read(targetPath: string): Promise<string> {
				return adapter.read(targetPath);
			},
		};

		const packet = await buildPolicyPacket(brokenAdapter, {
			surface: 'chat',
			workflow: 'note_chat',
			provider: 'codex',
			writeIntent: 'note_writeback',
		});

		expect(packet.fallbackMode).toBe('workflow');
		expect(packet.moduleIds).toContain('spec.memory_retrieval');
	});
});
