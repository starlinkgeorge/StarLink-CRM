import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  createQuotation,
  getCustomerCenter,
  getProducts,
} from "../services/crm";
import { useAuth } from "../store/auth";
import type { CustomerCenter, Product } from "../types";

type DraftLine = {
  product: Product;
  unitPrice: string;
  quantity: string;
};

const defaultPaymentTerm = "30% deposit, balance before shipment";
const defaultDeliveryTime = "30-45 days after deposit";

function money(value: string) {
  const amount = Number(value);
  return Number.isFinite(amount) ? amount.toFixed(2) : "0.00";
}

export function CustomerQuotationCreatePage() {
  const { customerId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [customer, setCustomer] = useState<CustomerCenter | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [productQuery, setProductQuery] = useState("");
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [currency, setCurrency] = useState("USD");
  const [paymentTerm, setPaymentTerm] = useState(defaultPaymentTerm);
  const [deliveryTime, setDeliveryTime] = useState(defaultDeliveryTime);
  const [validityDays, setValidityDays] = useState(30);
  const [shippingCost, setShippingCost] = useState("0");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const subtotal = useMemo(
    () => lines.reduce((total, line) => total + (Number(line.unitPrice) || 0) * (Number(line.quantity) || 0), 0),
    [lines],
  );
  const total = subtotal + (Number(shippingCost) || 0);
  const editable = user?.role !== "Viewer";

  useEffect(() => {
    if (!customerId) return;
    void getCustomerCenter(customerId)
      .then((result) => {
        setCustomer(result);
        setError("");
      })
      .catch(() => setError("无法加载客户信息。"));
  }, [customerId]);

  useEffect(() => {
    const query = productQuery.trim();
    if (!query) {
      setProducts([]);
      return undefined;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void getProducts({ limit: 20, offset: 0, q: query, is_active: true })
        .then((result) => {
          if (!cancelled) setProducts(result.items);
        })
        .catch(() => {
          if (!cancelled) setError("无法搜索产品库。");
        });
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [productQuery]);

  function addProduct(product: Product) {
    if (lines.some((line) => line.product.id === product.id)) return;
    setLines((current) => [
      ...current,
      { product, unitPrice: product.reference_price ?? "0", quantity: "1" },
    ]);
  }

  function updateLine(index: number, field: "unitPrice" | "quantity", value: string) {
    setLines((current) => current.map((line, lineIndex) => (
      lineIndex === index ? { ...line, [field]: value } : line
    )));
  }

  function removeLine(index: number) {
    setLines((current) => current.filter((_, lineIndex) => lineIndex !== index));
  }

  async function saveQuotation(event: FormEvent) {
    event.preventDefault();
    if (!customer || !editable) return;
    if (!lines.length) {
      setError("请至少添加一个报价产品。");
      return;
    }
    if (lines.some((line) => !Number.isFinite(Number(line.unitPrice)) || Number(line.unitPrice) < 0 || !Number.isFinite(Number(line.quantity)) || Number(line.quantity) <= 0)) {
      setError("请填写有效的单价和数量。");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const quotation = await createQuotation({
        customer_id: customer.id,
        currency,
        payment_term: paymentTerm,
        delivery_time: deliveryTime,
        validity_days: validityDays,
        shipping_cost: shippingCost,
        items: lines.map((line) => ({
          product_id: line.product.id,
          unit_price: line.unitPrice,
          quantity: line.quantity,
        })),
      });
      navigate(`/quotations/${quotation.id}`, {
        state: { notice: "报价创建成功，已自动创建或关联商机。" },
        replace: true,
      });
    } catch {
      setError("无法创建报价，请检查产品、价格和条款后重试。");
    } finally {
      setSaving(false);
    }
  }

  if (!customer) return <p className="text-slate-500">{error || "加载中…"}</p>;

  return (
    <>
      <Link to={`/customers/${customer.id}`} className="text-sm text-blue-700">← 返回客户详情</Link>
      <div className="mt-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">客户报价</p>
          <h2 className="text-3xl font-bold">为 {customer.company_name} 创建报价</h2>
          <p className="mt-1 text-sm text-slate-600">
            {customer.contact_name ?? "未设置联系人"} · {customer.email ?? "未填写邮箱"} · {customer.whatsapp ?? "未填写 WhatsApp"}
          </p>
        </div>
        <span className="rounded-full bg-blue-100 px-3 py-1 text-sm text-blue-700">客户已自动关联</span>
      </div>

      {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}
      {!editable && <p className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">Viewer 账号只读，不能创建报价。</p>}

      <form onSubmit={saveQuotation} className="mt-6 space-y-5">
        <section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            <label className="text-sm font-medium">币种<select value={currency} onChange={(event) => setCurrency(event.target.value)} disabled={!editable} className="mt-1 w-full rounded border px-3 py-2"><option value="USD">USD</option><option value="EUR">EUR</option><option value="CNY">CNY</option></select></label>
            <label className="text-sm font-medium">有效期（天）<input type="number" min="1" max="365" value={validityDays} onChange={(event) => setValidityDays(Number(event.target.value) || 1)} disabled={!editable} className="mt-1 w-full rounded border px-3 py-2" /></label>
            <label className="text-sm font-medium md:col-span-2">付款条款<input value={paymentTerm} onChange={(event) => setPaymentTerm(event.target.value)} disabled={!editable} required className="mt-1 w-full rounded border px-3 py-2" /></label>
            <label className="text-sm font-medium">门到门运费<input type="number" min="0" step="0.01" value={shippingCost} onChange={(event) => setShippingCost(event.target.value)} disabled={!editable} className="mt-1 w-full rounded border px-3 py-2" /></label>
            <label className="text-sm font-medium md:col-span-2">交期<input value={deliveryTime} onChange={(event) => setDeliveryTime(event.target.value)} disabled={!editable} required className="mt-1 w-full rounded border px-3 py-2" /></label>
          </div>
        </section>

        <section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-bold">报价产品</h3><p className="mt-1 text-sm text-slate-500">从产品库搜索并添加；价格和数量可在保存前调整。</p></div><p className="text-sm font-semibold">合计：{currency} {total.toFixed(2)}</p></div>
          <label className="mt-4 block text-sm font-medium">搜索产品（SKU、名称或材质）<input value={productQuery} onChange={(event) => setProductQuery(event.target.value)} disabled={!editable} placeholder="输入关键词后直接显示搜索结果" className="mt-1 w-full rounded border px-3 py-2" /></label>
          {productQuery.trim() && <div className="mt-2 max-h-64 overflow-y-auto rounded border bg-slate-50">{products.length ? products.map((product) => <button type="button" key={product.id} onClick={() => addProduct(product)} disabled={!editable || lines.some((line) => line.product.id === product.id)} className="flex w-full items-center justify-between gap-3 border-b px-3 py-2 text-left text-sm last:border-b-0 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"><span><strong>{product.name}</strong><span className="ml-2 text-slate-500">{product.sku}</span></span><span>{product.currency_code} {money(product.reference_price ?? "0")}</span></button>) : <p className="p-3 text-sm text-slate-500">没有匹配产品。</p>}</div>}

          <div className="mt-5 overflow-x-auto"><table className="min-w-[760px] w-full text-sm"><thead className="bg-slate-100 text-left"><tr><th className="p-3">产品</th><th className="p-3">SKU</th><th className="p-3">单价</th><th className="p-3">数量</th><th className="p-3 text-right">小计</th><th className="p-3">操作</th></tr></thead><tbody>{lines.map((line, index) => <tr key={line.product.id} className="border-b"><td className="p-3 font-medium">{line.product.name}</td><td className="p-3 text-slate-500">{line.product.sku}</td><td className="p-3"><input type="number" min="0" step="0.01" value={line.unitPrice} onChange={(event) => updateLine(index, "unitPrice", event.target.value)} disabled={!editable} className="w-28 rounded border px-2 py-1" /></td><td className="p-3"><input type="number" min="0.01" step="0.01" value={line.quantity} onChange={(event) => updateLine(index, "quantity", event.target.value)} disabled={!editable} className="w-24 rounded border px-2 py-1" /></td><td className="p-3 text-right">{currency} {((Number(line.unitPrice) || 0) * (Number(line.quantity) || 0)).toFixed(2)}</td><td className="p-3"><button type="button" onClick={() => removeLine(index)} disabled={!editable} className="text-rose-600 disabled:opacity-50">移除</button></td></tr>)}{!lines.length && <tr><td colSpan={6} className="p-6 text-center text-slate-500">请先搜索并添加产品。</td></tr>}</tbody></table></div>
        </section>

        <div className="flex justify-end gap-3"><Link to={`/customers/${customer.id}`} className="rounded border px-4 py-2">取消</Link><button type="submit" disabled={!editable || saving} className="rounded bg-blue-700 px-5 py-2 font-medium text-white disabled:opacity-50">{saving ? "正在创建…" : "创建报价"}</button></div>
      </form>
    </>
  );
}
