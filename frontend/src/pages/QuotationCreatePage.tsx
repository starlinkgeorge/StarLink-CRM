import { useEffect, useMemo, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { QuotationProductPicker } from "../components/QuotationProductPicker";
import { createQuotation, getCustomerCenter, getCustomers } from "../services/crm";
import { useAuth } from "../store/auth";
import type { Customer, CustomerCenter, Product } from "../types";

type DraftLine = { product: Product; unitPrice: string; quantity: string };

const defaultPaymentTerm = "30% deposit, balance before shipment";
const defaultDeliveryTime = "30-45 days after deposit";

function customerLabel(customer: Customer) {
  return customer.company_name || customer.contact_name || `客户 #${customer.id}`;
}

export function QuotationCreatePage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [customer, setCustomer] = useState<CustomerCenter | null>(null);
  const [customerQuery, setCustomerQuery] = useState("");
  const [customerResults, setCustomerResults] = useState<Customer[]>([]);
  const [customerSearching, setCustomerSearching] = useState(false);
  const [customerSearched, setCustomerSearched] = useState(false);
  const [customerLoading, setCustomerLoading] = useState(false);
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [currency, setCurrency] = useState("USD");
  const [paymentTerm, setPaymentTerm] = useState(defaultPaymentTerm);
  const [deliveryTime, setDeliveryTime] = useState(defaultDeliveryTime);
  const [validityDays, setValidityDays] = useState(30);
  const [shippingCost, setShippingCost] = useState("0");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const editable = user?.role !== "Viewer";
  const requestedCustomerId = searchParams.get("customer_id");
  const subtotal = useMemo(() => lines.reduce(
    (total, line) => total + (Number(line.unitPrice) || 0) * (Number(line.quantity) || 0),
    0,
  ), [lines]);
  const total = subtotal + (Number(shippingCost) || 0);

  useEffect(() => {
    if (!requestedCustomerId) {
      setCustomer(null);
      setCustomerLoading(false);
      return;
    }
    let cancelled = false;
    setCustomer(null);
    setCustomerLoading(true);
    void getCustomerCenter(requestedCustomerId)
      .then((result) => {
        if (cancelled) return;
        setCustomer(result);
        setCustomerQuery("");
        setCustomerResults([]);
        setError("");
      })
      .catch(() => {
        if (!cancelled) {
          setCustomer(null);
          setError("无法加载已选择的客户，请重新搜索并选择客户。");
        }
      })
      .finally(() => {
        if (!cancelled) setCustomerLoading(false);
      });
    return () => { cancelled = true; };
  }, [requestedCustomerId]);

  async function searchCustomers() {
    const query = customerQuery.trim();
    if (!query) {
      setCustomerResults([]);
      setCustomerSearched(false);
      return;
    }
    setCustomerSearching(true);
    setCustomerSearched(true);
    setError("");
    try {
      const page = await getCustomers({ limit: 10, offset: 0, q: query });
      setCustomerResults(page.items);
    } catch {
      setCustomerResults([]);
      setError("无法搜索客户，请稍后重试。");
    } finally {
      setCustomerSearching(false);
    }
  }

  function selectCustomer(result: Customer) {
    navigate(`/quotations/new?customer_id=${result.id}`);
  }

  function addProducts(products: Product[]) {
    setLines((current) => {
      const existingIds = new Set(current.map((line) => line.product.id));
      const additions = products
        .filter((product) => !existingIds.has(product.id))
        .map((product) => ({ product, unitPrice: product.reference_price ?? "0", quantity: "1" }));
      return additions.length ? [...current, ...additions] : current;
    });
  }

  function updateLine(index: number, field: "unitPrice" | "quantity", value: string) {
    setLines((current) => current.map((line, lineIndex) => (
      lineIndex === index ? { ...line, [field]: value } : line
    )));
  }

  async function saveQuotation(event: FormEvent) {
    event.preventDefault();
    if (!customer || !editable) {
      setError("请先选择客户。");
      return;
    }
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
        items: lines.map((line) => ({ product_id: line.product.id, unit_price: line.unitPrice, quantity: line.quantity })),
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

  return (
    <>
      <Link to={customer ? `/customers/${customer.id}` : "/quotations"} className="text-sm text-blue-700">
        ← {customer ? "返回客户详情" : "返回报价管理"}
      </Link>
      <div className="mt-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">报价管理</p>
          <h2 className="text-3xl font-bold">创建报价</h2>
        </div>
        {customer && <span className="rounded-full bg-blue-100 px-3 py-1 text-sm text-blue-700">客户已自动关联</span>}
      </div>

      {error && <p className="mt-4 text-sm text-rose-600" role="alert">{error}</p>}
      {!editable && <p className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">Viewer 账户只读，不能创建报价。</p>}

      <section className="mt-6 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-bold">报价客户</h3>
            <p className="mt-1 text-sm text-slate-500">从客户详情进入时已自动选择客户；也可以在这里搜索并选择客户。</p>
          </div>
          {customer && <button type="button" onClick={() => navigate("/quotations/new")} disabled={!editable} className="rounded border px-3 py-1.5 text-sm text-blue-700 disabled:opacity-50">更换客户</button>}
        </div>
        {customerLoading && <p className="mt-4 text-sm text-slate-500">正在加载客户…</p>}
        {customer && !customerLoading && <div className="mt-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3"><p className="font-semibold text-slate-900">{customer.company_name}</p><p className="mt-1 text-sm text-slate-600">{customer.contact_name ?? "未设置联系人"} · {customer.email ?? "未填写邮箱"} · {customer.whatsapp ?? "未填写 WhatsApp"}</p></div>}
        {!customer && !customerLoading && <div className="mt-4"><div className="flex gap-2"><input value={customerQuery} onChange={(event) => setCustomerQuery(event.target.value)} onKeyDown={(event: KeyboardEvent<HTMLInputElement>) => { if (event.key === "Enter") { event.preventDefault(); void searchCustomers(); } }} disabled={!editable || customerSearching} placeholder="搜索客户名、公司名、国家或邮箱" className="min-w-0 flex-1 rounded border px-3 py-2" /><button type="button" onClick={() => void searchCustomers()} disabled={!editable || customerSearching || !customerQuery.trim()} className="rounded bg-slate-800 px-4 py-2 font-medium text-white disabled:opacity-50">{customerSearching ? "搜索中…" : "搜索客户"}</button></div>{customerSearched && !customerSearching && <div className="mt-3 overflow-hidden rounded-lg border"><p className="border-b bg-slate-50 px-3 py-2 text-sm font-medium">客户搜索结果</p>{customerResults.map((result) => <button key={result.id} type="button" onClick={() => selectCustomer(result)} className="block w-full border-b px-3 py-2 text-left last:border-b-0 hover:bg-blue-50"><span className="font-medium">{customerLabel(result)}</span><span className="ml-2 text-sm text-slate-500">{result.contact_name ?? "—"} · {result.country ?? "—"}</span></button>)}{!customerResults.length && <p className="px-3 py-4 text-sm text-slate-500">未找到匹配客户</p>}</div>}</div>}
      </section>

      <form onSubmit={saveQuotation} className="mt-6 space-y-5">
        <section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5"><label className="text-sm font-medium">币种<select value={currency} onChange={(event) => setCurrency(event.target.value)} disabled={!editable} className="mt-1 w-full rounded border px-3 py-2"><option value="USD">USD</option><option value="EUR">EUR</option><option value="CNY">CNY</option></select></label><label className="text-sm font-medium">有效期（天）<input type="number" min="1" max="365" value={validityDays} onChange={(event) => setValidityDays(Number(event.target.value) || 1)} disabled={!editable} className="mt-1 w-full rounded border px-3 py-2" /></label><label className="text-sm font-medium md:col-span-2">付款条款<input value={paymentTerm} onChange={(event) => setPaymentTerm(event.target.value)} disabled={!editable} required className="mt-1 w-full rounded border px-3 py-2" /></label><label className="text-sm font-medium">门到门运费<input type="number" min="0" step="0.01" value={shippingCost} onChange={(event) => setShippingCost(event.target.value)} disabled={!editable} className="mt-1 w-full rounded border px-3 py-2" /></label><label className="text-sm font-medium md:col-span-2">交期<input value={deliveryTime} onChange={(event) => setDeliveryTime(event.target.value)} disabled={!editable} required className="mt-1 w-full rounded border px-3 py-2" /></label></div></section>

        <section className="space-y-4 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-bold">报价产品</h3><p className="mt-1 text-sm text-slate-500">搜索、勾选并一次性添加多个产品；单价和数量可在保存前修改。</p></div><p className="text-sm font-semibold">Subtotal: {currency} {subtotal.toFixed(2)} / Amount: {currency} {total.toFixed(2)}</p></div><QuotationProductPicker disabled={!editable || !customer} selectedProductIds={lines.map((line) => line.product.id)} onAddProducts={addProducts} /><div className="overflow-x-auto rounded-lg border border-slate-200"><table className="min-w-[880px] w-full text-sm"><thead className="bg-slate-100 text-left"><tr><th className="p-3">图片</th><th className="p-3">产品</th><th className="p-3">SKU</th><th className="p-3">Unit Price</th><th className="p-3">QTY</th><th className="p-3 text-right">Total Price</th><th className="p-3">操作</th></tr></thead><tbody>{lines.map((line, index) => { const image = line.product.images.find((item) => item.is_primary) ?? line.product.images[0]; return <tr key={line.product.id} className="border-t"><td className="p-3">{image ? <img src={image.image_url} alt="" className="h-12 w-12 rounded object-cover" /> : <span className="text-xs text-slate-400">No image</span>}</td><td className="p-3 font-medium">{line.product.name}</td><td className="p-3 font-mono text-slate-500">{line.product.sku}</td><td className="p-3"><input type="number" min="0" step="0.01" value={line.unitPrice} onChange={(event) => updateLine(index, "unitPrice", event.target.value)} disabled={!editable} className="w-28 rounded border px-2 py-1" /></td><td className="p-3"><input type="number" min="0.01" step="0.01" value={line.quantity} onChange={(event) => updateLine(index, "quantity", event.target.value)} disabled={!editable} className="w-24 rounded border px-2 py-1" /></td><td className="p-3 text-right">{currency} {((Number(line.unitPrice) || 0) * (Number(line.quantity) || 0)).toFixed(2)}</td><td className="p-3"><button type="button" onClick={() => setLines((current) => current.filter((_, lineIndex) => lineIndex !== index))} disabled={!editable} className="text-rose-600 disabled:opacity-50">删除</button></td></tr>; })}{!lines.length && <tr><td colSpan={7} className="p-8 text-center text-slate-500">请先选择客户，再搜索并添加产品。</td></tr>}</tbody></table></div></section>
        <div className="flex justify-end gap-3"><Link to={customer ? `/customers/${customer.id}` : "/quotations"} className="rounded border px-4 py-2">取消</Link><button type="submit" disabled={!editable || saving || customerLoading || !customer} className="rounded bg-blue-700 px-5 py-2 font-medium text-white disabled:opacity-50">{saving ? "正在创建…" : "创建报价"}</button></div>
      </form>
    </>
  );
}
