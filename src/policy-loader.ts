import type { AssistantProvider } from './provider-types';

export type PolicySurface = 'chat' | 'onboarding' | 'routine';
export type PolicyWorkflow = 'general_chat' | 'note_chat' | 'onboarding' | 'daily' | 'evening' | 'weekly' | 'monthly' | 'ambient';
export type PolicyWriteIntent = 'none' | 'profile' | 'memory' | 'routine_output' | 'note_writeback';
export type PolicyIntentTag = 'relationship' | 'recommendation' | 'planning' | 'moral_guidance' | 'file_writing';
export type PolicyFallbackMode = 'none' | 'workflow' | 'core_only';

export interface PolicyRequest {
	surface: PolicySurface;
	workflow: PolicyWorkflow;
	provider: AssistantProvider;
	writeIntent: PolicyWriteIntent;
	intentTags?: PolicyIntentTag[];
}

export interface PolicyPacket {
	markdown: string;
	moduleIds: string[];
	modulePaths: string[];
	fallbackMode: PolicyFallbackMode;
	tokenEstimate: number;
}

interface VaultAdapterLike {
	exists(path: string, sensitive?: boolean): Promise<boolean>;
	read(path: string): Promise<string>;
}

interface PolicyManifestModule {
	path: string;
	title: string;
	layer: 'framework' | 'spec';
}

interface PolicyManifest {
	version: number;
	core: {
		path: string;
		module_ids: string[];
		target_token_budget: number;
		hard_token_budget: number;
	};
	modules: Record<string, PolicyManifestModule>;
	bundles: {
		surface: Record<PolicySurface, string[]>;
		workflow: Record<PolicyWorkflow, string[]>;
		write_intent: Record<PolicyWriteIntent, string[]>;
		intent_tags: Record<PolicyIntentTag, string[]>;
		fallback_workflow: Record<PolicyWorkflow, string[]>;
	};
}

const MANIFEST_PATH = 'docs/policy/manifest.json';

function uniquePreservingOrder(values: string[]): string[] {
	const seen = new Set<string>();
	return values.filter((value) => {
		if (seen.has(value)) {
			return false;
		}
		seen.add(value);
		return true;
	});
}

function stripTitleLine(markdown: string): string {
	const lines = markdown.trim().split('\n');
	if (lines.length > 0 && lines[0].startsWith('# ')) {
		lines.shift();
	}
	return lines.join('\n').trim();
}

function renderCoreMarkdown(manifest: PolicyManifest, moduleTexts: Map<string, string>): string {
	const sections = [
		'# Steward Core',
		'',
		'This is a generated always-on policy artifact assembled from the canonical framework and spec modules listed in `docs/policy/manifest.json`.',
	];

	for (const moduleId of manifest.core.module_ids) {
		const module = manifest.modules[moduleId];
		const body = stripTitleLine(moduleTexts.get(moduleId) ?? '');
		sections.push('', `## ${module.title}`, '', body);
	}

	return `${sections.join('\n').trim()}\n`;
}

function renderPolicyPacketMarkdown(
	coreMarkdown: string,
	manifest: PolicyManifest,
	moduleIds: string[],
	moduleTexts: Map<string, string>
): string {
	const extras = moduleIds.filter((moduleId) => !manifest.core.module_ids.includes(moduleId));
	const sections = [
		'<POLICY_PACKET>',
		coreMarkdown.trim(),
	];

	for (const moduleId of extras) {
		const module = manifest.modules[moduleId];
		const body = moduleTexts.get(moduleId);
		if (!module || !body) {
			continue;
		}
		sections.push('', `<POLICY_MODULE id="${moduleId}" path="${module.path}">`, body.trim(), '</POLICY_MODULE>');
	}

	sections.push('</POLICY_PACKET>');
	return sections.join('\n');
}

function estimateTokenCount(markdown: string): number {
	const trimmed = markdown.trim();
	if (!trimmed) {
		return 0;
	}
	return Math.ceil(trimmed.split(/\s+/).length * 1.33);
}

async function loadManifest(adapter: VaultAdapterLike): Promise<PolicyManifest> {
	const raw = await adapter.read(MANIFEST_PATH);
	return JSON.parse(raw) as PolicyManifest;
}

function buildRequestedModuleIds(manifest: PolicyManifest, request: PolicyRequest, useFallbackWorkflow: boolean): string[] {
	const workflowKey = useFallbackWorkflow ? 'fallback_workflow' : 'workflow';
	const ids = [
		...manifest.core.module_ids,
		...(manifest.bundles.surface[request.surface] ?? []),
		...(manifest.bundles[workflowKey][request.workflow] ?? []),
	];

	if (!useFallbackWorkflow) {
		ids.push(...(manifest.bundles.write_intent[request.writeIntent] ?? []));
		for (const intentTag of request.intentTags ?? []) {
			ids.push(...(manifest.bundles.intent_tags[intentTag] ?? []));
		}
	}

	return uniquePreservingOrder(ids);
}

async function loadModuleTexts(
	adapter: VaultAdapterLike,
	manifest: PolicyManifest,
	moduleIds: string[]
): Promise<Map<string, string>> {
	const texts = new Map<string, string>();
	for (const moduleId of moduleIds) {
		const module = manifest.modules[moduleId];
		if (!module) {
			throw new Error(`Unknown policy module: ${moduleId}`);
		}
		if (!(await adapter.exists(module.path))) {
			throw new Error(`Missing policy module file: ${module.path}`);
		}
		texts.set(moduleId, await adapter.read(module.path));
	}
	return texts;
}

async function loadCoreMarkdown(adapter: VaultAdapterLike, manifest: PolicyManifest): Promise<string> {
	if (await adapter.exists(manifest.core.path)) {
		return adapter.read(manifest.core.path);
	}

	const moduleTexts = await loadModuleTexts(adapter, manifest, manifest.core.module_ids);
	return renderCoreMarkdown(manifest, moduleTexts);
}

export async function buildPolicyPacket(
	adapter: VaultAdapterLike,
	request: PolicyRequest
): Promise<PolicyPacket> {
	const manifest = await loadManifest(adapter);
	const coreMarkdown = await loadCoreMarkdown(adapter, manifest);
	let fallbackMode: PolicyFallbackMode = 'none';
	let moduleIds = buildRequestedModuleIds(manifest, request, false);
	let moduleTexts: Map<string, string>;

	try {
		moduleTexts = await loadModuleTexts(
			adapter,
			manifest,
			moduleIds.filter((moduleId) => !manifest.core.module_ids.includes(moduleId))
		);
	} catch (_error) {
		try {
			moduleIds = buildRequestedModuleIds(manifest, request, true);
			moduleTexts = await loadModuleTexts(
				adapter,
				manifest,
				moduleIds.filter((moduleId) => !manifest.core.module_ids.includes(moduleId))
			);
			fallbackMode = 'workflow';
		} catch (_fallbackError) {
			moduleIds = [...manifest.core.module_ids];
			moduleTexts = new Map<string, string>();
			fallbackMode = 'core_only';
		}
	}

	const markdown = renderPolicyPacketMarkdown(coreMarkdown, manifest, moduleIds, moduleTexts);
	return {
		markdown,
		moduleIds,
		modulePaths: [manifest.core.path, ...moduleIds.map((moduleId) => manifest.modules[moduleId]?.path).filter(Boolean)],
		fallbackMode,
		tokenEstimate: estimateTokenCount(markdown),
	};
}
