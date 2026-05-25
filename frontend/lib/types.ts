export type Role = 'user' | 'assistant';

export type Citation = {
  filename: string;
  source: string;
  section?: string;
  session?: string;
  tool?: string;
};

// A "block" is a single visual unit within an assistant turn. The assistant
// may interleave text and tool-call cards, so we store them in order.
export type AssistantBlock =
  | { kind: 'text'; text: string }
  | {
      kind: 'tool';
      id: string;
      name: string;
      args: Record<string, unknown>;
      result?: Record<string, unknown> | null;
      status: 'running' | 'done' | 'error';
    };

export type Message =
  | { role: 'user'; content: string }
  | {
      role: 'assistant';
      blocks: AssistantBlock[];
      citations: Citation[];
      streaming: boolean;
    };

export type WireEvent =
  | { type: 'text'; delta: string }
  | { type: 'tool_call'; id: string; name: string; args: Record<string, unknown> }
  | { type: 'tool_result'; id: string; name: string; result: Record<string, unknown> }
  | { type: 'done'; citations: Citation[] }
  | { type: 'error'; message: string };
