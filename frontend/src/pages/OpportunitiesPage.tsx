import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import {
  createOpportunity,
  getCustomers,
  getOpportunities,
  type OpportunityPayload,
} from "../services/crm";
import { useAuth } from "../store/auth";
import type { Customer, OpportunityPage, OpportunityStage } from "../types";

const PAGE_SIZE = 20;
const stages: OpportunityStage[] = ["Lead", "Qualified", "Proposal", "Negotiation", "Won", "Lost"];
const stageLabels: Record<OpportunityStage, string> = {
  Lead: "初始商机", Qualified: "已确认", Proposal: "方案/报价", Negotiation: "谈判中", Won: "已成交", Lost: "已丢失",
};

function stageClass(stage: OpportunityStage) {
  if (stage === "Won") return "bg-emerald-100 text-emerald-700";
  if (stage === "Lost") return "bg-slate-200 text-slate-600";
  if (stage === "Negotiation") return "bg-amber-100 text-amber-700";
  return "bg-blue-100 text-blue-700";
}

export function OpportunitiesPage() {
  const { user } = useAuth();
  const [data, setData] = useState<OpportunityPage | null>(null);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [offset, setOffset] = useState(0);
  const [query, setQuery] = useState("");
  const [stage, setStage] = useState("");
  const [active, setActive] = useState({ q: "", stage: "" });
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<OpportunityPayload>({ customer_id: 0, name: "", currency: "USD" });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async (currentOffset = offset, filters = active) => {
    try { setData(await getOpportunities({ limit: PAGE_SIZE, offset: currentOffset, ...filters })); setError(""); }
    catch { setError("无法加载商机列表。"); }
  }, [offset, active]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    getCustomers({ limit: 100, offset: 0 }).then((page) => setCustomers(page.items)).catch(() => undefined);
  }, []);

  function search(event: FormEvent) { event.preventDefault(); setOffset(0); setActive({ q: query, stage }); }

  async function submit(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError("");
    try {
      await createOpportunity(form);
      setForm({ customer_id: 0, name: "", currency: "USD" }); setShowCreate(false); setOffset(0);
      await load(0);
    } catch { setError("无法创建商机，请检查客户和必填字段。"); }
    finally { setSaving(false); }
  }

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4"><div><p className="text-sm text-slate-500">销售机会管理</p><h2 className="text-3xl font-bold">商机</h2></div>{user?.role !== "Viewer" && <button onClick={() => setShowCreate(!showCreate)} className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white">{showCreate ? "取消新增" : "新增商机"}</button>}</div>

      {showCreate && <form onSubmit={submit} className="mt-6 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><h3 className="font-bold">创建商机</h3><div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3"><select required value={form.customer_id || ""} onChange={(event) => setForm({ ...form, customer_id: Number(event.target.value) })} className="rounded-lg border px-3 py-2"><option value="">选择客户 *</option>{customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.company_name}</option>)}</select><input required maxLength={255} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="商机名称 *" className="rounded-lg border px-3 py-2" /><input maxLength={500} value={form.interested_product ?? ""} onChange={(event) => setForm({ ...form, interested_product: event.target.value })} placeholder="产品需求" className="rounded-lg border px-3 py-2" /><input type="number" min="0" step="0.01" value={form.amount ?? ""} onChange={(event) => setForm({ ...form, amount: event.target.value })} placeholder="金额" className="rounded-lg border px-3 py-2" /><input required minLength={3} maxLength={3} value={form.currency ?? "USD"} onChange={(event) => setForm({ ...form, currency: event.target.value.toUpperCase() })} placeholder="币种" className="rounded-lg border px-3 py-2" /><input type="date" value={form.expected_close_date ?? ""} onChange={(event) => setForm({ ...form, expected_close_date: event.target.value })} className="rounded-lg border px-3 py-2" /><select value={form.stage ?? "Lead"} onChange={(event) => setForm({ ...form, stage: event.target.value as OpportunityStage })} className="rounded-lg border px-3 py-2">{stages.map((item) => <option key={item} value={item}>{stageLabels[item]}</option>)}</select><textarea maxLength={10000} value={form.inquiry_content ?? ""} onChange={(event) => setForm({ ...form, inquiry_content: event.target.value })} placeholder="客户需求或询盘内容" className="min-h-24 rounded-lg border px-3 py-2 md:col-span-2" /></div><button disabled={saving} className="mt-4 rounded-lg bg-slate-900 px-4 py-2 font-semibold text-white disabled:opacity-60">{saving ? "保存中…" : "保存商机"}</button></form>}

      <form onSubmit={search} className="mt-6 flex flex-wrap gap-3 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200"><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="商机、客户或产品" className="min-w-64 flex-1 rounded-lg border px-3 py-2" /><select value={stage} onChange={(event) => setStage(event.target.value)} className="rounded-lg border px-3 py-2"><option value="">全部阶段</option>{stages.map((item) => <option key={item} value={item}>{stageLabels[item]}</option>)}</select><button className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white">搜索</button></form>

      {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}
      <div className="mt-6 overflow-x-auto rounded-xl bg-white shadow-sm ring-1 ring-slate-200"><table className="min-w-full text-left text-sm"><thead className="bg-slate-50 text-slate-500"><tr><th className="px-4 py-3">商机名称</th><th className="px-4 py-3">客户公司</th><th className="px-4 py-3">产品</th><th className="px-4 py-3">金额</th><th className="px-4 py-3">阶段</th><th className="px-4 py-3">预计成交</th><th className="px-4 py-3">负责人</th><th className="px-4 py-3">创建时间</th></tr></thead><tbody>{data?.items.map((item) => <tr key={item.id} className="border-t"><td className="px-4 py-3 font-medium text-blue-700"><Link to={`/opportunities/${item.id}`}>{item.name}</Link></td><td className="px-4 py-3">{item.customer_company}</td><td className="max-w-56 truncate px-4 py-3">{item.interested_product ?? "—"}</td><td className="whitespace-nowrap px-4 py-3">{item.amount ? `${item.currency} ${Number(item.amount).toLocaleString()}` : "—"}</td><td className="px-4 py-3"><span className={`rounded-full px-2 py-1 text-xs font-medium ${stageClass(item.stage)}`}>{stageLabels[item.stage]}</span></td><td className="whitespace-nowrap px-4 py-3">{item.expected_close_date ?? "—"}</td><td className="px-4 py-3">{item.owner_name ?? "—"}</td><td className="whitespace-nowrap px-4 py-3 text-slate-500">{new Date(item.created_at).toLocaleDateString()}</td></tr>)}{data?.items.length === 0 && <tr><td colSpan={8} className="px-4 py-10 text-center text-slate-500">暂无商机。</td></tr>}</tbody></table></div>
      <div className="mt-4 flex justify-between text-sm"><span className="text-slate-500">共 {data?.total ?? 0} 个商机</span><div className="flex gap-2"><button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} className="rounded border px-3 py-1 disabled:opacity-40">上一页</button><button disabled={!data || offset + PAGE_SIZE >= data.total} onClick={() => setOffset(offset + PAGE_SIZE)} className="rounded border px-3 py-1 disabled:opacity-40">下一页</button></div></div>
    </>
  );
}
