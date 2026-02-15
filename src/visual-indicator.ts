import { WidgetType } from '@codemirror/view';

export type IndicatorState = 'ready' | 'processing' | 'error';

export class ClaudeIndicatorWidget extends WidgetType {
	constructor(
		private state: IndicatorState,
		private toolName?: string
	) {
		super();
	}

	toDOM(): HTMLElement {
		const span = document.createElement('span');
		span.className = `claude-indicator claude-indicator-${this.state}`;

		switch (this.state) {
			case 'ready':
				span.textContent = '\u{1F916}';
				span.setAttribute('aria-label', 'Claude ready');
				break;
			case 'processing':
				if (this.toolName) {
					span.textContent = `\u{1F527} ${this.formatToolName(this.toolName)}`;
					span.setAttribute('aria-label', `Claude using ${this.toolName}`);
				} else {
					span.textContent = '\u231B';
					span.setAttribute('aria-label', 'Claude processing');
				}
				break;
			case 'error':
				span.textContent = '\u26A0\uFE0F';
				span.setAttribute('aria-label', 'Claude error');
				break;
		}

		return span;
	}

	private formatToolName(name: string): string {
		const toolLabels: Record<string, string> = {
			'Read': 'Reading...',
			'Write': 'Writing...',
			'Edit': 'Editing...',
			'Glob': 'Searching files...',
			'Grep': 'Searching content...',
			'Bash': 'Running command...',
			'WebFetch': 'Fetching web...',
			'WebSearch': 'Searching web...',
		};
		return toolLabels[name] || `Using ${name}...`;
	}

	eq(other: ClaudeIndicatorWidget): boolean {
		return other.state === this.state && other.toolName === this.toolName;
	}
}
