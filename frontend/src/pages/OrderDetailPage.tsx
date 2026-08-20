import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { deleteOrder, getOrder, updateOrder, type OrderPayload } from "../services/crm";
import { useAuth } from "../store/auth";
import type { Order } from "../types";

const payment = [["Unpaid", "未付款"], ["Deposit Received", "已收定金"], ["Paid in Full", "已收全款"]] as const;
const production = [["Not Started", "未开始"], ["In Production", "生产中"], ["Completed", "已完成"]] as const;
const shipping = [["Pending Shipment", "待出货"], ["Shipped", "已出货"], ["Delivered", "已签收"]] as const;

export function OrderDetailPage() {
  const { id } = useParams(); const { user } = useAuth(); const navigate = useNavigate();
  const [order, setOrder] = useState<Order | null>(null); const [error, setError] = useState(""); const [saving, setSaving] = useState(false);
  useEffect(() => { if (id) void getOrder(id).then(setOrder).catch(() => setError("无法加载订单。")); }, [id]);
  if (!order) return <p>{error || "加载中…"}</p>;
  const editable = user?.role !== "Viewer";
  const set = <K extends keyof Order>(key: K, value: Order[K]) => setOrder({ ...order, [key]: value });
  async function save(event: FormEvent) {
    event.preventDefault(); setSaving(true);
    const current = order;
    if (!current) { setSaving(false); return; }
    const payload: Partial<OrderPayload> = { order_no: current.order_no, order_date: current.order_date, currency: current.currency, order_amount: current.order_amount, payment_status: current.payment_status, production_status: current.production_status, shipping_status: current.shipping_status, expected_delivery_date: current.expected_delivery_date ?? undefined, shipped_at: current.shipped_at ?? undefined, notes: current.notes ?? undefined, rmb_received_amount: current.rmb_received_amount, purchase_cost: current.purchase_cost, freight_cost: current.freight_cost };
    try { setOrder(await updateOrder(current.id, payload)); setError(""); } catch { setError("保存失败，请检查金额和状态。"); } finally { setSaving(false); }
  }
  return <>
    <Link className="text-blue-700" to="/orders">← 返回订单列表</Link>
    <div className="mt-4 flex flex-wrap justify-between gap-3"><div><h2 className="text-3xl font-bold">{order.order_no}</h2><p className="text-slate-500"><Link className="text-blue-700" to={`/customers/${order.customer_id}`}>{order.customer_company}</Link> · {order.order_date}{order.opportunity_id && <> · <Link className="text-blue-700" to={`/opportunities/${order.opportunity_id}`}>关联商机</Link></>}{order.quotation_id && <> · <Link className="text-blue-700" to={`/quotations/${order.quotation_id}`}>关联报价</Link></>}</p></div>{user?.role === "Admin" && <button type="button" onClick={async () => { if (confirm("确认删除该订单？订单利润记录将一并删除。")) { try { await deleteOrder(order.id); navigate("/orders"); } catch { setError("无法删除订单。请稍后重试。"); } } }} className="text-rose-600">删除订单</button>}</div>
    {error && <p className="mt-3 text-rose-600">{error}</p>}
    <form onSubmit={save} className="mt-6 grid gap-5 lg:grid-cols-2">
      <section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><h3 className="font-bold">订单基本信息</h3><div className="mt-4 grid gap-3"><label>订单金额<input disabled={!editable} type="number" min="0" step="0.01" value={order.order_amount} onChange={(event) => set("order_amount", event.target.value)} className="mt-1 w-full rounded border px-3 py-2" /></label><label>币种<input disabled={!editable} maxLength={3} value={order.currency} onChange={(event) => set("currency", event.target.value.toUpperCase())} className="mt-1 w-full rounded border px-3 py-2" /></label><label>订单日期<input disabled={!editable} type="date" value={order.order_date} onChange={(event) => set("order_date", event.target.value)} className="mt-1 w-full rounded border px-3 py-2" /></label><label>备注<textarea disabled={!editable} value={order.notes ?? ""} onChange={(event) => set("notes", event.target.value || null)} className="mt-1 w-full rounded border px-3 py-2" /></label></div></section>
      <section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><h3 className="font-bold">履约与利润核算</h3><p className="mt-1 text-sm text-slate-500">人民币实收由人工录入，不使用实时汇率自动覆盖；三项任一留空即为待核算，不计入利润分析。</p><div className="mt-4 grid gap-3"><label>付款状态<select disabled={!editable} value={order.payment_status} onChange={(event) => set("payment_status", event.target.value as Order["payment_status"])} className="mt-1 w-full rounded border px-3 py-2">{payment.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>生产状态<select disabled={!editable} value={order.production_status} onChange={(event) => set("production_status", event.target.value as Order["production_status"])} className="mt-1 w-full rounded border px-3 py-2">{production.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>出货状态<select disabled={!editable} value={order.shipping_status} onChange={(event) => set("shipping_status", event.target.value as Order["shipping_status"])} className="mt-1 w-full rounded border px-3 py-2">{shipping.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>预计交货日期<input disabled={!editable} type="date" value={order.expected_delivery_date ?? ""} onChange={(event) => set("expected_delivery_date", event.target.value || null)} className="mt-1 w-full rounded border px-3 py-2" /></label><label>实际出货日期<input disabled={!editable} type="date" value={order.shipped_at ?? ""} onChange={(event) => set("shipped_at", event.target.value || null)} className="mt-1 w-full rounded border px-3 py-2" /></label>{[["rmb_received_amount", "人民币实收"], ["purchase_cost", "采购金额"], ["freight_cost", "运费"]].map(([field, label]) => <label key={field}>{label}<input disabled={!editable} type="number" min="0" step="0.01" value={(order[field as keyof Order] as string | null) ?? ""} onChange={(event) => set(field as keyof Order, (event.target.value || null) as never)} className="mt-1 w-full rounded border px-3 py-2" /></label>)}<p className="rounded bg-slate-50 p-3 font-semibold">{order.profit_accounting_status === "Pending" ? "待核算：请补全人民币实收、采购金额和运费。" : <>利润：¥{order.profit}, 利润率：{order.profit_margin ?? "—"}%, 实际汇率：{order.realized_exchange_rate ?? "—"}</>}</p></div></section>
      {editable && <button disabled={saving} className="w-fit rounded bg-blue-700 px-4 py-2 font-semibold text-white disabled:opacity-60">{saving ? "正在保存…" : "保存订单"}</button>}
    </form>
  </>;
}
