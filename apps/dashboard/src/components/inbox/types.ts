export interface ConversationOut {
  id: string;
  customer_id: string;
  channel: string;
  status: string;
  current_state: string;
  flow_state: string | null;
  assigned_agent_id: string | null;
  priority: string;
  started_at: string;
  last_message_at: string | null;
  closed_at: string | null;
  ai_active: boolean;
  human_active: boolean;
  summary: string | null;
  tags: string[];
  conversation_metadata: Record<string, unknown>;
  unread_count: number;
  customer_name: string | null;
}

export interface MessageOut {
  id: string;
  conversation_id: string;
  direction: string;
  sender_type: "customer" | "ai" | "human" | "system";
  sender_user_id: string | null;
  content_type: string;
  content_text: string | null;
  delivery_status: string;
  read_at: string | null;
  created_at: string;
}

export interface CustomerOut {
  id: string;
  full_name: string | null;
  preferred_language: string;
  preferred_channel: string | null;
  loyalty_reference: string | null;
  preferences: Record<string, unknown>;
  resort_preferences: Record<string, unknown>;
  contacts: { id: string; contact_type: string; value: string; is_primary: boolean; verified: boolean }[];
  tags: string[];
}
