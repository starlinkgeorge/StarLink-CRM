import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { createInquiry, getInquiries, type InquiryPayload } from "../services/crm";
import { useAuth } from "../store/auth";
import type { InquiryPage, InquiryStatus } from "../types";

const PAGE_SIZE = 20;
const statuses: InquiryStatus[] = ["New", "Processing", "Converted", "Closed"];
const statusLabels: Record<InquiryStatus, string> = {
  New: "待处理", Processing: "处理中", Converted: "已转换", Closed: "已关闭",
};

function statusClass(status: InquiryStatus) {
  if (status === "Converted") return "bg-emerald-100 text-emerald-700";
  if (status === "Closed") return "bg-slate-200 text-slate-600";
  if (status === "Processing") return "bg-amber-100 text-amber-700";
  return "bg-blue-100 text-blue-700";
}

export function InquiriesPage() {
  const { user } = useAuth();
  const [data, setData] = useState<InquiryPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [source, setSource] = useState("");
  const [active, setActive] = useState({ q: "", status: "", source: "" });
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<InquiryPayload>({
    company_name: "", contact_name: "", source: "Alibaba", source_platform: "Alibaba", inquiry_content: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (currentOffset = offset, filters = active) => {
    try {
      setData(await getInquiries({ limit: PAGE_SIZE, offset: currentOffset, ...filters }));
      setError("");
    } catch {
      setError("无法加载询盘列表。");
    }
  }, [active, offset]);

  useEffect(() => { void load(); }, [load]);

  function search(event: FormEvent) {
    event.preventDefault();
    setOffset(0);
    setActive({ q: query, status, source });
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await createInquiry(form);
      setForm({ company_name: "", contact_name: "", source: "Alibaba", source_platform: "Alibaba", inquiry_content: "" });
      setShowCreate(false);
      setOffset(0);
      await load(0);
    } catch {
      setError("无法创建询盘，请检查公司、联系人与询盘内容。");
    } finally {
      setSaving(false);
    }
  }

  return <>
    <div className="flex flex-wrap items-center justify-between gap-4"><div><p className="text-sm text-slate-500">Alibaba 与未来外部平台询盘统一进入此处</p><h2 className="text-3xl font-bold">询盘管理</h2></div>{user?.role !== "Viewer" && <button onClick={() => setShowCreate(!showCreate)} className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white">{showCreate ? "取消新增" : "手动创建询盘"}</button>}</div>
    {showCreate && <form onSubmit={submit} className="mt-6 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><h3 className="font-bold">手动创建询盘</h3><p className="mt-1 text-sm text-slate-500">可用于手动录入 Alibaba 询盘，也可作为后续 API 同步的输入结构。</p><div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3"><input required maxLength={255} value={form.company_name} onChange={(event) => setForm({ ...form, company_name: event.target.value })} placeholder="客户公司 *" className="rounded-lg border px-3 py-2" /><input required maxLength={120} value={form.contact_name} onChange={(event) => setForm({ ...form, contact_name: event.target.value })} placeholder="联系人 *" className="rounded-lg border px-3 py-2" /><input maxLength={100} value={form.country ?? ""} onChange={(event) => setForm({ ...form, country: event.target.value })} placeholder="国家" className="rounded-lg border px-3 py-2" /><input type="email" maxLength={320} value={form.email ?? ""} onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="邮箱" className="rounded-lg border px-3 py-2" /><input maxLength={50} value={form.whatsapp ?? ""} onChange={(event) => setForm({ ...form, whatsapp: event.target.value })} placeholder="WhatsApp" className="rounded-lg border px-3 py-2" /><input maxLength={500} value={form.interested_product ?? ""} onChange={(event) => setForm({ ...form, interested_product: event.target.value })} placeholder="产品需求" className="rounded-lg border px-3 py-2" /><input required maxLength={80} value={form.source ?? "Alibaba"} onChange={(event) => setForm({ ...form, source: event.target.value })} placeholder="来源渠道" className="rounded-lg border px-3 py-2" /><input required maxLength={80} value={form.source_platform ?? "Alibaba"} onChange={(event) => setForm({ ...form, source_platform: event.target.value })} placeholder="来源平台" className="rounded-lg border px-3 py-2" /><textarea required maxLength={10000} value={form.inquiry_content} onChange={(event) => setForm({ ...form, inquiry_content: event.target.value })} placeholder="原始询盘内容 *" className="min-h-24 rounded-lg border px-3 py-2 md:col-span-2 xl:col-span-3" /></div><button disabled={saving} className="mt-4 rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white disabled:opacity-60">{saving ? "保存中..." : "创建询盘"}</button></form>}
    <form onSubmit={search} className="mt-6 flex flex-wrap gap-3 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200"><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索公司、联系人、邮箱、产品或内容" className="min-w-64 flex-1 rounded-lg border px-3 py-2" /><select value={status} onChange={(event) => setStatus(event.target.value)} className="rounded-lg border px-3 py-2"><option value="">全部状态</option>{statuses.map((item) => <option key={item} value={item}>{statusLabels[item]}</option>)}</select><input value={source} onChange={(event) => setSource(event.target.value)} placeholder="来源渠道" className="rounded-lg border px-3 py-2" /><button className="rounded-lg bg-slate-900 px-4 py-2 font-semibold text-white">筛选</button></form>
    {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}
    <section className="mt-6 overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200"><div className="overflow-x-auto"><table className="w-full min-w-[920px] text-left text-sm"><thead className="bg-slate-50 text-slate-600"><tr><th className="px-5 py-3">客户</th><th className="px-5 py-3">联系人</th><th className="px-5 py-3">平台 / 渠道</th><th className="px-5 py-3">国家</th><th className="px-5 py-3">产品需求</th><th className="px-5 py-3">状态</th><th className="px-5 py-3">创建时间</th></tr></thead><tbody>{data?.items.map((item) => <tr key={item.id} className="border-t"><td className="px-5 py-4 font-medium"><Link to={`/inquiries/${item.id}`} className="text-blue-700 hover:underline">{item.company_name}</Link></td><td className="px-5 py-4">{item.contact_name}</td><td className="px-5 py-4">{item.source_platform}<span className="block text-xs text-slate-500">{item.source}</span></td><td className="px-5 py-4">{item.country ?? "—"}</td><td className="max-w-xs truncate px-5 py-4">{item.interested_product ?? "—"}</td><td className="px-5 py-4"><span className={`rounded-full px-2 py-1 text-xs font-medium ${statusClass(item.status)}`}>{statusLabels[item.status]}</span></td><td className="px-5 py-4">{new Date(item.created_at).toLocaleString()}</td></tr>)}{data?.items.length === 0 && <tr><td colSpan={7} className="px-5 py-12 text-center text-slate-500">暂无询盘</td></tr>}</tbody></table></div></section>
    <div className="mt-4 flex items-center justify-between text-sm text-slate-500"><span>共 {data?.total ?? 0} 条询盘</span><div className="flex gap-2"><button disabled={offset === 0} onClick={() => { const next = Math.max(0, offset - PAGE_SIZE); setOffset(next); void load(next); }} className="rounded border px-3 py-1 disabled:opacity-40">上一页</button><button disabled={!data || offset + PAGE_SIZE >= data.total} onClick={() => { const next = offset + PAGE_SIZE; setOffset(next); void load(next); }} className="rounded border px-3 py-1 disabled:opacity-40">下一页</button></div></div>
  </>;
}
