import { WidgetType } from '@codemirror/view';

export type IndicatorState = 'ready' | 'processing' | 'error';

export class ClaudeIndicatorWidget extends WidgetType {
	constructor(private state: IndicatorState) {
		super();
	}

	toDOM(): HTMLElement {
		const span = document.createElement('span');
		span.className = `claude-indicator claude-indicator-${this.state}`;

		switch (this.state) {
			case 'ready':
				span.innerHTML = '🤖';
				span.setAttribute('aria-label', 'Claude ready');
				break;
			case 'processing':
				span.innerHTML = '⏳';
				span.setAttribute('aria-label', 'Claude processing');
				break;
			case 'error':
				span.innerHTML = '⚠️';
				span.setAttribute('aria-label', 'Claude error');
				break;
		}

		return span;
	}

	eq(other: ClaudeIndicatorWidget): boolean {
		return other.state === this.state;
	}
}
