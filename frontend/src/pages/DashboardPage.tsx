import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { salesStageLabels } from "../constants/opportunitySalesStages";
import { getApiErrorMessage } from "../services/api";
import { completeDashboardTask, createDashboardTask, deleteDashboardTask, getCustomers, getDashboardStats, getDashboardTasks } from "../services/crm";
import { useAuth } from "../store/auth";
import type { CalculatedFollowupReminderStatus, Customer, DashboardStats, DashboardTask, FollowUpReminder, OpportunitySalesStage, TaskPriority } from "../types";

const priorityLabels: Record<TaskPriority, string> = { high: "高", medium: "中", low: "低" };
const priorityStyles: Record<TaskPriority, string> = { high: "bg-rose-100 text-rose-700", medium: "bg-amber-100 text-amber-700", low: "bg-slate-100 text-slate-700" };

function FollowUpReminderList({ items, emptyText }: { items: FollowUpReminder[]; emptyText: string }) {
  if (!items.length) return <p className="text-sm text-slate-500">{emptyText}</p>;
  return <div className="space-y-2">{items.slice(0, 3).map((item) => {
    const overdue = item.reminder_status === "overdue";
    return <Link key={item.id} to={`/customers/${item.customer_id}`} className={`block rounded-lg p-2.5 text-sm ${overdue ? "bg-rose-50 hover:bg-rose-100" : "bg-amber-50 hover:bg-amber-100"}`}><div className="flex justify-between gap-2"><strong className="truncate">{item.customer_name}</strong><span className={overdue ? "whitespace-nowrap text-rose-700" : "whitespace-nowrap text-amber-700"}>{item.next_followup_date}</span></div><p className="mt-1 truncate text-slate-600">{item.type} · {item.content}</p></Link>;
  })}</div>;
}

