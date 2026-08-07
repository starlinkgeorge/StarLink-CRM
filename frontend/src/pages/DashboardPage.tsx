import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getDashboardStats } from "../services/crm";
import type { DashboardStats } from "../types";
import { useAuth } from "../store/auth";

const labels: Record<string, string> = { Lead: "新线索", Contacted: "已联系", Quotation: "报价中", Negotiation: "谈判中", Won: "已成交", Lost: "已流失" };

export function DashboardPage() {
  const { user } = useAuth(); const [stats, setStats] = useState<DashboardStats | null>(null); const [error, setError] = useState("");
  useEffect(() => { getDashboardStats().then(setStats).catch(() => setError("无法加载仪表盘数据。")); }, []);
  const cards = [["客户总数", stats?.customer_count], ["今日新增", stats?.new_customers_today], ["待跟进", stats?.due_followups], ["跟进记录", stats?.followup_count]];
  return <><p className="text-sm text-slate-500">欢迎回来，{user?.name}</p><div className="mt-1 flex flex-wrap items-end justify-between gap-3"><h2 className="text-3xl font-bold">销售仪表盘</h2>{user?.role !== "Viewer" && <Link to="/customers/new" className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white">新增客户</Link>}</div>
    {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}<section className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{cards.map(([title, value]) => <article key={String(title)} className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><p className="text-sm text-slate-500">{title}</p><p className="mt-2 text-3xl font-bold">{value ?? "—"}</p></article>)}</section>
    <section className="mt-6 grid gap-5 lg:grid-cols-5"><article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200 lg:col-span-3"><h3 className="font-bold">销售漏斗</h3><div className="mt-5 space-y-4">{stats?.pipeline.map((item) => <div key={item.status}><div className="mb-1 flex justify-between text-sm"><span>{labels[item.status]}</span><strong>{item.count}</strong></div><div className="h-2 overflow-hidden rounded bg-slate-100"><div className="h-full rounded bg-blue-600" style={{ width: `${Math.min(100, (item.count / Math.max(1, stats.customer_count)) * 100)}%` }} /></div></div>)}</div></article>
      <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200 lg:col-span-2"><h3 className="font-bold">待办跟进</h3><div className="mt-4 space-y-3">{stats?.upcoming_followups.length ? stats.upcoming_followups.map((item) => <Link key={item.id} to={`/customers/${item.customer_id}`} className="block rounded-lg bg-slate-50 p-3 text-sm hover:bg-blue-50"><div className="flex justify-between gap-2"><strong className="truncate">{item.customer_name}</strong><span className="whitespace-nowrap text-slate-500">{item.next_followup_date}</span></div><p className="mt-1 truncate text-slate-600">{item.type} · {item.content}</p></Link>) : <p className="text-sm text-slate-500">暂无计划跟进事项。</p>}</div></article></section></>;
}
