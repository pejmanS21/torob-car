import { expect, test } from "bun:test";
import { ApiError } from "./api/client";
import { ADMIN_ERROR_TEXT, describeAudit, needsReauth, safeNext } from "./admin";
import type { AuditRow } from "./api/types";

const ORIGIN = "http://localhost:3000";

const row = (action: AuditRow["action"]): AuditRow => ({
  id: "a", actor_id: "b", actor_email: "admin@example.com", action,
  target_type: "user", target_id: "c",
  summary: { email: "driver@example.com" }, created_at: "2026-09-21T00:00:00Z",
});

test("needsReauth fires only on the admin_reauth_required code", () => {
  expect(needsReauth(new ApiError(403, "admin_reauth_required", "x"))).toBe(true);
  expect(needsReauth(new ApiError(403, "permission_denied", "x"))).toBe(false);
  expect(needsReauth(new ApiError(401, "not_authenticated", "x"))).toBe(false);
  expect(needsReauth(new Error("boom"))).toBe(false);
});

test("every admin error code the UI can hit has Persian copy", () => {
  expect(Object.keys(ADMIN_ERROR_TEXT).sort()).toEqual([
    "admin_reauth_required", "admin_user_not_found", "cannot_modify_self",
    "last_admin", "permission_denied", "validation_error",
  ]);
  for (const text of Object.values(ADMIN_ERROR_TEXT)) expect(text.length).toBeGreaterThan(0);
});

test.each([
  ["/\\evil.com"], ["//evil.com"], ["https://evil.com"], ["javascript:alert(1)"],
  [null], [""], ["/.//evil.example"], ["/.//"], ["/..//evil.example"],
])("safeNext(%p) is blocked and falls back to \"/\"", (next) => {
  expect(safeNext(next as string | null, ORIGIN)).toBe("/");
});

test("safeNext preserves a same-origin path, with its query string", () => {
  expect(safeNext("/admin", ORIGIN)).toBe("/admin");
  expect(safeNext("/admin?tab=x", ORIGIN)).toBe("/admin?tab=x");
});

test("describeAudit names the actor and the target", () => {
  const described = describeAudit(row("user_disabled"));
  expect(described).toContain("admin@example.com");
  expect(described).toContain("driver@example.com");
});

test("describeAudit falls back rather than throwing on an unknown action", () => {
  const unknown = { ...row("user_disabled"), action: "future_action" } as unknown as AuditRow;
  expect(describeAudit(unknown)).toContain("future_action");
});
