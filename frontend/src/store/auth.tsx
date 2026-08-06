import { createContext, useContext, useState, type ReactNode } from "react";
import { login as loginRequest } from "../services/auth";
import type { User } from "../types";

type AuthState = { user: User | null; isAuthenticated: boolean; login: (email: string, password: string) => Promise<void>; logout: () => void; };
const AuthContext = createContext<AuthState | undefined>(undefined);
const USER_KEY = "starlink.user";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => JSON.parse(localStorage.getItem(USER_KEY) ?? "null"));
  const logout = () => { localStorage.removeItem("starlink.access_token"); localStorage.removeItem("starlink.refresh_token"); localStorage.removeItem(USER_KEY); setUser(null); };
  const login = async (email: string, password: string) => {
    const result = await loginRequest(email, password);
    localStorage.setItem("starlink.access_token", result.access_token);
    localStorage.setItem("starlink.refresh_token", result.refresh_token);
    localStorage.setItem(USER_KEY, JSON.stringify(result.user));
    setUser(result.user);
  };
  return <AuthContext.Provider value={{ user, isAuthenticated: user !== null, login, logout }}>{children}</AuthContext.Provider>;
}
export function useAuth() { const context = useContext(AuthContext); if (!context) throw new Error("useAuth must be used within AuthProvider"); return context; }
