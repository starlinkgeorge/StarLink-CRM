import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import api from "../services/api";
import { getCustomers, type CustomerFilters } from "../services/crm";
import { useAuth } from "../store/auth";
import type { CustomerPage } from "../types";

const pageSize = 20;
type Filters = {
  q: string; source: string; country: string; customer_type: string; interested_product: string;
  followup_stage: string; response_status: string; followup_requirement: string; customer_level_value: string;
};
const blank: Filters = { q: "", source: "", country: "", customer_type: "", interested_product: "", followup_stage: "", response_status: "", followup_requirement: "", customer_level_value: "" };
const dash = (value: string | number | null | undefined) => value === null || value === undefined || value === "" ? "—" : value;

export function CustomerArchivePage() {
  const { user } = useAuth();
  const [filters, setFilters] = useState<Filters>(blank);
  const [active, setActive] = useState<Filters>(blank);
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<CustomerPage | null>(null);
  const [error, setError] = useState("");
  const [removing, setRemoving] = useState<number | null>(null);

  const load = useCallback(async (nextOffset = offset, nextFilters = active) => {
    const params: CustomerFilters = {
      limit: pageSize, offset: nextOffset,
      q: nextFilters.q || undefined, source: nextFilters.source || undefined,
      country: nextFilters.country || undefined, customer_type: nextFilters.customer_type || undefined,
      interested_product: nextFilters.interested_product || undefined,
      followup_stage: nextFilters.followup_stage || undefined,
      response_status: nextFilters.response_status || undefined,
      followup_requirement: nextFilters.followup_requirement || undefined,
      customer_level_value: nextFilters.customer_level_value ? Number(nextFilters.customer_level_value) : undefined,
    };
    try { setData(await getCustomers(params)); setError(""); }
    catch { setError("无法加载客户列表。请检查登录状态或稍后重试。"); }
  }, [active, offset]);

  useEffect(() => { void load(); }, [load]);
  const set = (key: keyof Filters, value: string) => setFilters((current) => ({ ...current, [key]: value }));
  function submit(event: FormEvent) { event.preventDefault(); setOffset(0); setActive(filters); }
  function reset() { setFilters(blank); setActive(blank); setOffset(0); }
  async function remove(id: number, company: string) {
    if (!window.confirm(`确定删除客户“${company}”吗？关联客户记录时系统会拒绝删除以保护数据。`)) return;
    setRemoving(id);
    try { await api.delete(`/customers/${id}`); await load(offset, active); }
    catch { setError("无法删除客户：该客户可能已关联商机、报价、询盘或跟进记录。"); }
    finally { setRemoving(null); }
  }

  return <>
    <div className="flex flex-wrap items-center justify-between gap-4"><div><p className="text-sm text-slate-500">客户档案表标准字段</p><h2 className="text-3xl font-bold">客户管理</h2></div>{user?.role !== "Viewer" && <Link to="/customers/new" className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white">新增客户</Link>}</div>
    <form onSubmit={submit} className="mt-6 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200"><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
      <input value={filters.q} onChange={(event) => set("q", event.target.value)} placeholder="客户、公司、邮箱、国家、电话或备注" className="rounded border px-3 py-2 xl:col-span-2" />
      <input value={filters.source} onChange={(event) => set("source", event.target.value)} placeholder="来源" className="rounded border px-3 py-2" />
      <input value={filters.country} onChange={(event) => set("country", event.target.value)} placeholder="国家" className="rounded border px-3 py-2" />
      <input value={filters.customer_type} onChange={(event) => set("customer_type", event.target.value)} placeholder="客户类型" className="rounded border px-3 py-2" />
      <input value={filters.interested_product} onChange={(event) => set("interested_product", event.target.value)} placeholder="兴趣产品" className="rounded border px-3 py-2" />
      <input value={filters.followup_stage} onChange={(event) => set("followup_stage", event.target.value)} placeholder="跟进阶段" className="rounded border px-3 py-2" />
      <input value={filters.response_status} onChange={(event) => set("response_status", event.target.value)} placeholder="是否回复" className="rounded border px-3 py-2" />
      <input value={filters.followup_requirement} onChange={(event) => set("followup_requirement", event.target.value)} placeholder="是否需要跟进" className="rounded border px-3 py-2" />
      <input type="number" min="0" value={filters.customer_level_value} onChange={(event) => set("customer_level_value", event.target.value)} placeholder="客户等级" className="rounded border px-3 py-2" />
    </div><div className="mt-3 flex gap-2"><button className="rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white">筛选</button><button type="button" onClick={reset} className="rounded border px-4 py-2 text-sm">重置</button></div></form>
    {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}
    <div className="mt-6 overflow-x-auto rounded-xl bg-white shadow-sm ring-1 ring-slate-200"><table className="min-w-[1300px] text-left text-sm"><thead className="bg-slate-50 text-slate-500"><tr><th className="px-4 py-3">客户名</th><th className="px-4 py-3">公司名</th><th className="px-4 py-3">国家</th><th className="px-4 py-3">来源</th><th className="px-4 py-3">客户类型</th><th className="px-4 py-3">兴趣产品</th><th className="px-4 py-3">客户等级</th><th className="px-4 py-3">客户总分</th><th className="px-4 py-3">跟进阶段</th><th className="px-4 py-3">最近跟进日期</th><th className="px-4 py-3">是否需要跟进</th>{user?.role === "Admin" && <th className="px-4 py-3">操作</th>}</tr></thead><tbody>
      {data?.items.map((customer) => <tr key={customer.id} className="border-t"><td className="px-4 py-3">{dash(customer.contact_name)}</td><td className="px-4 py-3 font-medium text-blue-700"><Link to={`/customers/${customer.id}`}>{customer.company_name}</Link></td><td className="px-4 py-3">{dash(customer.country)}</td><td className="px-4 py-3">{dash(customer.source)}</td><td className="px-4 py-3">{dash(customer.customer_type)}</td><td className="px-4 py-3">{dash(customer.interested_product)}</td><td className="px-4 py-3">{dash(customer.customer_level_value)}</td><td className="px-4 py-3">{dash(customer.customer_total_score)}</td><td className="px-4 py-3">{dash(customer.followup_stage)}</td><td className="px-4 py-3">{dash(customer.latest_followup_date?.slice(0, 10))}</td><td className="px-4 py-3">{dash(customer.followup_requirement)}</td>{user?.role === "Admin" && <td className="px-4 py-3"><button disabled={removing === customer.id} onClick={() => void remove(customer.id, customer.company_name)} className="text-rose-600 disabled:opacity-50">{removing === customer.id ? "删除中…" : "删除"}</button></td>}</tr>)}
      {data?.items.length === 0 && <tr><td colSpan={12} className="px-4 py-12 text-center text-slate-500">没有匹配的客户。</td></tr>}
    </tbody></table></div>
    <div className="mt-4 flex justify-between text-sm"><span className="text-slate-500">共 {data?.total ?? 0} 位客户</span><div className="flex gap-2"><button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - pageSize))} className="rounded border px-3 py-1 disabled:opacity-40">上一页</button><button disabled={!data || offset + pageSize >= data.total} onClick={() => setOffset(offset + pageSize)} className="rounded border px-3 py-1 disabled:opacity-40">下一页</button></div></div>
  </>;
}
