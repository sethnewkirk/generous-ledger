export interface StreamMessage {
	type: 'assistant' | 'result' | 'system' | 'stream_event';
	subtype?: string;
	message?: {
		role: string;
		content: Array<{
			type: 'text' | 'tool_use' | 'tool_result' | 'thinking';
			text?: string;
			thinking?: string;
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

export function extractThinkingAndText(messages: StreamMessage[]): { thinking: string; text: string } {
	let thinking = '';
	let text = '';
	const blockTypes = new Map<number, string>();

	for (const msg of messages) {
		if (msg.type !== 'stream_event' || !msg.event) continue;
		const evt = msg.event;

		if (evt.type === 'content_block_start' && evt.index !== undefined) {
			const blockType = evt.content_block?.type || 'text';
			blockTypes.set(evt.index, blockType);
			if (evt.content_block?.text) {
				if (blockType === 'thinking') {
					thinking += evt.content_block.text;
				} else {
					text += evt.content_block.text;
				}
			}
		}

		if (evt.type === 'content_block_delta' && evt.delta?.text) {
			const blockType = blockTypes.get(evt.index ?? -1) || 'text';
			if (evt.delta.type === 'thinking_delta' || blockType === 'thinking') {
				thinking += evt.delta.text;
			} else {
				text += evt.delta.text;
			}
		}
	}

	return { thinking, text };
}

export function separateThinkingFromAnswer(content: string): { thinking: string | null; answer: string } {
	// Look for explicit thinking tags only — no paragraph heuristic
	const match = content.match(/^<(?:thinking|antThinking)>([\s\S]*?)<\/(?:thinking|antThinking)>\s*([\s\S]*)$/);
	if (match) {
		return { thinking: match[1].trim(), answer: match[2].trim() };
	}
	return { thinking: null, answer: content };
}
