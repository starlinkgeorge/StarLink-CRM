import api from "./api";
import type { User } from "../types";

export interface LoginResponse { access_token: string; refresh_token: string; user: User; }
export const login = async (email: string, password: string) => (await api.post<LoginResponse>("/auth/login", { email, password })).data;
