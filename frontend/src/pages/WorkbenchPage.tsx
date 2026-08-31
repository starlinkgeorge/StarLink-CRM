import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { getApiErrorMessage } from "../services/api";
import { completeWorkbenchTask, createWorkbenchTask, deleteWorkbenchTask, getCustomers, getWorkbenchToday, saveDailyWorkNote } from "../services/crm";
import { useAuth } from "../store/auth";
import type { Customer, TaskPriority, WorkbenchToday } from "../types";

const priorityLabels: Record<TaskPriority, string> = { high: "高", medium: "中", low: "低" };
const priorityStyles: Record<TaskPriority, string> = { high: "bg-rose-100 text-rose-700", medium: "bg-amber-100 text-amber-700", low: "bg-slate-100 text-slate-700" };

export function WorkbenchPage() {
  const { user } = useAuth();
  const [data, setData] = useState<WorkbenchToday | null>(null);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [title, setTitle] = useState(""); const [dueDate, setDueDate] = useState(""); const [priority, setPriority] = useState<TaskPriority>("medium"); const [customerId, setCustomerId] = useState("");
  const [note, setNote] = useState(""); const [busy, setBusy] = useState(false); const [savingNote, setSavingNote] = useState(false); const [error, setError] = useState("");
  const isAdmin = user?.role === "Admin";

  async function load() {
    try { const result = await getWorkbenchToday(); setData(result); setNote(result.daily_note?.content ?? ""); setError(""); }
    catch (requestError: unknown) { setError(getApiErrorMessage(requestError, "无法加载每日工作台。")); }
  }
  useEffect(() => { void load(); void getCustomers({ limit: 100, offset: 0 }).then((page) => setCustomers(page.items)).catch(() => undefined); }, []);

  async function createTask(event: FormEvent) {
    event.preventDefault(); if (!title.trim() || !dueDate) return;
    setBusy(true); try { await createWorkbenchTask({ title: title.trim(), due_date: dueDate, priority, customer_id: customerId ? Number(customerId) : undefined }); setTitle(""); setCustomerId(""); await load(); }
    catch (requestError: unknown) { setError(getApiErrorMessage(requestError, "无法新增待办。")); } finally { setBusy(false); }
  }
  async function completeTask(id: number) { setBusy(true); try { await completeWorkbenchTask(id); await load(); } catch (requestError: unknown) { setError(getApiErrorMessage(requestError, "无法完成待办。")); } finally { setBusy(false); } }
  async function removeTask(id: number) { setBusy(true); try { await deleteWorkbenchTask(id); await load(); } catch (requestError: unknown) { setError(getApiErrorMessage(requestError, "无法删除待办。")); } finally { setBusy(false); } }
  async function persistNote() { setSavingNote(true); try { await saveDailyWorkNote(note); await load(); } catch (requestError: unknown) { setError(getApiErrorMessage(requestError, "无法保存今日工作备注。")); } finally { setSavingNote(false); } }

  if (!isAdmin) return <><div><p className="text-sm text-slate-500">每日工作台</p><h2 className="text-3xl font-bold">每日工作台</h2></div><p className="mt-6 rounded-xl bg-amber-50 p-4 text-amber-800">当前工作台仅对 Admin 开放。</p></>;
  const metrics = data?.metrics;
  const cards: Array<{ label: string; value: number | string; href: string }> = [
    { label: "今日待跟进客户", value: metrics?.due_today_customers ?? "—", href: "/followup-reminders?status=today" }, { label: "已逾期客户", value: metrics?.overdue_customers ?? "—", href: "/followup-reminders?status=overdue" }, { label: "今日新增客户", value: metrics?.new_customers ?? "—", href: "/customers" }, { label: "今日新增报价", value: metrics?.new_quotations ?? "—", href: "/quotations" }, { label: "今日新增订单", value: metrics?.new_orders ?? "—", href: "/orders" },
  ];
  return <>
    <div><p className="text-sm text-slate-500">今日工作 · {data?.today ?? "加载中"}（上海时间）</p><h2 className="text-3xl font-bold">每日工作台</h2></div>
    {error && <p className="mt-4 text-sm text-rose-600" role="alert">{error}</p>}
    <section className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">{cards.map((card) => <Link key={card.label} to={card.href} className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200 transition hover:ring-blue-400"><p className="text-sm text-slate-500">{card.label}</p><p className="mt-2 text-3xl font-bold text-slate-900">{card.value}</p></Link>)}</section>
    <div className="mt-6 grid gap-6 xl:grid-cols-[1.25fr_0.75fr]"><section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><div className="flex items-center justify-between"><div><h3 className="font-bold">今日待办</h3><p className="mt-1 text-sm text-slate-500">显示今天到期及已逾期任务。</p></div><span className="text-sm text-slate-500">{data?.tasks.length ?? 0} 项</span></div><form onSubmit={(event) => void createTask(event)} className="mt-5 grid gap-3 rounded-lg bg-slate-50 p-3 md:grid-cols-2"><input required value={title} onChange={(event) => setTitle(event.target.value)} placeholder="待办标题" className="rounded border px-3 py-2" /><input required type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} className="rounded border px-3 py-2" /><select value={priority} onChange={(event) => setPriority(event.target.value as TaskPriority)} className="rounded border px-3 py-2"><option value="high">高优先级</option><option value="medium">中优先级</option><option value="low">低优先级</option></select><select value={customerId} onChange={(event) => setCustomerId(event.target.value)} className="rounded border px-3 py-2"><option value="">不关联客户</option>{customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.company_name}</option>)}</select><button disabled={busy} className="w-fit rounded bg-blue-700 px-4 py-2 font-semibold text-white disabled:opacity-60">新增待办</button></form><div className="mt-4 divide-y">{data?.tasks.map((task) => <div key={task.id} className="flex flex-wrap items-center justify-between gap-3 py-3"><div><p className="font-medium">{task.title}</p><p className="mt-1 text-sm text-slate-500">截止：{task.due_date}{task.customer_name ? ` · ${task.customer_name}` : ""}</p></div><div className="flex items-center gap-3"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${priorityStyles[task.priority]}`}>{priorityLabels[task.priority]}</span><button type="button" disabled={busy} onClick={() => void completeTask(task.id)} className="text-sm font-semibold text-emerald-700">完成</button><button type="button" disabled={busy} onClick={() => void removeTask(task.id)} className="text-sm text-rose-600">删除</button></div></div>)}{data && !data.tasks.length && <p className="py-6 text-center text-sm text-slate-500">今天没有待办任务。</p>}</div></section><section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><h3 className="font-bold">今日工作备注</h3><p className="mt-1 text-sm text-slate-500">记录系统无法自动统计的工作内容。</p><textarea value={note} onChange={(event) => setNote(event.target.value)} maxLength={10000} className="mt-4 min-h-44 w-full rounded-lg border p-3" placeholder="例如：与工厂确认样品进度…" /><button type="button" disabled={savingNote} onClick={() => void persistNote()} className="mt-3 rounded bg-slate-900 px-4 py-2 font-semibold text-white disabled:opacity-60">{savingNote ? "保存中…" : "保存备注"}</button></section></div>
    <section className="mt-6 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><h3 className="font-bold">今日工作统计</h3><div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">{[["新增客户", metrics?.new_customers], ["跟进记录", metrics?.new_followups], ["报价", metrics?.new_quotations], ["订单", metrics?.new_orders], ["完成任务", metrics?.completed_tasks]].map(([label, value]) => <div key={String(label)} className="rounded-lg bg-slate-50 p-4"><p className="text-sm text-slate-500">{label}</p><p className="mt-1 text-2xl font-bold">{value ?? "—"}</p></div>)}</div></section>
  </>;
}
