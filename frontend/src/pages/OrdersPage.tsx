import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { backfillWonOrders, createOrder, getCustomers, getOpportunities, getOrderByQuotation, getOrders, getQuotation, getQuotations, previewWonOrderBackfill, type OrderPayload } from "../services/crm";
import { getApiErrorMessage } from "../services/api";
import { useAuth } from "../store/auth";
import type { Customer, OpportunityListItem, Order, OrderPage, QuotationListItem, WonOrderBackfillPreview, WonOrderBackfillResult } from "../types";

const payment = [["Unpaid", "未付款"], ["Deposit Received", "已收定金"], ["Paid in Full", "已收全款"]] as const;
const production = [["Not Started", "未开始"], ["In Production", "生产中"], ["Completed", "已完成"]] as const;
const shipping = [["Pending Shipment", "待出货"], ["Shipped", "已出货"], ["Delivered", "已签收"]] as const;
const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());

type Filters = { q: string; start_date: string; end_date: string; payment_status: "" | Order["payment_status"]; production_status: "" | Order["production_status"]; shipping_status: "" | Order["shipping_status"]; };
const emptyFilters: Filters = { q: "", start_date: "", end_date: "", payment_status: "", production_status: "", shipping_status: "" };

export function OrdersPage() {
  const { user } = useAuth(); const navigate = useNavigate(); const location = useLocation(); const [params] = useSearchParams();
  const customerId = Number(params.get("customer_id")) || undefined;
  const [data, setData] = useState<OrderPage | null>(null); const [customers, setCustomers] = useState<Customer[]>([]);
  const [opportunities, setOpportunities] = useState<OpportunityListItem[]>([]); const [quotations, setQuotations] = useState<QuotationListItem[]>([]);
  const [offset, setOffset] = useState(0);
  const [filters, setFilters] = useState<Filters>(emptyFilters); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const [backfillPreview, setBackfillPreview] = useState<WonOrderBackfillPreview | null>(null);
  const [backfillResult, setBackfillResult] = useState<WonOrderBackfillResult | null>(null);
  const [fallbackOrderDate, setFallbackOrderDate] = useState("");
  const [backfillBusy, setBackfillBusy] = useState(false);
  const [show, setShow] = useState(location.pathname.endsWith("/new"));
  const [form, setForm] = useState<OrderPayload>({ order_no: "", customer_id: customerId ?? 0, opportunity_id: Number(params.get("opportunity_id")) || undefined, quotation_id: Number(params.get("quotation_id")) || undefined, order_date: today, currency: "USD", order_amount: "", rmb_received_amount: "0", purchase_cost: "0", freight_cost: "0" });
  const loadOrders = useCallback(async (nextFilters = filters, nextOffset = offset) => {
    try {
      setData(await getOrders({ limit: 20, offset: nextOffset, customer_id: customerId, q: nextFilters.q || undefined, start_date: nextFilters.start_date || undefined, end_date: nextFilters.end_date || undefined, payment_status: nextFilters.payment_status || undefined, production_status: nextFilters.production_status || undefined, shipping_status: nextFilters.shipping_status || undefined }));
      setError("");
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError, "无法加载订单。"));
    }
  }, [customerId, filters, offset]);
  useEffect(() => { void loadOrders(); void getCustomers({ limit: 100, offset: 0 }).then((page) => setCustomers(page.items)).catch(() => setError("无法加载可选客户。")); }, [loadOrders]);
  useEffect(() => {
    const selectedCustomerId = form.customer_id;
    if (!selectedCustomerId) { setOpportunities([]); setQuotations([]); return; }
    let active = true;
    void Promise.all([
      getOpportunities({ limit: 100, offset: 0, customer_id: selectedCustomerId }),
      getQuotations({ limit: 100, offset: 0, customer_id: selectedCustomerId }),
    ]).then(([opportunityPage, quotationPage]) => {
      if (!active) return;
      setOpportunities(opportunityPage.items); setQuotations(quotationPage.items);
    }).catch(() => { if (active) setError("无法加载该客户的商机或报价。") });
    return () => { active = false; };
  }, [form.customer_id]);
  useEffect(() => {
    const quotationId = Number(params.get("quotation_id")); if (!quotationId) return; setBusy(true);
    void (async () => {
      const quote = await getQuotation(quotationId); const existing = await getOrderByQuotation(quotationId);
      if (existing) { navigate(`/orders/${existing.id}`, { replace: true }); return; }
      const version = quote.versions.find((item) => item.version_no === quote.current_version) ?? quote.versions[0];
      setForm((current) => ({ ...current, quotation_id: quotationId, customer_id: quote.customer_id, opportunity_id: quote.opportunity_id ?? undefined, currency: version?.currency ?? quote.currency, order_amount: version?.total_amount ?? quote.total_amount }));
    })().catch(() => setError("无法读取报价默认信息。请从订单管理手动创建。")).finally(() => setBusy(false));
  }, [navigate, params]);
  async function submit(event: FormEvent) { event.preventDefault(); setBusy(true); try { const order = await createOrder(form); navigate(`/orders/${order.id}`); } catch (requestError: unknown) { setError(getApiErrorMessage(requestError, "无法创建订单，服务端已回滚本次操作。请检查客户、订单号和报价是否重复。")); } finally { setBusy(false); } }
  async function scanWonOrders() {
    setBackfillBusy(true); setBackfillResult(null);
    try { setBackfillPreview(await previewWonOrderBackfill()); setError(""); }
    catch (requestError: unknown) { setError(getApiErrorMessage(requestError, "无法扫描历史赢单订单。")); }
    finally { setBackfillBusy(false); }
  }
  async function runWonBackfill() {
    if (!backfillPreview) return;
    if (backfillPreview.requires_date_confirmation > 0 && !fallbackOrderDate) {
      setError("有历史赢单缺少可靠赢单日期，请先由管理员确认补建订单日期。"); return;
    }
    setBackfillBusy(true);
    try {
      const result = await backfillWonOrders(fallbackOrderDate || undefined);
      setBackfillResult(result); setBackfillPreview(null); setError("");
      await loadOrders(filters, 0); setOffset(0);
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError, "补建历史订单失败，服务端已回滚本次操作。请联系管理员查看服务日志。"));
    } finally { setBackfillBusy(false); }
  }
  const editable = user?.role !== "Viewer";
  const isAdmin = user?.role === "Admin";
  const setFilter = <K extends keyof Filters>(key: K, value: Filters[K]) => setFilters((current) => ({ ...current, [key]: value }));
  return <>
    <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-sm text-slate-500">真实成交、履约与利润核算</p><h2 className="text-3xl font-bold">订单管理</h2></div><div className="flex flex-wrap gap-2">{isAdmin && !show && <button type="button" onClick={() => void scanWonOrders()} disabled={backfillBusy} className="rounded border border-amber-500 px-4 py-2 font-semibold text-amber-700 disabled:opacity-60">{backfillBusy ? "正在扫描…" : "补建赢单订单"}</button>}{editable && !show && <button type="button" onClick={() => { setShow(true); navigate("/orders/new"); }} className="rounded bg-blue-700 px-4 py-2 font-semibold text-white">新建订单</button>}</div></div>
    {backfillPreview && <section className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-slate-700">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-base font-bold text-slate-900">历史赢单订单扫描</h3><p className="mt-1">仅会处理当前为“赢单”且尚未关联订单的商机。确认前不会修改任何数据。</p></div><button type="button" onClick={() => setBackfillPreview(null)} className="text-slate-600">关闭</button></div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5"><div><b>{backfillPreview.total_won}</b><p>赢单商机总数</p></div><div><b>{backfillPreview.already_ordered}</b><p>已有订单</p></div><div><b>{backfillPreview.eligible_auto_build}</b><p>可直接补建</p></div><div><b>{backfillPreview.requires_date_confirmation}</b><p>需确认日期</p></div><div><b>{backfillPreview.unbuildable}</b><p>无法自动补建</p></div></div>
      {backfillPreview.requires_date_confirmation > 0 && <label className="mt-4 block max-w-xs font-medium">缺少可靠赢单日期时使用的订单日期<input required type="date" value={fallbackOrderDate} onChange={(event) => setFallbackOrderDate(event.target.value)} className="mt-1 block w-full rounded border bg-white px-3 py-2" /></label>}
      {backfillPreview.candidates.length > 0 && <div className="mt-4 max-h-56 overflow-auto rounded border bg-white"><table className="min-w-[760px] w-full text-left"><thead className="bg-slate-100"><tr><th className="px-3 py-2">商机</th><th className="px-3 py-2">客户</th><th className="px-3 py-2">报价</th><th className="px-3 py-2">订单日期</th><th className="px-3 py-2">结果</th></tr></thead><tbody>{backfillPreview.candidates.map((candidate) => <tr key={candidate.opportunity_id} className="border-t"><td className="px-3 py-2"><Link className="text-blue-700" to={`/opportunities/${candidate.opportunity_id}`}>{candidate.opportunity_name}</Link></td><td className="px-3 py-2">{candidate.customer_company}</td><td className="px-3 py-2">{candidate.quotation_number ?? "—"}</td><td className="px-3 py-2">{candidate.order_date ?? "需确认"}</td><td className="px-3 py-2">{candidate.reason ?? "可补建"}</td></tr>)}</tbody></table></div>}
      <button type="button" onClick={() => void runWonBackfill()} disabled={backfillBusy || (!backfillPreview.eligible_auto_build && !backfillPreview.requires_date_confirmation)} className="mt-4 rounded bg-amber-600 px-4 py-2 font-semibold text-white disabled:opacity-60">{backfillBusy ? "正在补建…" : "确认补建安全订单"}</button>
    </section>}
    {backfillResult && <p className="mt-4 rounded bg-emerald-50 px-4 py-3 text-sm text-emerald-800">补建完成：新建 {backfillResult.created} 个订单；已有订单跳过 {backfillResult.already_ordered} 个；缺少日期 {backfillResult.requires_date_confirmation} 个；无法自动补建 {backfillResult.unbuildable} 个。</p>}
    {show && <form onSubmit={submit} className="mt-5 grid gap-3 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200 md:grid-cols-3">
      <div className="md:col-span-3 flex items-center justify-between"><h3 className="font-bold">新建订单</h3><button type="button" onClick={() => { setShow(false); navigate("/orders"); }} className="text-sm text-slate-600">取消</button></div>
      <label>订单号<input required placeholder="例如 SO-20260819-1" value={form.order_no} onChange={(event) => setForm({ ...form, order_no: event.target.value })} className="mt-1 w-full rounded border px-3 py-2" /></label>
      <label>客户<select required value={form.customer_id || ""} onChange={(event) => setForm({ ...form, customer_id: Number(event.target.value), opportunity_id: undefined, quotation_id: undefined })} className="mt-1 w-full rounded border px-3 py-2"><option value="">选择客户</option>{customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.company_name || customer.contact_name}</option>)}</select></label>
      <label>订单日期<input required type="date" value={form.order_date} onChange={(event) => setForm({ ...form, order_date: event.target.value })} className="mt-1 w-full rounded border px-3 py-2" /></label>
      <label>关联商机（可选）<select value={form.opportunity_id ?? ""} disabled={!form.customer_id} onChange={(event) => setForm({ ...form, opportunity_id: event.target.value ? Number(event.target.value) : undefined })} className="mt-1 w-full rounded border px-3 py-2 disabled:bg-slate-100"><option value="">不关联商机</option>{opportunities.map((opportunity) => <option key={opportunity.id} value={opportunity.id}>{opportunity.name}（{opportunity.deal_stage}）</option>)}</select></label>
      <label>关联报价（可选）<select value={form.quotation_id ?? ""} disabled={!form.customer_id} onChange={(event) => { const quotationId = event.target.value ? Number(event.target.value) : undefined; const quotation = quotations.find((item) => item.id === quotationId); setForm({ ...form, quotation_id: quotationId, opportunity_id: quotation?.opportunity_id ?? form.opportunity_id }); }} className="mt-1 w-full rounded border px-3 py-2 disabled:bg-slate-100"><option value="">不关联报价</option>{quotations.map((quotation) => <option key={quotation.id} value={quotation.id}>{quotation.quotation_number} · {quotation.currency} {quotation.total_amount}</option>)}</select></label>
      <label>币种<input required maxLength={3} value={form.currency} onChange={(event) => setForm({ ...form, currency: event.target.value.toUpperCase() })} className="mt-1 w-full rounded border px-3 py-2" /></label>
      <label>订单金额<input required type="number" min="0" step="0.01" value={form.order_amount} onChange={(event) => setForm({ ...form, order_amount: event.target.value })} className="mt-1 w-full rounded border px-3 py-2" /></label>
      <label>付款状态<select value={form.payment_status ?? "Unpaid"} onChange={(event) => setForm({ ...form, payment_status: event.target.value as OrderPayload["payment_status"] })} className="mt-1 w-full rounded border px-3 py-2">{payment.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>生产状态<select value={form.production_status ?? "Not Started"} onChange={(event) => setForm({ ...form, production_status: event.target.value as OrderPayload["production_status"] })} className="mt-1 w-full rounded border px-3 py-2">{production.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>出货状态<select value={form.shipping_status ?? "Pending Shipment"} onChange={(event) => setForm({ ...form, shipping_status: event.target.value as OrderPayload["shipping_status"] })} className="mt-1 w-full rounded border px-3 py-2">{shipping.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>预计交货日期<input type="date" value={form.expected_delivery_date ?? ""} onChange={(event) => setForm({ ...form, expected_delivery_date: event.target.value || undefined })} className="mt-1 w-full rounded border px-3 py-2" /></label>
      <label>实际出货日期<input type="date" value={form.shipped_at ?? ""} onChange={(event) => setForm({ ...form, shipped_at: event.target.value || undefined })} className="mt-1 w-full rounded border px-3 py-2" /></label>
      <label className="md:col-span-3">备注<textarea value={form.notes ?? ""} onChange={(event) => setForm({ ...form, notes: event.target.value || undefined })} className="mt-1 w-full rounded border px-3 py-2" /></label>
      <button disabled={busy} className="w-fit rounded bg-slate-900 px-4 py-2 font-semibold text-white disabled:opacity-60">{busy ? "正在创建…" : "创建订单"}</button>
    </form>}
    <form onSubmit={(event) => { event.preventDefault(); setOffset(0); void loadOrders(filters, 0); }} className="mt-5 grid gap-2 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200 md:grid-cols-4">
      <input value={filters.q} onChange={(event) => setFilter("q", event.target.value)} placeholder="搜索订单号或客户" className="rounded border px-3 py-2" />
      <input type="date" value={filters.start_date} onChange={(event) => setFilter("start_date", event.target.value)} className="rounded border px-3 py-2" />
      <input type="date" value={filters.end_date} onChange={(event) => setFilter("end_date", event.target.value)} className="rounded border px-3 py-2" />
      <select value={filters.payment_status} onChange={(event) => setFilter("payment_status", event.target.value as Filters["payment_status"])} className="rounded border px-3 py-2"><option value="">全部付款状态</option>{payment.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
      <select value={filters.production_status} onChange={(event) => setFilter("production_status", event.target.value as Filters["production_status"])} className="rounded border px-3 py-2"><option value="">全部生产状态</option>{production.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
      <select value={filters.shipping_status} onChange={(event) => setFilter("shipping_status", event.target.value as Filters["shipping_status"])} className="rounded border px-3 py-2"><option value="">全部出货状态</option>{shipping.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
      <div className="flex gap-2"><button className="rounded border px-4 py-2">筛选</button><button type="button" onClick={() => { setFilters(emptyFilters); setOffset(0); void loadOrders(emptyFilters, 0); }} className="rounded border px-4 py-2">重置</button></div>
    </form>
    {customerId && <p className="mt-3 text-sm text-slate-500">正在显示该客户的订单。</p>}{error && <p className="mt-3 text-rose-600">{error}</p>}
    <div className="mt-5 overflow-x-auto rounded-xl bg-white shadow-sm ring-1 ring-slate-200"><table className="min-w-[1000px] w-full text-left text-sm"><thead className="bg-slate-50 text-slate-500"><tr>{["订单号", "客户", "日期", "金额", "付款", "生产", "出货", "利润", "负责人"].map((label) => <th key={label} className="px-4 py-3">{label}</th>)}</tr></thead><tbody>{data?.items.map((order) => <tr key={order.id} className="border-t"><td className="px-4 py-3"><Link className="text-blue-700" to={`/orders/${order.id}`}>{order.order_no}</Link></td><td className="px-4 py-3">{order.customer_company}</td><td className="px-4 py-3">{order.order_date}</td><td className="px-4 py-3">{order.currency} {order.order_amount}</td><td className="px-4 py-3">{payment.find(([value]) => value === order.payment_status)?.[1]}</td><td className="px-4 py-3">{production.find(([value]) => value === order.production_status)?.[1]}</td><td className="px-4 py-3">{shipping.find(([value]) => value === order.shipping_status)?.[1]}</td><td className="px-4 py-3">¥{order.profit}</td><td className="px-4 py-3">{order.owner_name ?? "—"}</td></tr>)}{data && !data.items.length && <tr><td colSpan={9} className="px-4 py-8 text-center text-slate-500">暂无匹配订单。</td></tr>}</tbody></table></div>
    {data && <div className="mt-4 flex items-center justify-between gap-3 text-sm text-slate-600"><span>共 {data.total} 个订单 · 第 {Math.floor(data.offset / data.limit) + 1} / {Math.max(1, Math.ceil(data.total / data.limit))} 页</span><div className="flex gap-2"><button type="button" disabled={offset === 0} onClick={() => { const next = Math.max(0, offset - data.limit); setOffset(next); void loadOrders(filters, next); }} className="rounded border px-3 py-1.5 disabled:opacity-40">上一页</button><button type="button" disabled={offset + data.limit >= data.total} onClick={() => { const next = offset + data.limit; setOffset(next); void loadOrders(filters, next); }} className="rounded border px-3 py-1.5 disabled:opacity-40">下一页</button></div></div>}
  </>;
}
