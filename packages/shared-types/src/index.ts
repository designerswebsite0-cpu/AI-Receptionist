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

export type TenantMembership = {
  tenant_id: string;
  tenant_name: string;
  tenant_slug: string;
  role: "owner" | "admin" | "manager" | "staff" | "read_only";
};

export type CurrentUser = {
  user_id: string;
  email: string;
  memberships: TenantMembership[];
};
