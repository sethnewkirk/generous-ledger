import { createRenderer, ResponseRenderer } from '../format-renderer';
import { App } from 'obsidian';
import { FormatContext } from '../format-detector';

// Mock Editor for testing
class MockEditor {
  private lines: string[] = [''];
  private cursorLine = 0;

  getCursor() {
    return { line: this.cursorLine, ch: 0 };
  }

  getLine(line: number): string {
    return this.lines[line] || '';
  }

  lastLine(): number {
    return this.lines.length - 1;
  }

  replaceRange(text: string, from: { line: number; ch: number }, to?: { line: number; ch: number }): void {
    if (!to) {
      // Insert at position
      const line = this.lines[from.line] || '';
      const textLines = text.split('\n');

      if (textLines.length === 1) {
        // Single line insert
        this.lines[from.line] = line.substring(0, from.ch) + text + line.substring(from.ch);
      } else {
        // Multi-line insert
        const beforeLines = this.lines.slice(0, from.line);
        const afterLines = this.lines.slice(from.line + 1);
        const prefix = line.substring(0, from.ch);
        const suffix = line.substring(from.ch);

        textLines[0] = prefix + textLines[0];
        textLines[textLines.length - 1] = textLines[textLines.length - 1] + suffix;

        this.lines = [...beforeLines, ...textLines, ...afterLines];
      }
    } else {
      // Replace range - preserve characters before from.ch and after to.ch
      const beforeLines = this.lines.slice(0, from.line);
      const firstLinePrefix = this.lines[from.line]?.substring(0, from.ch) || '';
      const lastLineSuffix = this.lines[to.line]?.substring(to.ch) || '';
      const afterLines = this.lines.slice(to.line + 1);

      const newLines = text.split('\n');

      if (newLines.length === 1) {
        // Single line replacement
        this.lines = [...beforeLines, firstLinePrefix + newLines[0] + lastLineSuffix, ...afterLines];
      } else {
        // Multi-line replacement
        newLines[0] = firstLinePrefix + newLines[0];
        newLines[newLines.length - 1] = newLines[newLines.length - 1] + lastLineSuffix;
        this.lines = [...beforeLines, ...newLines, ...afterLines];
      }
    }
  }

  getAllContent(): string {
    return this.lines.join('\n');
  }
}

describe('MockEditor', () => {
  test('replaceRange without to parameter should insert', () => {
    const editor = new MockEditor();
    editor.replaceRange('Line 1\nLine 2\nLine 3', { line: 0, ch: 0 });
    expect(editor.getAllContent()).toBe('Line 1\nLine 2\nLine 3');
  });

  test('replaceRange with to parameter should replace', () => {
    const editor = new MockEditor();
    (editor as any).lines = ['Line 1', 'Line 2', 'Line 3'];

    const lastLine = editor.lastLine();
    const lastLineLength = editor.getLine(lastLine).length;

    editor.replaceRange('New Line 2', { line: 1, ch: 0 }, { line: lastLine, ch: lastLineLength });
    expect(editor.getAllContent()).toBe('Line 1\nNew Line 2');
  });
});

