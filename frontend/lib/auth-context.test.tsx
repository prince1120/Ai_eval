import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { AuthProvider, useAuth, type User } from "./auth-context";
import { apiFetch } from "./api";

vi.mock("./api", () => ({
  apiFetch: vi.fn(),
}));

const mockedApiFetch = vi.mocked(apiFetch);

const testUser: User = {
  id: "u1",
  email: "agent@scribe.ai",
  organization_id: "org1",
  role: "evaluator",
  created_at: "2026-01-01T00:00:00Z",
};

function Probe() {
  const { user, isLoading, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="loading">{String(isLoading)}</span>
      <span data-testid="user">{user ? user.email : "none"}</span>
      <button onClick={() => login(testUser, null)}>login</button>
      <button onClick={() => logout()}>logout</button>
    </div>
  );
}

describe("AuthProvider", () => {
  beforeEach(() => {
    mockedApiFetch.mockReset();
    Object.defineProperty(window, "location", {
      value: { ...window.location, href: "", pathname: "/" },
      writable: true,
    });
  });

  it("hydrates the session from /auth/me on mount without touching any client-side token storage", async () => {
    mockedApiFetch.mockResolvedValueOnce(testUser);

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    expect(screen.getByTestId("loading").textContent).toBe("true");

    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));
    expect(screen.getByTestId("user").textContent).toBe(testUser.email);
    expect(mockedApiFetch).toHaveBeenCalledWith("/auth/me");
  });

  it("treats a failed /auth/me lookup as logged-out rather than throwing", async () => {
    mockedApiFetch.mockRejectedValueOnce(new Error("401"));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));
    expect(screen.getByTestId("user").textContent).toBe("none");
  });

  it("login() stores the user/organization returned by the API response directly, and logout() clears it via /auth/logout", async () => {
    mockedApiFetch.mockResolvedValueOnce(null); // initial /auth/me -> no session

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));

    act(() => {
      screen.getByText("login").click();
    });
    expect(screen.getByTestId("user").textContent).toBe(testUser.email);

    mockedApiFetch.mockResolvedValueOnce({ detail: "Logged out" });
    await act(async () => {
      screen.getByText("logout").click();
    });

    expect(mockedApiFetch).toHaveBeenCalledWith("/auth/logout", { method: "POST" });
    expect(screen.getByTestId("user").textContent).toBe("none");
    expect(window.location.href).toBe("/login");
  });
});
