import { useAppConfig } from '@vben/hooks';

import { getAgentScopeUserId } from './request';

const { apiURL } = useAppConfig(import.meta.env, import.meta.env.PROD);

export interface ChatInputMsg {
  name: string;
  role: 'assistant' | 'system' | 'user';
  content: { text: string; type: 'text' }[];
}

export interface StreamChatOptions {
  agentId: string;
  sessionId: string;
  input: ChatInputMsg;
  onEvent: (event: any) => void;
  signal?: AbortSignal;
}

/**
 * Stream a chat response from the AgentScope backend over SSE.
 *
 * The backend returns a `text/event-stream` where each frame is
 * `data: <AgentEvent json>`. We parse frames incrementally and invoke
 * `onEvent` for each decoded event.
 */
export async function streamChat(options: StreamChatOptions): Promise<void> {
  const { agentId, sessionId, input, onEvent, signal } = options;
  const response = await fetch(`${apiURL}/chat/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-ID': getAgentScopeUserId(),
    },
    body: JSON.stringify({
      agent_id: agentId,
      session_id: sessionId,
      input,
    }),
    signal,
  });

  if (!response.ok || !response.body) {
    const text = await response.text().catch(() => '');
    throw new Error(text || `Chat request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let index = buffer.indexOf('\n\n');
    while (index !== -1) {
      const frame = buffer.slice(0, index).trim();
      buffer = buffer.slice(index + 2);
      if (frame.startsWith('data:')) {
        const payload = frame.slice(5).trim();
        try {
          onEvent(JSON.parse(payload));
        } catch {
          // ignore malformed frame
        }
      }
      index = buffer.indexOf('\n\n');
    }
  }
}
