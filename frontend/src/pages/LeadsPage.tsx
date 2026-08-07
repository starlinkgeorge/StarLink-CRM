import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { createLead, getLeads, type LeadCreatePayload } from "../services/crm";
import { useAuth } from "../store/auth";
import type { LeadPage, LeadStatus } from "../types";

const PAGE_SIZE = 20;
const statusLabels: Record<LeadStatus, string> = {
  New: "新询盘",
  Contacted: "已联系",
  Qualified: "已确认",
  Converted: "已转换",
  Lost: "已失效",
};
const sources = ["", "Alibaba", "Website", "Facebook", "LinkedIn", "Other"];

const emptyLead: LeadCreatePayload = { company_name: "", contact_name: "" };

function leadStatusClass(status: LeadStatus) {
  if (status === "Converted") return "bg-emerald-100 text-emerald-700";
  if (status === "Lost") return "bg-slate-200 text-slate-600";
  if (status === "Qualified") return "bg-violet-100 text-violet-700";
  if (status === "Contacted") return "bg-blue-100 text-blue-700";
  return "bg-amber-100 text-amber-700";
}

export function LeadsPage() {
  const { user } = useAuth();
  const [data, setData] = useState<LeadPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [source, setSource] = useState("");
  const [activeFilters, setActiveFilters] = useState({ q: "", status: "", source: "" });
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<LeadCreatePayload>(emptyLead);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setError("");
    getLeads({ limit: PAGE_SIZE, offset, ...activeFilters })
      .then(setData)
      .catch(() => setError("无法加载询盘列表。"));
  }, [offset, activeFilters]);

  function search(event: FormEvent) {
    event.preventDefault();
    setOffset(0);
    setActiveFilters({ q: query, status, source });
  }

  async function submitLead(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await createLead(form);
      setForm(emptyLead);
      setShowCreate(false);
      setOffset(0);
      setActiveFilters({ q: "", status: "", source: "" });
      setQuery(""); setStatus(""); setSource("");
      setData(await getLeads({ limit: PAGE_SIZE, offset: 0 }));
    } catch {
      setError("无法创建询盘，请检查必填字段。");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div><p className="text-sm text-slate-500">外贸询盘池</p><h2 className="text-3xl font-bold">Lead 询盘</h2></div>
        {user?.role !== "Viewer" && (
          <button onClick={() => setShowCreate(!showCreate)} className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white">
            {showCreate ? "取消新增" : "新增询盘"}
          </button>
        )}
      </div>

      {showCreate && (
        <form onSubmit={submitLead} className="mt-6 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <h3 className="font-bold">录入新询盘</h3>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <input required maxLength={255} value={form.company_name} onChange={(event) => setForm({ ...form, company_name: event.target.value })} placeholder="公司名称 *" className="rounded-lg border px-3 py-2" />
            <input required maxLength={120} value={form.contact_name} onChange={(event) => setForm({ ...form, contact_name: event.target.value })} placeholder="联系人 *" className="rounded-lg border px-3 py-2" />
            <input maxLength={100} value={form.country ?? ""} onChange={(event) => setForm({ ...form, country: event.target.value })} placeholder="国家/地区" className="rounded-lg border px-3 py-2" />
            <input type="email" maxLength={320} value={form.email ?? ""} onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="邮箱" className="rounded-lg border px-3 py-2" />
            <input maxLength={50} value={form.phone ?? ""} onChange={(event) => setForm({ ...form, phone: event.target.value })} placeholder="电话" className="rounded-lg border px-3 py-2" />
            <input maxLength={50} value={form.whatsapp ?? ""} onChange={(event) => setForm({ ...form, whatsapp: event.target.value })} placeholder="WhatsApp" className="rounded-lg border px-3 py-2" />
            <select value={form.source ?? ""} onChange={(event) => setForm({ ...form, source: event.target.value })} className="rounded-lg border px-3 py-2">
              {sources.map((item) => <option key={item || "none"} value={item}>{item || "选择询盘来源"}</option>)}
            </select>
            <input maxLength={500} value={form.interested_product ?? ""} onChange={(event) => setForm({ ...form, interested_product: event.target.value })} placeholder="感兴趣产品" className="rounded-lg border px-3 py-2 md:col-span-2" />
            <textarea maxLength={10000} value={form.inquiry_content ?? ""} onChange={(event) => setForm({ ...form, inquiry_content: event.target.value })} placeholder="询盘内容" className="min-h-28 rounded-lg border px-3 py-2 md:col-span-2 xl:col-span-3" />
          </div>
          <button disabled={saving} className="mt-4 rounded-lg bg-slate-900 px-4 py-2 font-semibold text-white disabled:opacity-60">{saving ? "保存中…" : "保存询盘"}</button>
        </form>
      )}

      <form onSubmit={search} className="mt-6 grid gap-3 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200 md:grid-cols-4">
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="公司、联系人、产品或询盘内容" className="rounded-lg border px-3 py-2 md:col-span-2" />
        <select value={status} onChange={(event) => setStatus(event.target.value)} className="rounded-lg border px-3 py-2">
          <option value="">全部状态</option>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <select value={source} onChange={(event) => setSource(event.target.value)} className="rounded-lg border px-3 py-2">
          {sources.map((item) => <option key={item || "all"} value={item}>{item || "全部来源"}</option>)}
        </select>
        <button className="w-fit rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white">搜索</button>
      </form>

      {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}
      <div className="mt-6 overflow-x-auto rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-500"><tr><th className="px-4 py-3">公司</th><th className="px-4 py-3">联系人</th><th className="px-4 py-3">国家</th><th className="px-4 py-3">来源</th><th className="px-4 py-3">感兴趣产品</th><th className="px-4 py-3">状态</th><th className="px-4 py-3">创建时间</th></tr></thead>
          <tbody>
            {data?.items.map((lead) => (
              <tr key={lead.id} className="border-t">
                <td className="px-4 py-3 font-medium text-blue-700"><Link to={`/leads/${lead.id}`}>{lead.company_name}</Link></td>
                <td className="px-4 py-3">{lead.contact_name}</td><td className="px-4 py-3">{lead.country ?? "—"}</td><td className="px-4 py-3">{lead.source ?? "—"}</td><td className="max-w-64 truncate px-4 py-3">{lead.interested_product ?? "—"}</td>
                <td className="px-4 py-3"><span className={`rounded-full px-2 py-1 text-xs font-medium ${leadStatusClass(lead.status)}`}>{statusLabels[lead.status]}</span></td>
                <td className="whitespace-nowrap px-4 py-3 text-slate-500">{new Date(lead.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
            {data?.items.length === 0 && <tr><td colSpan={7} className="px-4 py-10 text-center text-slate-500">没有匹配的询盘。</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="mt-4 flex justify-between text-sm"><span className="text-slate-500">共 {data?.total ?? 0} 条询盘</span><div className="flex gap-2"><button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} className="rounded border px-3 py-1 disabled:opacity-40">上一页</button><button disabled={!data || offset + PAGE_SIZE >= data.total} onClick={() => setOffset(offset + PAGE_SIZE)} className="rounded border px-3 py-1 disabled:opacity-40">下一页</button></div></div>
    </>
  );
}
