import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { apiFetch, ApiError } from "./api";

function mockFetchOnce(response: Partial<Response> & { json?: () => Promise<unknown> }) {
  return vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({}),
    ...response,
  } as Response);
}

describe("apiFetch", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("always sends credentials: include so the httpOnly auth cookie is attached", async () => {
    const fetchMock = mockFetchOnce({ json: async () => ({ ok: true }) });
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/transcripts");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0];
    expect(init.credentials).toBe("include");
  });

  it("does not force a JSON Content-Type when the body is FormData", async () => {
    const fetchMock = mockFetchOnce({ json: async () => ({ ok: true }) });
    vi.stubGlobal("fetch", fetchMock);

    const formData = new FormData();
    formData.append("file", new Blob(["audio"]), "call.mp3");

    await apiFetch("/transcripts/upload-audio", { method: "POST", body: formData });

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers["Content-Type"]).toBeUndefined();
    expect(init.body).toBe(formData);
  });

  it("throws an ApiError carrying the parsed status and detail message on a non-ok response", async () => {
    const fetchMock = mockFetchOnce({
      ok: false,
      status: 422,
      json: async () => ({ detail: "Validation failed" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/templates", { method: "POST" })).rejects.toMatchObject({
      status: 422,
      message: "Validation failed",
    });
    await expect(apiFetch("/templates", { method: "POST" })).rejects.toBeInstanceOf(ApiError);
  });

  it("on a 401 while already on /login, throws without redirecting or hitting the logout endpoint again", async () => {
    window.history.pushState({}, "", "/login");
    const fetchMock = mockFetchOnce({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Not authenticated" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/auth/me")).rejects.toMatchObject({ status: 401 });
    // Only the original request should have fired - no extra call to /auth/logout.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
