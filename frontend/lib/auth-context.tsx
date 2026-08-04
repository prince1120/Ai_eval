"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { apiFetch } from "./api";

export interface User {
  id: string;
  email: string;
  full_name?: string;
  organization_id: string;
  role: string;
  created_at: string;
}

export interface Organization {
  id: string;
  name: string;
  created_at: string;
}

interface AuthContextType {
  user: User | null;
  organization: Organization | null;
  isLoading: boolean;
  login: (user: User, organization?: Organization | null) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    // Populate cached session on client mount to avoid SSR hydration mismatch
    if (typeof window !== "undefined") {
      try {
        const cached = localStorage.getItem("scribe_user");
        if (cached) {
          setUser(JSON.parse(cached));
          setIsLoading(false);
        }
      } catch (e) {
        // Ignore parse error
      }
    }

    apiFetch<User>("/auth/me")
      .then((userData) => {
        setUser(userData);
        if (typeof window !== "undefined") {
          localStorage.setItem("scribe_user", JSON.stringify(userData));
        }
      })
      .catch(() => {
        setUser(null);
        if (typeof window !== "undefined") {
          localStorage.removeItem("scribe_user");
        }
      })
      .finally(() => setIsLoading(false));
  }, []);

  const login = (newUser: User, newOrg?: Organization | null) => {
    setUser(newUser);
    if (typeof window !== "undefined") {
      localStorage.setItem("scribe_user", JSON.stringify(newUser));
    }
    if (newOrg !== undefined) {
      setOrganization(newOrg);
    }
  };

  const logout = () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("scribe_user");
    }
    apiFetch("/auth/logout", { method: "POST" })
      .catch(() => {})
      .finally(() => {
        setUser(null);
        setOrganization(null);
        window.location.href = "/login";
      });
  };

  return (
    <AuthContext.Provider
      value={{ user, organization, isLoading, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
