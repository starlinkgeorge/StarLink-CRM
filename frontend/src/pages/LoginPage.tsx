import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import axios from "axios";
import { useAuth } from "../store/auth";

export function LoginPage() {
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [error, setError] = useState(""); const [loading, setLoading] = useState(false);
  const { login } = useAuth(); const navigate = useNavigate(); const location = useLocation(); const destination = (location.state as { from?: { pathname: string } })?.from?.pathname ?? "/";
  async function submit(event: FormEvent) { event.preventDefault(); setError(""); setLoading(true); try { await login(email, password); navigate(destination, { replace: true }); } catch (err) { setError(axios.isAxiosError(err) ? err.response?.data?.detail ?? "登录失败。" : "登录失败。"); } finally { setLoading(false); } }
  return <main className="grid min-h-screen place-items-center bg-slate-950 p-5"><form onSubmit={submit} className="w-full max-w-md rounded-2xl bg-white p-8 shadow-2xl"><p className="text-sm font-semibold text-blue-600">Dalian StarLink International Trade</p><h1 className="mt-2 text-2xl font-bold">登录 StarLink CRM</h1><p className="mt-2 text-sm text-slate-500">请输入你的工作邮箱和密码。</p>{error && <p className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}<label className="mt-6 block text-sm font-medium">邮箱<input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-blue-600" /></label><label className="mt-4 block text-sm font-medium">密码<input required type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-blue-600" /></label><button disabled={loading} className="mt-6 w-full rounded-lg bg-blue-600 px-4 py-2.5 font-semibold text-white hover:bg-blue-700 disabled:opacity-60">{loading ? "登录中…" : "登录"}</button></form></main>;
}
