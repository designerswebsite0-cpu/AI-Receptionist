export interface ContactOut {
  id: string;
  contact_type: string;
  value: string;
  is_primary: boolean;
  verified: boolean;
}

export interface CustomerListItem {
  id: string;
  full_name: string | null;
  preferred_language: string;
  preferred_channel: string | null;
  lifetime_value: number;
  loyalty_reference: string | null;
  created_at: string;
  tags: string[];
  is_vip: boolean;
  conversation_count: number;
  last_interaction_at: string | null;
  primary_contact: { contact_type: string; value: string } | null;
}

export interface CustomerDetail extends CustomerListItem {
  preferences: Record<string, unknown>;
  resort_preferences: Record<string, { value: unknown; confidence: number; source: string } | unknown>;
  contacts: ContactOut[];
}

export interface NoteOut {
  id: string;
  author_user_id: string | null;
  note: string;
  created_at: string;
}
