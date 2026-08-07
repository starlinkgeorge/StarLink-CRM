import axios from "axios";
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { convertLead, getLead } from "../services/crm";
import { useAuth } from "../store/auth";
import type { LeadDetail } from "../types";

const statusLabels = { New: "新询盘", Contacted: "已联系", Qualified: "已确认", Converted: "已转换", Lost: "已失效" };

export function LeadDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [converting, setConverting] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!id) return;
    try { setLead(await getLead(id)); setError(""); } catch { setError("无法加载询盘详情。"); }
  }, [id]);

  useEffect(() => { void load(); }, [load]);

  async function convert() {
    if (!lead || !window.confirm("确认将此询盘转换为客户、联系人和商机？")) return;
    setConverting(true); setError("");
    try { await convertLead(lead.id); await load(); }
    catch (err) { setError(axios.isAxiosError(err) ? err.response?.data?.detail ?? "转换失败。" : "转换失败。"); }
    finally { setConverting(false); }
  }

  if (!lead) return <p className="text-slate-500">{error || "加载中…"}</p>;
  const canConvert = user?.role !== "Viewer" && lead.status !== "Converted" && lead.status !== "Lost";

  return (
    <>
      <Link to="/leads" className="text-sm text-blue-700">← 返回询盘列表</Link>
      <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
        <div><p className="text-sm text-slate-500">{lead.public_id}</p><h2 className="mt-1 text-3xl font-bold">{lead.company_name}</h2><p className="mt-1 text-slate-600">{lead.contact_name}</p></div>
        <div className="flex items-center gap-3"><span className="rounded-full bg-blue-50 px-3 py-1 text-sm font-medium text-blue-700">{statusLabels[lead.status]}</span>{canConvert && <button disabled={converting} onClick={() => void convert()} className="rounded-lg bg-emerald-600 px-4 py-2 font-semibold text-white disabled:opacity-60">{converting ? "转换中…" : "转换为客户"}</button>}</div>
      </div>
      {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}

      {lead.status === "Converted" && lead.converted_customer_id && (
        <section className="mt-5 rounded-xl bg-emerald-50 p-4 ring-1 ring-emerald-200"><h3 className="font-semibold text-emerald-800">询盘已成功转换</h3><p className="mt-1 text-sm text-emerald-700">客户 #{lead.converted_customer_id} · 商机 #{lead.converted_opportunity_id}</p><Link to={`/customers/${lead.converted_customer_id}`} className="mt-3 inline-block text-sm font-semibold text-emerald-800 underline">打开客户详情</Link></section>
      )}

      <section className="mt-6 grid gap-5 lg:grid-cols-2">
        <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><h3 className="font-bold">询盘资料</h3><dl className="mt-4 grid grid-cols-2 gap-4 text-sm"><div><dt className="text-slate-500">国家/地区</dt><dd>{lead.country ?? "—"}</dd></div><div><dt className="text-slate-500">来源</dt><dd>{lead.source ?? "—"}</dd></div><div><dt className="text-slate-500">邮箱</dt><dd>{lead.email ?? "—"}</dd></div><div><dt className="text-slate-500">电话</dt><dd>{lead.phone ?? "—"}</dd></div><div><dt className="text-slate-500">WhatsApp</dt><dd>{lead.whatsapp ?? "—"}</dd></div><div><dt className="text-slate-500">感兴趣产品</dt><dd>{lead.interested_product ?? "—"}</dd></div><div><dt className="text-slate-500">创建时间</dt><dd>{new Date(lead.created_at).toLocaleString()}</dd></div><div><dt className="text-slate-500">更新时间</dt><dd>{new Date(lead.updated_at).toLocaleString()}</dd></div></dl></article>
        <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><h3 className="font-bold">询盘内容</h3><p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-slate-700">{lead.inquiry_content ?? "暂无询盘内容。"}</p></article>
      </section>
    </>
  );
}
