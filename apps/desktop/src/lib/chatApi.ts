import { invoke, Channel } from "@tauri-apps/api/core";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
  sequence?: number;
}

export interface HealthStatus {
  healthy: boolean;
  status?: string;
  service?: string;
  version?: string;
  error?: string;
}

export interface ChatChunkEvent {
  delta: string;
  done: boolean;
  error?: string;
}

export interface ConversationSummary {
  id: string;
  title: string;
  model: string;
  mode: string;
  created_at: number;
  updated_at: number;
}

export interface ConversationMessage {
  id: string;
  conversation_id: string;
  sequence: number;
  role: string;
  content: string;
  created_at: number;
}

export async function checkBrainHealth(): Promise<HealthStatus> {
  return await invoke<HealthStatus>("check_brain_health");
}

export async function streamChatMessage(
  model: string,
  messages: Array<{ role: string; content: string }>,
  requestId: string,
  onChunk: (chunk: ChatChunkEvent) => void,
  conversationId?: string,
  userMessageId?: string
): Promise<void> {
  const channel = new Channel<ChatChunkEvent>();
  channel.onmessage = onChunk;

  await invoke("send_chat_message", {
    payload: {
      model,
      messages,
      temperature: 0.7,
      request_id: requestId,
      conversation_id: conversationId || null,
      user_message_id: userMessageId || null,
    },
    onEvent: channel,
  });
}

export async function cancelChatMessage(requestId: string): Promise<boolean> {
  return await invoke<boolean>("cancel_chat", { requestId });
}

export async function listConversations(mode: string = "personal"): Promise<ConversationSummary[]> {
  return await invoke<ConversationSummary[]>("list_conversations", { mode });
}

export async function createConversation(
  title: string,
  model: string,
  mode: string = "personal"
): Promise<ConversationSummary> {
  return await invoke<ConversationSummary>("create_conversation", {
    title,
    model,
    mode,
  });
}

export async function getConversationMessages(
  conversationId: string,
  mode: string = "personal"
): Promise<ConversationMessage[]> {
  return await invoke<ConversationMessage[]>("get_conversation_messages", {
    conversationId,
    mode,
  });
}

export async function renameConversation(
  conversationId: string,
  title: string
): Promise<ConversationSummary> {
  return await invoke<ConversationSummary>("rename_conversation", {
    conversationId,
    title,
  });
}

export async function deleteConversation(conversationId: string): Promise<boolean> {
  return await invoke<boolean>("delete_conversation", {
    conversationId,
  });
}
