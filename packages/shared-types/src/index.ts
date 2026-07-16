/** Mirrors the response envelope defined in docs/api.md. Shared by the
 * dashboard and (from Phase 5) the widget so every client decodes API
 * responses the same way. */

export type ApiError = {
  code: string;
  message: string;
};

export type ApiSuccess<T> = {
  success: true;
  data: T;
};

export type ApiFailure = {
  success: false;
  error: ApiError;
};

export type ApiResponse<T> = ApiSuccess<T> | ApiFailure;

/** Single-resort deployment (docs/product_decisions.md) — no tenant/role
 * concept; a verified session is sufficient for full access. */
export type CurrentUser = {
  user_id: string;
  email: string;
  resort_configured: boolean;
};

export type ResortSettings = {
  id: string;
  resort_name: string;
  legal_name: string | null;
  description: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  postal_code: string | null;
  phone: string | null;
  email: string | null;
  whatsapp: string | null;
  timezone: string;
  currency: string;
  default_language: string;
  check_in_time: string | null;
  check_out_time: string | null;
  logo_url: string | null;
  primary_brand_color: string | null;
  secondary_brand_color: string | null;
  website_url: string | null;
  settings_metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};
