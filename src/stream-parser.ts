export interface StreamMessage {
	type: 'assistant' | 'result' | 'system' | 'stream_event';
	subtype?: string;
	message?: {
		role: string;
		content: Array<{
			type: 'text' | 'tool_use' | 'tool_result';
			text?: string;
			name?: string;
			input?: any;
		}>;
	};
	event?: {
		type: string;
		index?: number;
		delta?: {
			type: string;
			text?: string;
		};
		content_block?: {
			type: string;
			text?: string;
		};
	};
	session_id?: string;
	result?: string;
	is_error?: boolean;
	errors?: string[];
}

export function extractTextContent(messages: StreamMessage[]): string {
	const textParts: string[] = [];

	for (const msg of messages) {
		if (msg.type === 'assistant' && msg.message?.content) {
			for (const block of msg.message.content) {
				if (block.type === 'text' && block.text) {
					textParts.push(block.text);
				}
			}
		}
		if (msg.type === 'result' && msg.result) {
			textParts.push(msg.result);
		}
	}

	return textParts.join('\n');
}

export function extractStreamingText(messages: StreamMessage[]): string {
	let accumulatedText = '';

	for (const msg of messages) {
		if (msg.type === 'stream_event' && msg.event) {
			if (msg.event.type === 'content_block_delta' && msg.event.delta?.text) {
				accumulatedText += msg.event.delta.text;
			} else if (msg.event.type === 'content_block_start' && msg.event.content_block?.text) {
				accumulatedText += msg.event.content_block.text;
			}
		}
	}

	return accumulatedText;
}

export function extractSessionId(messages: StreamMessage[]): string | null {
	// Use session_id from the result message — it's the authoritative source
	for (const msg of messages) {
		if (msg.type === 'result' && msg.session_id) {
			return msg.session_id;
		}
	}
	// Fallback to any message with session_id
	for (const msg of messages) {
		if (msg.session_id) {
			return msg.session_id;
		}
	}
	return null;
}

export function extractError(messages: StreamMessage[]): string | null {
	for (const msg of messages) {
		if (msg.type === 'result' && msg.is_error) {
			if (msg.errors && msg.errors.length > 0) {
				return msg.errors.join('; ');
			}
			if (msg.result) {
				return msg.result;
			}
			return 'Unknown error during execution';
		}
	}
	return null;
}

export function extractCurrentToolUse(messages: StreamMessage[]): string | null {
	const toolUses: string[] = [];
	const toolResults = new Set<string>();

	for (const msg of messages) {
		if (msg.message?.content) {
			for (const block of msg.message.content) {
				if (block.type === 'tool_use' && block.name) {
					toolUses.push(block.name);
				}
				if (block.type === 'tool_result') {
					toolResults.add(toolUses[toolUses.length - 1] || '');
				}
			}
		}
	}

	for (let i = toolUses.length - 1; i >= 0; i--) {
		if (!toolResults.has(toolUses[i])) {
			return toolUses[i];
		}
	}
	return null;
}
