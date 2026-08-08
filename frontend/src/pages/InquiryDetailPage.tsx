import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { convertInquiry, getInquiry, updateInquiry } from "../services/crm";
import { useAuth } from "../store/auth";
import type { Inquiry, InquiryStatus } from "../types";

const statuses: InquiryStatus[] = ["New", "Processing", "Closed"];
const statusLabels: Record<InquiryStatus, string> = { New: "待处理", Processing: "处理中", Converted: "已转换", Closed: "已关闭" };

export function InquiryDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [inquiry, setInquiry] = useState<Inquiry | null>(null);
  const [status, setStatus] = useState<InquiryStatus>("New");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const editable = user?.role !== "Viewer";
  const load = useCallback(async () => { if (!id) return; try { const item = await getInquiry(id); setInquiry(item); setStatus(item.status); setError(""); } catch { setError("无法加载询盘详情。"); } }, [id]);
  useEffect(() => { void load(); }, [load]);

  async function saveStatus() { if (!inquiry) return; setSaving(true); try { const item = await updateInquiry(inquiry.id, { status }); setInquiry(item); setError(""); } catch { setError("无法更新询盘状态。"); } finally { setSaving(false); } }
  async function convert() { if (!inquiry) return; setSaving(true); try { const result = await convertInquiry(inquiry.id); navigate(`/customers/${result.customer.id}`); } catch { setError("无法转换询盘；请确认该询盘尚未转换且未关闭。"); setSaving(false); } }
  if (!inquiry) return <p className="text-slate-500">{error || "加载中..."}</p>;
  const converted = inquiry.status === "Converted";

  return <><Link to="/inquiries" className="text-sm text-blue-700">← 返回询盘列表</Link><div className="mt-4 flex flex-wrap items-start justify-between gap-4"><div><p className="text-sm text-slate-500">{inquiry.public_id}</p><h2 className="mt-1 text-3xl font-bold">{inquiry.company_name}</h2><p className="mt-1 text-slate-600">{inquiry.contact_name} · {inquiry.source_platform} / {inquiry.source}</p></div>{editable && !converted && <button disabled={saving || inquiry.status === "Closed"} onClick={() => void convert()} className="rounded-lg bg-emerald-600 px-4 py-2 font-semibold text-white disabled:opacity-60">转换为客户和商机</button>}</div>{error && <p className="mt-4 text-sm text-rose-600">{error}</p>}
    <section className="mt-6 grid gap-5 lg:grid-cols-2"><article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><h3 className="font-bold">询盘信息</h3><dl className="mt-4 grid grid-cols-2 gap-4 text-sm"><div><dt className="text-slate-500">联系人</dt><dd>{inquiry.contact_name}</dd></div><div><dt className="text-slate-500">国家</dt><dd>{inquiry.country ?? "—"}</dd></div><div><dt className="text-slate-500">邮箱</dt><dd>{inquiry.email ?? "—"}</dd></div><div><dt className="text-slate-500">WhatsApp</dt><dd>{inquiry.whatsapp ?? "—"}</dd></div><div><dt className="text-slate-500">产品需求</dt><dd>{inquiry.interested_product ?? "—"}</dd></div><div><dt className="text-slate-500">创建时间</dt><dd>{new Date(inquiry.created_at).toLocaleString()}</dd></div></dl><h4 className="mt-5 text-sm font-semibold">原始询盘内容</h4><p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{inquiry.inquiry_content}</p></article><article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><h3 className="font-bold">处理状态</h3><p className="mt-3 text-sm">当前状态：<strong>{statusLabels[inquiry.status]}</strong></p>{editable && !converted && <div className="mt-5 flex flex-wrap gap-3"><select value={status} onChange={(event) => setStatus(event.target.value as InquiryStatus)} className="rounded border px-3 py-2">{statuses.map((item) => <option key={item} value={item}>{statusLabels[item]}</option>)}</select><button disabled={saving} onClick={() => void saveStatus()} className="rounded bg-blue-600 px-4 py-2 font-semibold text-white disabled:opacity-60">保存状态</button></div>}{converted && <div className="mt-5 rounded-lg bg-emerald-50 p-4 text-sm text-emerald-800"><p>该询盘已转换为 CRM 客户与商机。</p>{inquiry.customer_id && <Link to={`/customers/${inquiry.customer_id}`} className="mt-2 inline-block font-medium text-emerald-800 underline">查看客户</Link>}{inquiry.converted_opportunity_id && <Link to={`/opportunities/${inquiry.converted_opportunity_id}`} className="ml-4 inline-block font-medium text-emerald-800 underline">查看商机</Link>}</div>}</article></section>
  </>;
}