export function DashboardPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "Admin";
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [tasks, setTasks] = useState<DashboardTask[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [title, setTitle] = useState(""); const [dueDate, setDueDate] = useState(""); const [priority, setPriority] = useState<TaskPriority>("medium"); const [customerId, setCustomerId] = useState("");
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const dashboard = await getDashboardStats();
      setStats(dashboard);
      if (isAdmin) setTasks(await getDashboardTasks());
      setError("");
    } catch (requestError: unknown) { setError(getApiErrorMessage(requestError, "无法加载仪表盘数据，请刷新后重试。")); }
  }, [isAdmin]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (isAdmin) void getCustomers({ limit: 100, offset: 0 }).then((page) => setCustomers(page.items)).catch(() => undefined); }, [isAdmin]);

  async function createTask(event: FormEvent) {
    event.preventDefault(); if (!title.trim() || !dueDate) return;
    setBusy(true); try { await createDashboardTask({ title: title.trim(), due_date: dueDate, priority, customer_id: customerId ? Number(customerId) : undefined }); setTitle(""); setCustomerId(""); await load(); } catch (requestError: unknown) { setError(getApiErrorMessage(requestError, "无法新增待办。")); } finally { setBusy(false); }
  }
  async function completeTask(id: number) { setBusy(true); try { await completeDashboardTask(id); await load(); } catch (requestError: unknown) { setError(getApiErrorMessage(requestError, "无法完成待办。")); } finally { setBusy(false); } }
  async function deleteTask(id: number) { setBusy(true); try { await deleteDashboardTask(id); await load(); } catch (requestError: unknown) { setError(getApiErrorMessage(requestError, "无法删除待办。")); } finally { setBusy(false); } }

  const cards: Array<[string, number | undefined, string, CalculatedFollowupReminderStatus | undefined]> = [
    ["已逾期", stats?.followup_reminder_overdue_count, "text-rose-700", "overdue"],
    ["今日需要跟进", stats?.followup_reminder_today_count, "text-orange-700", "today"],
    ["未来3天", stats?.followup_reminder_upcoming_count, "text-amber-700", "upcoming"],
    ["客户总数", stats?.customer_count, "text-slate-800", undefined],
  ];
  const maxStageCount = Math.max(1, ...(stats?.opportunity_pipeline.map((item) => item.count) ?? [0]));

  return <>
    <p className="text-sm text-slate-500">欢迎回来，{user?.name}</p>
    <div className="mt-1 flex flex-wrap items-end justify-between gap-3"><h2 className="text-3xl font-bold">仪表盘</h2>{user?.role !== "Viewer" && <Link to="/customers/new" className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white">新增客户</Link>}</div>
    {error && <p className="mt-4 text-sm text-rose-600" role="alert">{error}</p>}
    <section className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{cards.map(([titleText, value, color, reminderFilter]) => {
      const content = <><p className="text-sm text-slate-500">{titleText}</p><p className={`mt-2 text-3xl font-bold ${color}`}>{value ?? "—"}</p></>;
      const className = "rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200";
      return reminderFilter ? <Link key={titleText} to={`/followup-reminders?status=${reminderFilter}`} className={`${className} transition hover:-translate-y-0.5 hover:shadow-md`}>{content}</Link> : <article key={titleText} className={className}>{content}</article>;
    })}</section>
    <section className="mt-5 grid gap-5 xl:grid-cols-2">
      <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><div className="flex items-center justify-between"><div><h3 className="font-bold">今日待办</h3><p className="mt-1 text-sm text-slate-500">今天到期和已逾期的任务</p></div>{isAdmin && <span className="text-sm text-slate-500">{tasks.length} 项</span>}</div>{isAdmin ? <><form onSubmit={(event) => void createTask(event)} className="mt-4 grid gap-2 sm:grid-cols-2"><input required value={title} onChange={(event) => setTitle(event.target.value)} placeholder="待办标题" className="rounded border px-3 py-2 text-sm" /><input required type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} className="rounded border px-3 py-2 text-sm" /><select value={priority} onChange={(event) => setPriority(event.target.value as TaskPriority)} className="rounded border px-3 py-2 text-sm"><option value="high">高优先级</option><option value="medium">中优先级</option><option value="low">低优先级</option></select><select value={customerId} onChange={(event) => setCustomerId(event.target.value)} className="rounded border px-3 py-2 text-sm"><option value="">不关联客户</option>{customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.company_name}</option>)}</select><button disabled={busy} className="w-fit rounded bg-blue-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">新增待办</button></form><div className="mt-3 divide-y">{tasks.map((task) => <div key={task.id} className="flex items-center justify-between gap-3 py-2.5"><div className="min-w-0"><p className="truncate text-sm font-medium">{task.title}</p><p className="text-xs text-slate-500">截止 {task.due_date}{task.customer_name ? ` · ${task.customer_name}` : ""}</p></div><div className="flex shrink-0 items-center gap-2"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${priorityStyles[task.priority]}`}>{priorityLabels[task.priority]}</span><button type="button" disabled={busy} onClick={() => void completeTask(task.id)} className="text-xs font-semibold text-emerald-700">完成</button><button type="button" disabled={busy} onClick={() => void deleteTask(task.id)} className="text-xs text-rose-600">删除</button></div></div>)}{!tasks.length && <p className="py-5 text-center text-sm text-slate-500">今日没有待办任务。</p>}</div></> : <p className="mt-4 text-sm text-slate-500">待办仅对 Admin 开放。</p>}</article>
      <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><div className="flex items-center justify-between"><div><h3 className="font-bold">客户跟进提醒</h3><p className="mt-1 text-sm text-slate-500">优先处理最紧急客户</p></div><Link to="/followup-reminders" className="text-sm text-blue-700">提醒中心</Link></div><h4 className="mt-4 text-sm font-semibold text-rose-700">逾期未跟进</h4><div className="mt-2"><FollowUpReminderList items={stats?.overdue_followups ?? []} emptyText="暂无逾期客户。" /></div><h4 className="mt-4 text-sm font-semibold text-amber-700">今日待跟进</h4><div className="mt-2"><FollowUpReminderList items={stats?.today_followups ?? []} emptyText="今日暂无待跟进客户。" /></div></article>
    </section>
    <section className="mt-5 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><div className="flex items-center justify-between"><div><h3 className="font-bold">销售漏斗</h3><p className="mt-1 text-sm text-slate-500">按销售阶段查看可见商机</p></div><Link to="/pipeline" className="text-sm text-blue-700">查看看板</Link></div><div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">{stats?.opportunity_pipeline.map((item) => <div key={item.sales_stage} className="rounded-lg bg-slate-50 p-3"><div className="flex justify-between text-sm"><span>{salesStageLabels[item.sales_stage as OpportunitySalesStage]}</span><strong>{item.count}</strong></div><div className="mt-2 h-1.5 overflow-hidden rounded bg-slate-200"><div className="h-full rounded bg-blue-600" style={{ width: `${(item.count / maxStageCount) * 100}%` }} /></div></div>)}</div></section>
  </>;
}
