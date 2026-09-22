import { expect, test } from "bun:test";
import { act, renderHook, waitFor } from "@testing-library/react";
import { deferred } from "../../../test/support";
import { useApi } from "./useApi";

test.each([new Error("bad payload"), "failure"])("unexpected errors become API errors: %s", async error => {
  const hook = renderHook(() => useApi("data", async () => { throw error; }));
  await waitFor(() => expect(hook.result.current.loading).toBe(false));
  expect(hook.result.current.error?.code).toBe("network_error");
  expect(hook.result.current.error?.message).toBe(error instanceof Error ? error.message : "request failed");
});

test("a superseded success cannot replace the latest response", async () => {
  const old = deferred<string>();
  const current = deferred<string>();
  const hook = renderHook(({ key }) => useApi(key, () => key === "old" ? old.promise : current.promise), { initialProps: { key: "old" } });
  hook.rerender({ key: "new" });
  await act(async () => current.resolve("new result"));
  expect(hook.result.current.data).toBe("new result");
  await act(async () => old.resolve("obsolete result"));
  expect(hook.result.current.data).toBe("new result");
  expect(hook.result.current.loading).toBe(false);
});
