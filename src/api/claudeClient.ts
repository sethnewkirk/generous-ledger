import Anthropic from '@anthropic-ai/sdk';

export interface ClaudeClientConfig {
	apiKey: string;
	model: string;
	maxTokens: number;
	systemPrompt?: string;
}

export class ClaudeClient {
	private client: Anthropic;
	private config: ClaudeClientConfig;

	constructor(config: ClaudeClientConfig) {
		this.config = config;
		this.client = new Anthropic({
			apiKey: config.apiKey,
		});
	}

	async sendMessage(content: string): Promise<string> {
		try {
			const message = await this.client.messages.create({
				model: this.config.model,
				max_tokens: this.config.maxTokens,
				system: this.config.systemPrompt || undefined,
				messages: [
					{
						role: 'user',
						content: content
					}
				]
			});

			if (message.content[0].type === 'text') {
				return message.content[0].text;
			}

			throw new Error('Unexpected response format from Claude API');
		} catch (error) {
			if (error instanceof Anthropic.APIError) {
				throw new Error(`Claude API Error: ${error.message}`);
			}
			throw error;
		}
	}

	updateConfig(config: Partial<ClaudeClientConfig>): void {
		this.config = { ...this.config, ...config };
		if (config.apiKey) {
			this.client = new Anthropic({
				apiKey: config.apiKey,
			});
		}
	}
}
