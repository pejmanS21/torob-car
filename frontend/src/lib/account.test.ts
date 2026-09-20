import { expect, test } from "bun:test";
import { AUTH_ERROR_TEXT, clearAccount, removeAlertById, toAlertBody, toPriceAlert, toggleSavedId, withAlertId } from "./account";
import type { PriceAlert } from "./types";

const alert = (title: string, id?: string): PriceAlert => ({ id, title, threshold: 500_000_000, params: { q: title } });

test("toggleSavedId adds, removes, and toggling twice restores the list (the revert path)", () => {
  const added = toggleSavedId(["a"], "b");
  expect(added).toEqual({ saved: ["a", "b"], wasSaved: false });
  const reverted = toggleSavedId(added.saved, "b");
  expect(reverted).toEqual({ saved: ["a"], wasSaved: true });
});

test("withAlertId patches the server id onto the optimistic alert only", () => {
  const local = alert("۲۰۶");
  const other = alert("دنا", "srv-1");
  const patched = withAlertId([other, local], local, "srv-2");
  expect(patched.map((a) => a.id)).toEqual(["srv-1", "srv-2"]);
  expect(local.id).toBeUndefined(); // never mutates
});

test("removeAlertById returns what it removed so a failed delete can restore it", () => {
  const kept = alert("دنا", "srv-1");
  const gone = alert("۲۰۶", "srv-2");
  expect(removeAlertById([kept, gone], "srv-2")).toEqual({ alerts: [kept], removed: gone });
  expect(removeAlertById([kept], "missing")).toEqual({ alerts: [kept], removed: undefined });
});

test("logout clears saved and alerts and keeps compare", () => {
  const state = { compare: ["x", "y"], saved: ["a"], alerts: [alert("۲۰۶", "srv-1")] };
  expect(clearAccount(state)).toEqual({ compare: ["x", "y"], saved: [], alerts: [] });
});

test("alerts convert to and from the API shapes without the id leaking into a create body", () => {
  expect(toAlertBody(alert("۲۰۶", "srv-1"))).toEqual({ title: "۲۰۶", threshold: 500_000_000, params: { q: "۲۰۶" } });
  const read = { id: "srv-1", title: "۲۰۶", threshold: 1, params: {}, created_at: "2026-09-20T00:00:00Z" };
  expect(toPriceAlert(read)).toEqual({ id: "srv-1", title: "۲۰۶", threshold: 1, params: {} });
});

test("every auth error code the dialog handles has Persian copy", () => {
  expect(Object.keys(AUTH_ERROR_TEXT).sort()).toEqual([
    "account_disabled",
    "email_taken",
    "invalid_credentials",
    "validation_error",
  ]);
});
