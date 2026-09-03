import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { getApiErrorMessage } from "../services/api";
import { getAlibabaIntegrationStatus, getSystemSettings, receiveAlibabaInquiry, updateSystemSettings } from "../services/crm";
import { useAuth } from "../store/auth";
import type { AlibabaInquiryResult, AlibabaIntegrationStatus, SystemSettings } from "../types";

type Section = "home" | "followup" | "company" | "quotation-order" | "signature" | "sources";

const cards: { id: Exclude<Section, "home">; title: string; description: string; icon: string }[] = [
  { id: "followup", title: "跟进规则", description: "设置统计起始日期、各阶段提醒与转冷周期。", icon: "跟" },
  { id: "company", title: "公司资料", description: "维护公司名称、Logo、地址及联系资料。", icon: "企" },
  { id: "quotation-order", title: "报价/订单默认设置", description: "设置默认币种、有效期、付款条款和交期。", icon: "报" },
  { id: "signature", title: "邮件签名", description: "设置新邮件和回复默认插入的富文本签名。", icon: "邮" },
  { id: "sources", title: "数据来源管理", description: "保留 Alibaba 国际站的现有接入状态和测试入口。", icon: "数" },
];

export function SettingsPage() {
  const { user } = useAuth();
  const [section, setSection] = useState<Section>("home");
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [status, setStatus] = useState<AlibabaIntegrationStatus | null>(null);
  const [result, setResult] = useState<AlibabaInquiryResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState("");
  const isAdmin = user?.role === "Admin";

  useEffect(() => {
    void getSystemSettings().then(setSettings).catch((requestError: unknown) => setError(getApiErrorMessage(requestError, "无法读取设置。")));
    void getAlibabaIntegrationStatus().then(setStatus).catch(() => undefined);
  }, []);

  async function save() {
    if (!settings || !isAdmin) return;
    setSaving(true); setError("");
    try { setSettings(await updateSystemSettings(settings)); }
    catch (requestError: unknown) { setError(getApiErrorMessage(requestError, "保存设置失败。")); }
    finally { setSaving(false); }
  }

  async function simulateInquiry() {
    setTesting(true); setError(""); setResult(null);
    const nonce = Date.now();
    try {
      setResult(await receiveAlibabaInquiry({
        company_name: `Alibaba Demo School ${nonce}`, contact_name: "Demo Buyer", country: "United States",
        email: `alibaba.demo.${nonce}@example.com`, whatsapp: "+1 202 555 0100",
        inquiry_content: "Please quote Montessori classroom materials for a new preschool.",
        interested_product: "Montessori materials and preschool furniture", source: "Alibaba",
      }));
    } catch (requestError: unknown) { setError(getApiErrorMessage(requestError, "模拟接收询盘失败。")); }
    finally { setTesting(false); }
  }

  if (!settings) return <p className="text-slate-500">正在加载设置…</p>;
  const panel = (title: string, description: string, children: ReactNode) => <section className="mt-6 max-w-4xl rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><h3 className="font-bold">{title}</h3><p className="mt-1 text-sm text-slate-500">{description}</p>{!isAdmin && <p className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">只有 Admin 可以修改设置；当前内容仅供查看。</p>}{children}{isAdmin && <button type="button" disabled={saving} onClick={() => void save()} className="mt-6 rounded-lg bg-blue-700 px-4 py-2 font-semibold text-white disabled:opacity-60">{saving ? "保存中…" : "保存设置"}</button>}</section>;
  const fieldClass = "rounded-lg border border-slate-300 px-3 py-2 disabled:bg-slate-50";

  return <>
    <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-sm text-slate-500">系统设置</p><h2 className="text-3xl font-bold">{section === "home" ? "设置中心" : cards.find((item) => item.id === section)?.title}</h2></div>{section !== "home" && <button type="button" onClick={() => setSection("home")} className="text-sm font-medium text-blue-700">← 返回设置中心</button>}</div>
    {error && <p className="mt-4 text-sm text-rose-600" role="alert">{error}</p>}
    {section === "home" && <div className="mt-6 grid gap-4 md:grid-cols-2">{cards.map((card) => <button key={card.id} type="button" onClick={() => setSection(card.id)} className="flex items-start gap-4 rounded-xl bg-white p-5 text-left shadow-sm ring-1 ring-slate-200 transition hover:ring-blue-400"><span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-blue-50 font-bold text-blue-700">{card.icon}</span><span><span className="block font-bold text-slate-900">{card.title}</span><span className="mt-1 block text-sm text-slate-500">{card.description}</span></span></button>)}</div>}
    {section === "followup" && panel("跟进规则", "全部周期按上海业务日期计算；保存后新的提醒读取会立即采用这些参数。", <div className="mt-5 grid gap-4 md:grid-cols-2">{([
      ["rule_start_date", "跟进统计起始日期", "date"], ["new_customer_first_followup_days", "新客户首次跟进天数", "number"], ["new_customer_unanswered_reminder_days", "新客户未回复提醒天数", "number"], ["communicating_reminder_days", "沟通中提醒天数", "number"], ["quoted_reminder_days", "已报价提醒天数", "number"], ["cold_customer_after_days", "转冷客户天数", "number"], ["cold_customer_reminder_days", "冷客户提醒天数", "number"],
    ] as const).map(([key, label, type]) => <label key={key} className="grid gap-1 text-sm font-medium text-slate-700">{label}<input disabled={!isAdmin} type={type} min={type === "number" ? 1 : undefined} value={settings.followup_rules[key]} onChange={(event) => setSettings({ ...settings, followup_rules: { ...settings.followup_rules, [key]: type === "number" ? Number(event.target.value) : event.target.value } })} className={fieldClass} /></label>)}</div>)}
    {section === "company" && panel("公司资料", "用于统一维护公司对外资料；不会改动历史报价文件。", <div className="mt-5 grid gap-4 md:grid-cols-2">{([
      ["company_name", "公司名称"], ["english_name", "英文名称"], ["logo_url", "Logo URL"], ["address", "地址"], ["phone", "电话"], ["email", "邮箱"], ["website", "网站"],
    ] as const).map(([key, label]) => <label key={key} className="grid gap-1 text-sm font-medium text-slate-700">{label}<input disabled={!isAdmin} type={key === "email" ? "email" : "text"} value={settings.company_profile[key]} onChange={(event) => setSettings({ ...settings, company_profile: { ...settings.company_profile, [key]: event.target.value } })} className={fieldClass} /></label>)}</div>)}
    {section === "quotation-order" && panel("报价/订单默认设置", "新建报价会采用这些默认商业条款；历史报价和订单不会被修改。", <div className="mt-5 grid gap-4 md:grid-cols-2"><label className="grid gap-1 text-sm font-medium text-slate-700">默认币种<input disabled={!isAdmin} maxLength={3} value={settings.quotation_order_defaults.default_currency} onChange={(event) => setSettings({ ...settings, quotation_order_defaults: { ...settings.quotation_order_defaults, default_currency: event.target.value.toUpperCase() } })} className={fieldClass} /></label><label className="grid gap-1 text-sm font-medium text-slate-700">默认报价有效期（天）<input disabled={!isAdmin} type="number" min={1} value={settings.quotation_order_defaults.default_quotation_validity_days} onChange={(event) => setSettings({ ...settings, quotation_order_defaults: { ...settings.quotation_order_defaults, default_quotation_validity_days: Number(event.target.value) } })} className={fieldClass} /></label><label className="grid gap-1 text-sm font-medium text-slate-700 md:col-span-2">默认付款条款<input disabled={!isAdmin} value={settings.quotation_order_defaults.default_payment_term} onChange={(event) => setSettings({ ...settings, quotation_order_defaults: { ...settings.quotation_order_defaults, default_payment_term: event.target.value } })} className={fieldClass} /></label><label className="grid gap-1 text-sm font-medium text-slate-700 md:col-span-2">默认交期<input disabled={!isAdmin} value={settings.quotation_order_defaults.default_delivery_time} onChange={(event) => setSettings({ ...settings, quotation_order_defaults: { ...settings.quotation_order_defaults, default_delivery_time: event.target.value } })} className={fieldClass} /></label></div>)}
    {section === "signature" && panel("邮件签名", "可使用基础 HTML；发送前可在邮件编辑器中修改或删除。", <label className="mt-5 grid gap-1 text-sm font-medium text-slate-700">默认签名 HTML<textarea disabled={!isAdmin} value={settings.email_signature.html} onChange={(event) => setSettings({ ...settings, email_signature: { html: event.target.value } })} className={`${fieldClass} min-h-40 font-mono text-xs`} /></label>)}
    {section === "sources" && <section className="mt-6 max-w-3xl rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><div className="flex flex-wrap items-start justify-between gap-4"><div className="flex items-center gap-3"><div className="flex h-12 w-12 items-center justify-center rounded-xl bg-orange-100 font-bold text-orange-700">A</div><div><h3 className="font-bold">Alibaba 国际站</h3><p className="mt-1 text-sm text-slate-500">自动创建或匹配客户管理中的客户档案</p></div></div><span className={`rounded-full px-3 py-1 text-sm font-medium ${status?.connected ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>{status?.connected ? "已连接" : "未连接"}</span></div><div className="mt-5 rounded-lg bg-blue-50 p-4 text-sm text-blue-800">当前为模拟接入模式，尚未配置真实 Alibaba API。测试按键会创建一条模拟询盘，并通过与未来正式回调相同的客户匹配流程处理。</div>{user?.role !== "Viewer" && <button type="button" disabled={testing} onClick={() => void simulateInquiry()} className="mt-5 rounded-lg bg-orange-600 px-4 py-2 font-semibold text-white disabled:opacity-60">{testing ? "模拟接收中…" : "测试接收阿里询盘"}</button>}{result && <div className="mt-5 rounded-lg bg-emerald-50 p-4 text-sm text-emerald-800"><p className="font-semibold">{result.created ? "已创建新客户" : "检测到重复询盘，已返回现有客户"}</p><p className="mt-1">客户 ID：{result.customer_id} · {result.customer.company_name}</p><Link to={`/customers/${result.customer_id}`} className="mt-3 inline-block font-semibold underline">打开客户详情</Link></div>}</section>}
  </>;
}
