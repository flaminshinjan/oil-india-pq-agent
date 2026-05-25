import type { WireEvent } from './types';

/**
 * Stream the chat endpoint, yielding one parsed WireEvent at a time.
 * Server sends newline-delimited JSON; we buffer partial lines across chunks.
 */
export async function* streamChat(
  history: { role: 'user' | 'assistant'; content: string }[],
  signal?: AbortSignal,
): AsyncGenerator<WireEvent> {
  const resp = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages: history }),
    signal,
  });

  if (!resp.ok || !resp.body) {
    const text = await resp.text().catch(() => '');
    throw new Error(`HTTP ${resp.status}: ${text || resp.statusText}`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });

    let nl: number;
    while ((nl = buf.indexOf('\n')) !== -1) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (!line) continue;
      try {
        yield JSON.parse(line) as WireEvent;
      } catch (e) {
        console.warn('failed to parse stream line', line, e);
      }
    }
  }
  // Flush any trailing line
  const tail = buf.trim();
  if (tail) {
    try {
      yield JSON.parse(tail) as WireEvent;
    } catch {
      /* ignore */
    }
  }
}
