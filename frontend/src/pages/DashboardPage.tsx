import { useEffect, useState } from "react";
import { getDashboardStats } from "../services/crm";
import { useAuth } from "../store/auth";

export function DashboardPage() {
  const { user } = useAuth(); const [stats, setStats] = useState<{ customer_count: number; followup_count: number } | null>(null); const [error, setError] = useState("");
  useEffect(() => { getDashboardStats().then(setStats).catch(() => setError("无法加载统计数据。")); }, []);
  return <><p className="text-sm text-slate-500">欢迎回来，{user?.name}</p><h2 className="mt-1 text-3xl font-bold">工作概览</h2>{error && <p className="mt-4 text-sm text-rose-600">{error}</p>}<section className="mt-7 grid gap-4 sm:grid-cols-2"><article className="rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-200"><p className="text-sm text-slate-500">客户数量</p><p className="mt-2 text-3xl font-bold">{stats?.customer_count ?? "—"}</p></article><article className="rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-200"><p className="text-sm text-slate-500">跟进记录</p><p className="mt-2 text-3xl font-bold">{stats?.followup_count ?? "—"}</p></article></section></>;
}
