import { useCallback, useState, type KeyboardEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { createQuotation, getCustomers } from "../services/crm";
import { useAuth } from "../store/auth";
import type { Customer } from "../types";

function customerLabel(customer: Customer) {
  return customer.company_name || customer.contact_name || `客户 #${customer.id}`;
}

export function QuotationCreatePage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [customerQuery, setCustomerQuery] = useState("");
  const [customerResults, setCustomerResults] = useState<Customer[]>([]);
  const [customerSearching, setCustomerSearching] = useState(false);
  const [customerSearched, setCustomerSearched] = useState(false);
  const [creatingCustomerId, setCreatingCustomerId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const editable = user?.role !== "Viewer";

  const createDraft = useCallback(async (customerId: number) => {
    if (!editable) return;
    setCreatingCustomerId(customerId);
    setError("");
    try {
      const quotation = await createQuotation({ customer_id: customerId });
      navigate(`/quotations/${quotation.id}`, {
        replace: true,
        state: { notice: "报价草稿已创建，请在此添加产品并填写付款、交期和运费。" },
      });
    } catch {
      setError("无法创建报价草稿，请确认客户存在且您有管理权限后重试。");
    } finally {
      setCreatingCustomerId(null);
    }
  }, [editable, navigate]);

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

  return (
    <>
      <Link to="/quotations" className="text-sm text-blue-700">← 返回报价管理</Link>
      <div className="mt-4">
        <p className="text-sm text-slate-500">报价管理</p>
        <h2 className="text-3xl font-bold">选择客户</h2>
        <p className="mt-1 text-sm text-slate-500">选择客户后将直接进入正式报价编辑页，在那里填写产品、价格、付款条款、交期和运费。</p>
      </div>
      {error && <p className="mt-4 text-sm text-rose-600" role="alert">{error}</p>}
      {!editable && <p className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">Viewer 账户只读，不能创建报价。</p>}

      <section className="mt-6 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <h3 className="font-bold">报价客户</h3>
          <p className="mt-1 text-sm text-slate-500">搜索并选择客户后，系统会创建空白报价草稿并跳转至正式编辑页。</p>
          <div className="mt-4 flex gap-2">
            <input value={customerQuery} onChange={(event) => setCustomerQuery(event.target.value)} onKeyDown={(event: KeyboardEvent<HTMLInputElement>) => { if (event.key === "Enter") { event.preventDefault(); void searchCustomers(); } }} disabled={!editable || customerSearching || creatingCustomerId !== null} placeholder="搜索客户名、公司名、国家或邮箱" className="min-w-0 flex-1 rounded border px-3 py-2" />
            <button type="button" onClick={() => void searchCustomers()} disabled={!editable || customerSearching || !customerQuery.trim() || creatingCustomerId !== null} className="rounded bg-slate-800 px-4 py-2 font-medium text-white disabled:opacity-50">{customerSearching ? "搜索中…" : "搜索客户"}</button>
          </div>
          {customerSearched && !customerSearching && <div className="mt-3 overflow-hidden rounded-lg border"><p className="border-b bg-slate-50 px-3 py-2 text-sm font-medium">客户搜索结果</p>{customerResults.map((result) => <button key={result.id} type="button" onClick={() => void createDraft(result.id)} disabled={!editable || creatingCustomerId !== null} className="block w-full border-b px-3 py-2 text-left last:border-b-0 hover:bg-blue-50 disabled:opacity-50"><span className="font-medium">{customerLabel(result)}</span><span className="ml-2 text-sm text-slate-500">{result.contact_name ?? "—"} · {result.country ?? "—"}</span>{creatingCustomerId === result.id && <span className="ml-2 text-sm text-blue-700">正在创建…</span>}</button>)}{!customerResults.length && <p className="px-3 py-4 text-sm text-slate-500">未找到匹配客户</p>}</div>}
      </section>
    </>
  );
}
