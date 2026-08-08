import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { login as loginRequest } from "../services/auth";
import { AUTH_EXPIRED_EVENT } from "../services/api";
import type { User } from "../types";

type AuthState = { user: User | null; isAuthenticated: boolean; login: (email: string, password: string) => Promise<void>; logout: () => void; };
const AuthContext = createContext<AuthState | undefined>(undefined);
const USER_KEY = "starlink.user";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => JSON.parse(localStorage.getItem(USER_KEY) ?? "null"));
  const logout = useCallback(() => {
    localStorage.removeItem("starlink.access_token");
    localStorage.removeItem("starlink.refresh_token");
    localStorage.removeItem(USER_KEY);
    setUser(null);
  }, []);
  useEffect(() => {
    window.addEventListener(AUTH_EXPIRED_EVENT, logout);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, logout);
  }, [logout]);
  const login = async (email: string, password: string) => {
    const result = await loginRequest(email, password);
    localStorage.setItem("starlink.access_token", result.access_token);
    localStorage.setItem("starlink.refresh_token", result.refresh_token);
    localStorage.setItem(USER_KEY, JSON.stringify(result.user));
    setUser(result.user);
  };
  return <AuthContext.Provider value={{ user, isAuthenticated: user !== null, login, logout }}>{children}</AuthContext.Provider>;
}
// This hook intentionally shares the authentication context with the provider.
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() { const context = useContext(AuthContext); if (!context) throw new Error("useAuth must be used within AuthProvider"); return context; }