describe('MarkdownRenderer', () => {
  let renderer: ResponseRenderer;
  let mockEditor: MockEditor;
  let mockApp: App;

  beforeEach(() => {
    mockEditor = new MockEditor();
    mockApp = {} as App;

    const mockContext: FormatContext = {
      format: 'markdown',
      file: {} as any,
      content: '',
    };

    renderer = createRenderer(mockApp, mockContext);
  });

  describe('Streaming UX behavior', () => {
    test('should show streaming content during appendContent', async () => {
      // Initialize response
      const insertPos = await renderer.initResponse(mockEditor as any);

      // Simulate streaming: first chunk
      await renderer.appendContent('Thinking about the problem...', mockEditor as any, insertPos || undefined);

      const content = mockEditor.getAllContent();
      expect(content).toContain('Thinking about the problem...');
    });

    test('should replace streaming content with final answer on finalize', async () => {
      // Initialize response
      const insertPos = await renderer.initResponse(mockEditor as any);

      // Simulate streaming: intermediate content
      await renderer.appendContent('Thinking step by step...', mockEditor as any, insertPos || undefined);
      let content = mockEditor.getAllContent();
      expect(content).toContain('Thinking step by step...');

      // Finalize with final answer (different from streaming content)
      await renderer.finalizeResponse('The answer is 42.', mockEditor as any, insertPos || undefined);

      // Should have replaced streaming content with final answer
      content = mockEditor.getAllContent();
      expect(content).toContain('The answer is 42.');
      expect(content).not.toContain('Thinking step by step...');
    });

    test('should handle empty final content', async () => {
      const insertPos = await renderer.initResponse(mockEditor as any);

      await renderer.appendContent('Streaming...', mockEditor as any, insertPos || undefined);
      await renderer.finalizeResponse('', mockEditor as any, insertPos || undefined);

      const content = mockEditor.getAllContent();
      // Should have callout structure but no content
      expect(content).toContain('[!claude]');
    });
  });

  describe('Thinking collapse (Option D)', () => {
    test('should collapse thinking when response has thinking and answer', async () => {
      const insertPos = await renderer.initResponse(mockEditor as any);

      // Simulate streaming content with thinking + answer
      const fullResponse = "Let me think about this.\n\nFirst, I'll analyze the problem.\n\nThe answer is 42.";
      await renderer.appendContent(fullResponse, mockEditor as any, insertPos || undefined);
      await renderer.finalizeResponse(fullResponse, mockEditor as any, insertPos || undefined);

      const content = mockEditor.getAllContent();

      // Should have collapsed thinking in nested callout
      expect(content).toContain('> > [!note]- Thinking');

      // Thinking should be in nested callout (with > > prefix)
      expect(content).toContain('> > Let me think about this.');
      expect(content).toContain("> > First, I'll analyze the problem.");

      // Answer should be in main callout (with single > prefix)
      expect(content).toContain('> The answer is 42.');
    });

    test('should not add details when response is only answer (single paragraph)', async () => {
      const insertPos = await renderer.initResponse(mockEditor as any);

      // Single paragraph response (no thinking to collapse)
      const shortResponse = "The answer is 42.";
      await renderer.appendContent(shortResponse, mockEditor as any, insertPos || undefined);
      await renderer.finalizeResponse(shortResponse, mockEditor as any, insertPos || undefined);

      const content = mockEditor.getAllContent();

      // Should NOT have nested callout
      expect(content).not.toContain('[!note]- Thinking');

      // Should just have the answer
      expect(content).toContain('> The answer is 42.');
    });

    test('should not add details when response has only two short lines', async () => {
      const insertPos = await renderer.initResponse(mockEditor as any);

      // Two lines but both short (likely both part of answer)
      const shortResponse = "The answer is 42.\nIt's the meaning of life.";
      await renderer.appendContent(shortResponse, mockEditor as any, insertPos || undefined);
      await renderer.finalizeResponse(shortResponse, mockEditor as any, insertPos || undefined);

      const content = mockEditor.getAllContent();

      // Should NOT have nested callout (not enough thinking to justify collapse)
      expect(content).not.toContain('[!note]- Thinking');
    });

    test('should collapse when response has substantial thinking before answer', async () => {
      const insertPos = await renderer.initResponse(mockEditor as any);

      const fullResponse = `Let me analyze this step by step.

First, I need to understand the context. The problem involves multiple factors.

After careful consideration, here's what I found:
- Point 1
- Point 2

The final answer is: it depends on the context.`;

      await renderer.appendContent(fullResponse, mockEditor as any, insertPos || undefined);
      await renderer.finalizeResponse(fullResponse, mockEditor as any, insertPos || undefined);

      const content = mockEditor.getAllContent();

      // Should have collapsed thinking in nested callout
      expect(content).toContain('> > [!note]- Thinking');
      expect(content).toContain('> > Let me analyze this step by step.');

      // Final answer should be in main callout
      expect(content).toContain('> The final answer is: it depends on the context.');
    });
  });
});
