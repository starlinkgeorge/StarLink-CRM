import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

// A relative URL supports same-origin deployments; split frontend/API projects
// supply their own absolute endpoint through the Vercel environment variable.
const baseURL = (import.meta.env.VITE_API_BASE_URL || "/api/v1").replace(/\/+$/, "");
const api = axios.create({ baseURL });
const refreshClient = axios.create({ baseURL });
export const AUTH_EXPIRED_EVENT = "starlink.auth.expired";

type RefreshResponse = { access_token: string; refresh_token: string };
type RetriableRequestConfig = InternalAxiosRequestConfig & { _retry?: boolean };
let refreshPromise: Promise<string> | null = null;

/**
 * Return the safe business/validation message supplied by FastAPI without
 * exposing internal server errors, SQL, or credentials to CRM users.
 */
export function getApiErrorMessage(error: unknown, fallback: string): string {
  const response = (error as AxiosError<{ detail?: unknown }>).response;
  // Only API validation/business errors are user-facing. Never render a
  // server-generated 5xx message because it could expose implementation
  // details such as SQL or infrastructure configuration.
  if (!response || response.status < 400 || response.status >= 500) return fallback;
  const detail = response.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (item && typeof item === "object" && "msg" in item && typeof item.msg === "string" ? item.msg : null))
      .filter((message): message is string => Boolean(message));
    if (messages.length) return messages.join("；");
  }
  return fallback;
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("starlink.access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(undefined, async (error: AxiosError) => {
  const original = error.config as RetriableRequestConfig | undefined;
  const requestUrl = original?.url ?? "";
  const isAuthRequest = requestUrl.includes("/auth/login") || requestUrl.includes("/auth/refresh");
  if (error.response?.status !== 401 || !original || original._retry || isAuthRequest) {
    return Promise.reject(error);
  }

  const storedRefreshToken = localStorage.getItem("starlink.refresh_token");
  if (!storedRefreshToken) {
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
    return Promise.reject(error);
  }

  original._retry = true;
  try {
    refreshPromise ??= refreshClient
      .post<RefreshResponse>("/auth/refresh", { refresh_token: storedRefreshToken })
      .then(({ data }) => {
        localStorage.setItem("starlink.access_token", data.access_token);
        localStorage.setItem("starlink.refresh_token", data.refresh_token);
        return data.access_token;
      })
      .finally(() => {
        refreshPromise = null;
      });
    const accessToken = await refreshPromise;
    original.headers.Authorization = `Bearer ${accessToken}`;
    return api(original);
  } catch (refreshError) {
    localStorage.removeItem("starlink.access_token");
    localStorage.removeItem("starlink.refresh_token");
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
    return Promise.reject(refreshError);
  }
});

export default api;
