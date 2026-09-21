import { ApiError } from "./api/client";
import type { AdminAction, AuditRow } from "./api/types";

/** Keyed by `ApiError.code`, never by message text — the project rule. */
export const ADMIN_ERROR_TEXT: Record<string, string> = {
  admin_reauth_required: "برای این کار باید رمزت رو دوباره وارد کنی",
  permission_denied: "دسترسی ادمین نداری",
  cannot_modify_self: "روی حساب خودت نمی‌تونی این کار رو انجام بدی",
  last_admin: "آخرین ادمین فعال رو نمی‌شه غیرفعال یا حذف کرد",
  admin_user_not_found: "این کاربر دیگر وجود ندارد",
  validation_error: "مقدار واردشده معتبر نیست",
};

export const needsReauth = (error: unknown): boolean =>
  error instanceof ApiError && error.code === "admin_reauth_required";

/** Resolves `next` against `origin` (the current origin by default) and requires
 *  their origins to match, rather than pattern-matching the string. The WHATWG URL
 *  parser folds a leading backslash to a slash for special schemes, so
 *  `"/\evil.com"` would pass a `startsWith("/")` check yet resolve off-origin
 *  (CWE-601). `origin` is a parameter — not always `window.location.origin` — so
 *  this is testable without a DOM. */
export function safeNext(
  next: string | null,
  origin: string = typeof window === "undefined" ? "" : window.location.origin,
): string {
  if (!next) return "/";
  try {
    const resolved = new URL(next, origin);
    return resolved.origin === origin ? resolved.pathname + resolved.search : "/";
  } catch {
    return "/";
  }
}

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
