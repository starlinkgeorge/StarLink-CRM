import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { salesStageLabels } from "../constants/opportunitySalesStages";
import { getDashboardStats } from "../services/crm";
import { useAuth } from "../store/auth";
import type {
  DashboardStats,
  FollowUpReminder,
  OpportunityReminder,
  OpportunitySalesStage,
} from "../types";

const customerLabels: Record<string, string> = {
  Lead: "新线索",
  Contacted: "已联系",
  Quotation: "已报价",
  Negotiation: "谈判中",
  Won: "已成交",
  Lost: "已流失",
};

function FollowUpReminderList({
  items,
  emptyText,
}: {
  items: FollowUpReminder[];
  emptyText: string;
}) {
  if (!items.length) return <p className="text-sm text-slate-500">{emptyText}</p>;
  return (
    <div className="space-y-2">
      {items.map((item) => {
        const overdue = item.reminder_status === "overdue";
        return (
          <Link
            key={item.id}
            to={`/customers/${item.customer_id}`}
            className={`block rounded-lg p-3 text-sm ${overdue ? "bg-rose-50 hover:bg-rose-100" : "bg-amber-50 hover:bg-amber-100"}`}
          >
            <div className="flex justify-between gap-2">
              <strong className="truncate">{item.customer_name}</strong>
              <span className={overdue ? "whitespace-nowrap text-rose-700" : "whitespace-nowrap text-amber-700"}>
                {item.next_followup_date}
              </span>
            </div>
            <p className="mt-1 truncate text-slate-600">{item.type} · {item.content}</p>
          </Link>
        );
      })}
    </div>
  );
}

function OpportunityReminderList({ items }: { items: OpportunityReminder[] }) {
  if (!items.length) return <p className="text-sm text-slate-500">暂无需处理的商机提醒。</p>;
  return (
    <div className="space-y-2">
      {items.map((item) => {
        const quoteDue = item.reminder_status === "Quote Follow-up Due";
        return (
          <Link
            key={item.id}
            to={`/opportunities/${item.id}`}
            className={`block rounded-lg p-3 text-sm ${quoteDue ? "bg-rose-50 hover:bg-rose-100" : "bg-violet-50 hover:bg-violet-100"}`}
          >
            <div className="flex justify-between gap-2">
              <strong className="truncate">{item.name}</strong>
              <span className={quoteDue ? "text-rose-700" : "text-violet-700"}>
                {quoteDue ? "报价待跟进" : "长期无活动"}
              </span>
            </div>
            <p className="mt-1 truncate text-slate-600">
              {item.customer_name} · {quoteDue ? `应跟进：${item.quote_followup_due_date}` : `最后活动：${new Date(item.last_activity_at).toLocaleDateString()}`}
            </p>
          </Link>
        );
      })}
    </div>
  );
}

export function DashboardPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    getDashboardStats()
      .then((value) => {
        if (mounted) {
          setStats(value);
          setError("");
        }
      })
      .catch(() => {
        if (mounted) setError("无法加载仪表盘数据，请刷新后重试。");
      });
    return () => {
      mounted = false;
    };
  }, []);

  const cards = [
    ["今日待跟进客户", stats?.today_due_customer_count, "text-amber-700"],
    ["逾期跟进客户", stats?.overdue_customer_count, "text-rose-700"],
    ["本周跟进任务", stats?.week_followup_task_count, "text-blue-700"],
    ["报价待跟进商机", stats?.quote_followup_overdue_count, "text-rose-700"],
    ["长期无活动商机", stats?.inactive_opportunity_count, "text-violet-700"],
    ["客户总数", stats?.customer_count, "text-slate-800"],
  ];
  const maxStageCount = Math.max(
    1,
    ...(stats?.opportunity_pipeline.map((item) => item.count) ?? [0]),
  );

  return (
    <>
      <p className="text-sm text-slate-500">欢迎回来，{user?.name}</p>
      <div className="mt-1 flex flex-wrap items-end justify-between gap-3">
        <h2 className="text-3xl font-bold">销售工作台</h2>
        {user?.role !== "Viewer" && (
          <Link to="/customers/new" className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white">
            新增客户
          </Link>
        )}
      </div>
      {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}

      <section className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
        {cards.map(([title, value, color]) => (
          <article key={String(title)} className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
            <p className="text-sm text-slate-500">{title}</p>
            <p className={`mt-2 text-3xl font-bold ${color}`}>{value ?? "—"}</p>
          </article>
        ))}
      </section>

      <section className="mt-6 grid gap-5 xl:grid-cols-5">
        <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200 xl:col-span-3">
          <div className="flex items-center justify-between">
            <h3 className="font-bold">销售漏斗</h3>
            <Link to="/pipeline" className="text-sm text-blue-700">查看看板</Link>
          </div>
          <div className="mt-5 space-y-4">
            {stats?.opportunity_pipeline.map((item) => (
              <div key={item.sales_stage}>
                <div className="mb-1 flex justify-between text-sm">
                  <span>{salesStageLabels[item.sales_stage as OpportunitySalesStage]}</span>
                  <strong>{item.count}</strong>
                </div>
                <div className="h-2 overflow-hidden rounded bg-slate-100">
                  <div className="h-full rounded bg-blue-600" style={{ width: `${(item.count / maxStageCount) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
          <div className="mt-5 grid gap-3 border-t pt-4 sm:grid-cols-3">
            <div><p className="text-sm text-slate-500">商机总数</p><strong className="text-xl">{stats?.opportunity_count ?? "—"}</strong></div>
            <div><p className="text-sm text-slate-500">进行中</p><strong className="text-xl">{stats?.active_opportunity_count ?? "—"}</strong></div>
            <div><p className="text-sm text-slate-500">商机总金额</p>{stats?.opportunity_total_amounts.map((item) => <strong key={item.currency} className="mr-3 text-xl">{item.currency} {Number(item.amount).toLocaleString()}</strong>) || "—"}</div>
          </div>
        </article>

        <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200 xl:col-span-2">
          <div className="flex items-center justify-between"><h3 className="font-bold">客户跟进提醒</h3><Link to="/customers" className="text-sm text-blue-700">客户列表</Link></div>
          <h4 className="mt-4 text-sm font-semibold text-rose-700">逾期未跟进</h4>
          <div className="mt-2"><FollowUpReminderList items={stats?.overdue_followups ?? []} emptyText="暂无逾期客户。" /></div>
          <h4 className="mt-5 text-sm font-semibold text-amber-700">今日待跟进</h4>
          <div className="mt-2"><FollowUpReminderList items={stats?.today_followups ?? []} emptyText="今日暂无待跟进客户。" /></div>
        </article>
      </section>

      <section className="mt-6 grid gap-5 lg:grid-cols-2">
        <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <div className="flex items-center justify-between"><h3 className="font-bold">商机提醒</h3><Link to="/opportunities" className="text-sm text-blue-700">商机管理</Link></div>
          <div className="mt-4"><OpportunityReminderList items={stats?.opportunity_reminders ?? []} /></div>
        </article>
        <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <h3 className="font-bold">客户状态分布</h3>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {stats?.pipeline.map((item) => <div key={item.status} className="flex justify-between rounded-lg bg-slate-50 p-3 text-sm"><span>{customerLabels[item.status] ?? item.status}</span><strong>{item.count}</strong></div>)}
          </div>
        </article>
      </section>
    </>
  );
}
