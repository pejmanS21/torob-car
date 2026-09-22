import type { PriceAlertCreate, PriceAlertRead } from "./api/types";
import type { PriceAlert } from "./types";

/** Mirror backend `schemas/auth.py`. */
export const MIN_PASSWORD_LENGTH = 8;
export const MAX_PASSWORD_LENGTH = 128;

/** Keyed by `ApiError.code` — never by message text. Anything absent falls back to the shared banner copy. */
export const AUTH_ERROR_TEXT: Record<string, string> = {
  invalid_credentials: "ایمیل یا رمز اشتباه است",
  email_taken: "این ایمیل قبلاً ثبت شده؛ وارد شو",
  account_disabled: "حساب غیرفعال شده",
  validation_error: "ایمیل یا رمز واردشده معتبر نیست",
};

export interface AccountLists { saved: string[]; alerts: PriceAlert[]; }
/** Lists tagged with the account they belong to. `null` = genuinely anonymous
 *  (never signed in on this browser, or an old stored blob with no owner). */
export interface OwnedLists extends AccountLists { ownerId: string | null; }

/** Toggling is its own inverse, so a failed sync reverts by toggling again. */
export function toggleSavedId(saved: string[], id: string): { saved: string[]; wasSaved: boolean } {
  const wasSaved = saved.includes(id);
  return { saved: wasSaved ? saved.filter((x) => x !== id) : [...saved, id], wasSaved };
}

export const withAlertId = (alerts: PriceAlert[], local: PriceAlert, id: string): PriceAlert[] =>
  alerts.map((a) => (a === local ? { ...a, id } : a));

export function removeAlertById(alerts: PriceAlert[], id: string): { alerts: PriceAlert[]; removed: PriceAlert | undefined } {
  return { alerts: alerts.filter((a) => a.id !== id), removed: alerts.find((a) => a.id === id) };
}

/** Logout: the next person on this device must not inherit the account's lists. Compare is a local scratchpad and stays. */
export const clearAccount = <T extends OwnedLists>(state: T): T => ({ ...state, saved: [], alerts: [], ownerId: null });

/** Decides what a fresh sign-in may upload to `/me/import`. A blob with no owner (or
 *  owned by the very account signing in) is this account's own data and goes up as-is;
 *  a blob owned by someone else is a leftover from a previous account on this browser
 *  (cookie expiry is not logout) and must never be imported into a different one. */
export function importableLists(persisted: OwnedLists, userId: string): AccountLists {
  if (persisted.ownerId !== null && persisted.ownerId !== userId) {
    return { saved: [], alerts: [] };
  }
  return { saved: persisted.saved, alerts: persisted.alerts };
}

export const toAlertBody = ({ title, threshold, params }: PriceAlert): PriceAlertCreate => ({ title, threshold, params });
export const toPriceAlert = ({ id, title, threshold, params }: PriceAlertRead): PriceAlert => ({ id, title, threshold, params });
