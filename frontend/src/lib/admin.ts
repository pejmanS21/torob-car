import { ApiError } from "./api/client";
import type { AdminAction, AuditRow } from "./api/types";

/** Keyed by `ApiError.code`, never by message text — the project rule. */
export const ADMIN_ERROR_TEXT: Record<string, string> = {
  admin_reauth_required: "برای این کار باید رمزت رو دوباره وارد کنی",
  permission_denied: "دسترسی ادمین نداری",
  cannot_modify_self: "روی حساب خودت نمی‌تونی این کار رو انجام بدی",
  last_admin: "آخرین ادمین فعال رو نمی‌شه غیرفعال یا حذف کرد",
};

export const needsReauth = (error: unknown): boolean =>
  error instanceof ApiError && error.code === "admin_reauth_required";

const ACTION_TEXT: Record<AdminAction, string> = {
  user_disabled: "غیرفعال کرد",
  user_enabled: "فعال کرد",
  user_promoted: "ادمین کرد",
  user_demoted: "از ادمینی برداشت",
  user_password_reset: "رمز را بازنشانی کرد",
  user_deleted: "حذف کرد",
};

/** An unknown action falls back to the raw code rather than throwing: the backend
 *  vocabulary grows one phase at a time and a stale UI must not crash on a new one. */
export function describeAudit(row: AuditRow): string {
  const target =
    typeof row.summary.email === "string" ? row.summary.email : row.target_id ?? "—";
  return `${row.actor_email} — ${ACTION_TEXT[row.action] ?? row.action} — ${target}`;
}
