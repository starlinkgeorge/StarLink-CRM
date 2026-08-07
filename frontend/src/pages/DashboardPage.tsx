import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getDashboardStats } from "../services/crm";
import { useAuth } from "../store/auth";
import type { DashboardStats, FollowUpReminder } from "../types";

const labels: Record<string, string> = {
  Lead: "新线索",
  Contacted: "已联系",
  Quotation: "报价中",
  Negotiation: "谈判中",
  Won: "已成交",
  Lost: "已流失",
};

function ReminderList({ items, emptyText }: { items: FollowUpReminder[]; emptyText: string }) {
  if (!items.length) return <p className="text-sm text-slate-500">{emptyText}</p>;
  return items.map((item) => (
    <Link
      key={item.id}
      to={`/customers/${item.customer_id}`}
      className={`block rounded-lg p-3 text-sm ${item.reminder_status === "overdue" ? "bg-rose-50 hover:bg-rose-100" : "bg-amber-50 hover:bg-amber-100"}`}
    >
      <div className="flex justify-between gap-2">
        <strong className="truncate">{item.customer_name}</strong>
        <span className={item.reminder_status === "overdue" ? "whitespace-nowrap text-rose-700" : "whitespace-nowrap text-amber-700"}>
          {item.next_followup_date}
        </span>
      </div>
      <p className="mt-1 truncate text-slate-600">{item.type} · {item.content}</p>
    </Link>
  ));
}

export function DashboardPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getDashboardStats().then(setStats).catch(() => setError("无法加载仪表盘数据。"));
  }, []);

  const cards = [
    ["客户总数", stats?.customer_count],
    ["今日新增", stats?.new_customers_today],
    ["今日待跟进", stats?.today_followup_count],
    ["逾期客户", stats?.overdue_followup_count],
    ["跟进记录", stats?.followup_count],
  ];

  return (
    <>
      <p className="text-sm text-slate-500">欢迎回来，{user?.name}</p>
      <div className="mt-1 flex flex-wrap items-end justify-between gap-3">
        <h2 className="text-3xl font-bold">销售仪表盘</h2>
        {user?.role !== "Viewer" && (
          <Link to="/customers/new" className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white">新增客户</Link>
        )}
      </div>
      {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}

      <section className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {cards.map(([title, value]) => (
          <article key={String(title)} className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
            <p className="text-sm text-slate-500">{title}</p>
            <p className="mt-2 text-3xl font-bold">{value ?? "—"}</p>
          </article>
        ))}
      </section>

      <section className="mt-6 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
        <div className="flex items-center justify-between"><h3 className="font-bold">商机统计</h3><Link to="/opportunities" className="text-sm text-blue-700">进入商机管理</Link></div>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <div className="rounded-lg bg-slate-50 p-4"><p className="text-sm text-slate-500">商机总数</p><strong className="mt-1 block text-2xl">{stats?.opportunity_count ?? "—"}</strong></div>
          <div className="rounded-lg bg-blue-50 p-4"><p className="text-sm text-blue-700">进行中</p><strong className="mt-1 block text-2xl">{stats?.active_opportunity_count ?? "—"}</strong></div>
          <div className="rounded-lg bg-emerald-50 p-4"><p className="text-sm text-emerald-700">成交商机</p><strong className="mt-1 block text-2xl">{stats?.won_opportunity_count ?? "—"}</strong></div>
          <div className="rounded-lg bg-slate-100 p-4"><p className="text-sm text-slate-600">丢失商机</p><strong className="mt-1 block text-2xl">{stats?.lost_opportunity_count ?? "—"}</strong></div>
          <div className="rounded-lg bg-violet-50 p-4"><p className="text-sm text-violet-700">商机金额</p><div className="mt-1 space-y-1">{stats?.opportunity_amounts.length ? stats.opportunity_amounts.map((item) => <strong key={item.currency} className="block text-lg">{item.currency} {Number(item.amount).toLocaleString()}</strong>) : <strong className="block text-2xl">—</strong>}</div></div>
        </div>
      </section>

      <section className="mt-6 grid gap-5 lg:grid-cols-5">
        <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200 lg:col-span-3">
          <h3 className="font-bold">销售漏斗</h3>
          <div className="mt-5 space-y-4">
            {stats?.pipeline.map((item) => (
              <div key={item.status}>
                <div className="mb-1 flex justify-between text-sm"><span>{labels[item.status]}</span><strong>{item.count}</strong></div>
                <div className="h-2 overflow-hidden rounded bg-slate-100">
                  <div className="h-full rounded bg-blue-600" style={{ width: `${Math.min(100, (item.count / Math.max(1, stats.customer_count)) * 100)}%` }} />
                </div>
              </div>
            ))}
          </div>
        </article>

        <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200 lg:col-span-2">
          <div className="flex items-center justify-between">
            <h3 className="font-bold">跟进提醒</h3>
            <span className="text-sm text-slate-500">
              今日 {stats?.today_followup_count ?? 0} · 逾期 {stats?.overdue_followup_count ?? 0}
            </span>
          </div>
          <h4 className="mt-4 text-sm font-semibold text-rose-700">逾期客户</h4>
          <div className="mt-2 space-y-2">
            <ReminderList items={stats?.overdue_followups ?? []} emptyText="暂无逾期客户。" />
          </div>
          <h4 className="mt-5 text-sm font-semibold text-amber-700">今日待跟进</h4>
          <div className="mt-2 space-y-2">
            <ReminderList items={stats?.today_followups ?? []} emptyText="今日暂无待跟进客户。" />
          </div>
        </article>
      </section>
    </>
  );
}
