import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const api = axios.create({ baseURL });
const refreshClient = axios.create({ baseURL });
export const AUTH_EXPIRED_EVENT = "starlink.auth.expired";

type RefreshResponse = { access_token: string; refresh_token: string };
type RetriableRequestConfig = InternalAxiosRequestConfig & { _retry?: boolean };
let refreshPromise: Promise<string> | null = null;

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
