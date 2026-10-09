import { afterEach, describe, expect, it, vi } from "vitest";

import { api, ApiError, humanise } from "@/lib/api";

afterEach(() => vi.restoreAllMocks());

const rejection = (p: Promise<unknown>) =>
  p.then(
    () => {
      throw new Error("expected the request to fail");
    },
    (e: ApiError) => e,
  );

function mockFetch(status: number, body: unknown) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(body === null ? null : JSON.stringify(body), { status })));
}

describe("api client", () => {
  it("returns parsed JSON", async () => {
    mockFetch(200, { ok: true });
    await expect(api("/x")).resolves.toEqual({ ok: true });
  });

  it("returns undefined for 204", async () => {
    mockFetch(204, null);
    await expect(api("/x", { method: "DELETE" })).resolves.toBeUndefined();
  });

  it("turns validation errors into readable field messages", async () => {
    mockFetch(422, { detail: "Validation failed", errors: [{ field: "inputs.vacancy_pct", message: "must be at most 100" }] });
    const err = await rejection(api("/x"));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(err.summary).toBe("Vacancy %: must be at most 100");
  });

  it("explains an expired session", async () => {
    mockFetch(401, {});
    const err = await rejection(api("/x"));
    expect(err.summary).toMatch(/session has ended/);
  });

  it("reports network failures", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("offline"))));
    const err = await rejection(api("/x"));
    expect(err.status).toBe(0);
    expect(err.message).toMatch(/Could not reach the server/);
  });

  it("humanises field names", () => {
    expect(humanise("body.interest_rate_pct")).toBe("Interest rate %");
  });
});
