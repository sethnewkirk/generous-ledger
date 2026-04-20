import {
	getConfiguredHandle,
	getMissingProviderNotice,
	getProviderBinaryPath,
	getProviderModel,
	normalizeConfiguredProvider,
} from '../provider-config';

describe('provider config helpers', () => {
	test('normalizes configured provider values', () => {
		expect(normalizeConfiguredProvider('codex')).toBe('codex');
		expect(normalizeConfiguredProvider('claude')).toBe('claude');
		expect(normalizeConfiguredProvider('other')).toBeNull();
		expect(normalizeConfiguredProvider(undefined)).toBeNull();
	});

	test('returns provider-specific binary paths and models', () => {
		expect(getProviderBinaryPath('codex', { codexPath: '', claudePath: 'claude' })).toBe('codex');
		expect(getProviderBinaryPath('claude', { codexPath: 'codex', claudePath: '/usr/local/bin/claude' })).toBe('/usr/local/bin/claude');
		expect(getProviderModel('codex', { codexModel: 'gpt-5.4', claudeModel: 'claude-sonnet' })).toBe('gpt-5.4');
		expect(getProviderModel('claude', { codexModel: '', claudeModel: '  ' })).toBeUndefined();
	});

	test('uses Steward as the default handle and exposes a setup notice', () => {
		expect(getConfiguredHandle()).toBe('Steward');
		expect(getConfiguredHandle('  Navigator  ')).toBe('Navigator');
		expect(getMissingProviderNotice()).toContain('Choose Codex or Claude');
	});
});
