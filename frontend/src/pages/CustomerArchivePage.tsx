import { useCallback, useEffect, useRef, useState, type FormEvent, type UIEvent } from "react";
import { Link } from "react-router-dom";

import api from "../services/api";
import { getCustomers, type CustomerFilters } from "../services/crm";
import { useAuth } from "../store/auth";
import type { CustomerPage } from "../types";

const pageSize = 10;
const tableWidthClass = "min-w-[2780px]";

type Filters = {
  q: string; source: string; country: string; customer_type: string; interested_product: string;
  followup_stage: string; response_status: string; followup_requirement: string; customer_level_value: string;
};

const blank: Filters = {
  q: "", source: "", country: "", customer_type: "", interested_product: "", followup_stage: "",
  response_status: "", followup_requirement: "", customer_level_value: "",
};

const dash = (value: string | number | null | undefined) => value === null || value === undefined || value === "" ? "—" : value;
const dateOnly = (value: string | null | undefined) => value ? value.slice(0, 10) : "—";
const noteSummary = (value: string | null | undefined) => {
  const note = value?.trim();
  if (!note) return "—";
  const characters = Array.from(note);
  return characters.length > 50 ? `${characters.slice(0, 50).join("")}…` : note;
};

function visiblePages(currentPage: number, totalPages: number): Array<number | string> {
  const candidates = new Set<number>([1, totalPages, currentPage - 1, currentPage, currentPage + 1]);
  if (currentPage <= 3) [2, 3, 4].forEach((page) => candidates.add(page));
  if (currentPage >= totalPages - 2) [totalPages - 3, totalPages - 2, totalPages - 1].forEach((page) => candidates.add(page));

  const pages = [...candidates].filter((page) => page >= 1 && page <= totalPages).sort((a, b) => a - b);
  const result: Array<number | string> = [];
  let previous = 0;
  for (const page of pages) {
    if (page - previous > 1) result.push(`ellipsis-${previous}`);
    result.push(page);
    previous = page;
  }
  return result;
}

export function CustomerArchivePage() {
  const { user } = useAuth();
  const [filters, setFilters] = useState<Filters>(blank);
  const [active, setActive] = useState<Filters>(blank);
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<CustomerPage | null>(null);
  const [error, setError] = useState("");
  const [jumpPage, setJumpPage] = useState("");
  const [jumpError, setJumpError] = useState("");
  const [removing, setRemoving] = useState<number | null>(null);
  const topScrollRef = useRef<HTMLDivElement>(null);
  const tableScrollRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async (nextOffset = offset, nextFilters = active) => {
    const params: CustomerFilters = {
      limit: pageSize,
      offset: nextOffset,
      q: nextFilters.q || undefined,
      source: nextFilters.source || undefined,
      country: nextFilters.country || undefined,
      customer_type: nextFilters.customer_type || undefined,
      interested_product: nextFilters.interested_product || undefined,
      followup_stage: nextFilters.followup_stage || undefined,
      response_status: nextFilters.response_status || undefined,
      followup_requirement: nextFilters.followup_requirement || undefined,
      customer_level_value: nextFilters.customer_level_value ? Number(nextFilters.customer_level_value) : undefined,
    };
    try {
      setData(await getCustomers(params));
      setError("");
    } catch {
      setError("无法加载客户列表。请检查登录状态或稍后重试。");
    }
  }, [active, offset]);

  useEffect(() => { void load(); }, [load]);

  const set = (key: keyof Filters, value: string) => setFilters((current) => ({ ...current, [key]: value }));
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / pageSize));
  const currentPage = Math.min(totalPages, Math.floor(offset / pageSize) + 1);

  function syncHorizontalScroll(source: HTMLDivElement, target: HTMLDivElement | null) {
    if (target && target.scrollLeft !== source.scrollLeft) target.scrollLeft = source.scrollLeft;
  }

  function handleTopScroll(event: UIEvent<HTMLDivElement>) {
    syncHorizontalScroll(event.currentTarget, tableScrollRef.current);
  }

  function handleTableScroll(event: UIEvent<HTMLDivElement>) {
    syncHorizontalScroll(event.currentTarget, topScrollRef.current);
  }

  function goToPage(page: number) {
    const safePage = Math.min(Math.max(page, 1), totalPages);
    setJumpError("");
    setOffset((safePage - 1) * pageSize);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    setJumpPage("");
    setJumpError("");
    setOffset(0);
    setActive(filters);
  }

  function reset() {
    setFilters(blank);
    setActive(blank);
    setJumpPage("");
    setJumpError("");
    setOffset(0);
  }

  function submitJump(event: FormEvent) {
    event.preventDefault();
    const targetPage = Number(jumpPage);
    if (!Number.isInteger(targetPage) || targetPage < 1 || targetPage > totalPages) {
      setJumpError(`请输入 1 至 ${totalPages} 之间的页码。`);
      return;
    }
    goToPage(targetPage);
  }

  async function remove(id: number, company: string) {
    if (!window.confirm(`确定删除客户“${company}”吗？关联客户记录时系统会拒绝删除以保护数据。`)) return;
    setRemoving(id);
    try {
      await api.delete(`/customers/${id}`);
      const nextOffset = data?.items.length === 1 && offset > 0 ? offset - pageSize : offset;
      await load(nextOffset, active);
      if (nextOffset !== offset) setOffset(nextOffset);
    } catch {
      setError("无法删除客户：该客户可能已关联商机、报价、询盘或跟进记录。");
    } finally {
      setRemoving(null);
    }
  }

  return <>
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div><p className="text-sm text-slate-500">客户档案表标准字段</p><h2 className="text-3xl font-bold">客户管理</h2></div>
      {user?.role !== "Viewer" && <Link to="/customers/new" className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white">新增客户</Link>}
    </div>

    <form onSubmit={submit} className="mt-6 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <input value={filters.q} onChange={(event) => set("q", event.target.value)} placeholder="客户、公司、邮箱、国家、电话或备注" className="rounded border px-3 py-2 xl:col-span-2" />
        <input value={filters.source} onChange={(event) => set("source", event.target.value)} placeholder="来源" className="rounded border px-3 py-2" />
        <input value={filters.country} onChange={(event) => set("country", event.target.value)} placeholder="国家" className="rounded border px-3 py-2" />
        <input value={filters.customer_type} onChange={(event) => set("customer_type", event.target.value)} placeholder="客户类型" className="rounded border px-3 py-2" />
        <input value={filters.interested_product} onChange={(event) => set("interested_product", event.target.value)} placeholder="兴趣产品" className="rounded border px-3 py-2" />
        <input value={filters.followup_stage} onChange={(event) => set("followup_stage", event.target.value)} placeholder="跟进阶段" className="rounded border px-3 py-2" />
        <input value={filters.response_status} onChange={(event) => set("response_status", event.target.value)} placeholder="是否回复" className="rounded border px-3 py-2" />
        <input value={filters.followup_requirement} onChange={(event) => set("followup_requirement", event.target.value)} placeholder="是否需要跟进" className="rounded border px-3 py-2" />
        <input type="number" min="0" value={filters.customer_level_value} onChange={(event) => set("customer_level_value", event.target.value)} placeholder="客户等级" className="rounded border px-3 py-2" />
      </div>
      <div className="mt-3 flex gap-2"><button className="rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white">筛选</button><button type="button" onClick={reset} className="rounded border px-4 py-2 text-sm">重置</button></div>
    </form>

    {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}

    <section className="mt-6 overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
      <div className="border-b bg-slate-50 px-4 py-2">
        <p className="mb-1 text-xs text-slate-500">左右拖动此滚动条查看全部客户档案字段</p>
        <div ref={topScrollRef} onScroll={handleTopScroll} className="overflow-x-auto" aria-label="客户列表横向滚动条">
          <div className={`${tableWidthClass} h-3`} />
        </div>
      </div>
      <div ref={tableScrollRef} onScroll={handleTableScroll} className="overflow-x-auto">
        <table className={`${tableWidthClass} text-left text-sm`}>
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="min-w-32 px-4 py-3">客户名</th><th className="min-w-48 px-4 py-3">公司名</th><th className="min-w-32 px-4 py-3">国家</th><th className="min-w-36 px-4 py-3">获得客户时间</th><th className="min-w-28 px-4 py-3">职位</th><th className="min-w-40 px-4 py-3">WhatsApp</th><th className="min-w-56 px-4 py-3">邮箱</th><th className="min-w-36 px-4 py-3">电话</th><th className="min-w-28 px-4 py-3">来源</th><th className="min-w-32 px-4 py-3">客户类型</th><th className="min-w-56 px-4 py-3">兴趣产品</th><th className="min-w-28 px-4 py-3">客户体量</th><th className="min-w-28 px-4 py-3">客户等级</th><th className="min-w-28 px-4 py-3">客户总分</th><th className="min-w-36 px-4 py-3">跟进阶段</th><th className="min-w-40 px-4 py-3">自动判断阶段</th><th className="min-w-36 px-4 py-3">最近跟进日期</th><th className="min-w-36 px-4 py-3">是否需要跟进</th><th className="min-w-80 px-4 py-3">备注</th>
              {user?.role === "Admin" && <th className="min-w-24 px-4 py-3">操作</th>}
            </tr>
          </thead>
          <tbody>
            {data?.items.map((customer) => <tr key={customer.id} className="border-t align-top">
              <td className="whitespace-nowrap px-4 py-3">{dash(customer.contact_name)}</td>
              <td className="px-4 py-3 font-medium text-blue-700"><Link to={`/customers/${customer.id}`}>{customer.company_name}</Link></td>
              <td className="whitespace-nowrap px-4 py-3">{dash(customer.country)}</td><td className="whitespace-nowrap px-4 py-3">{dateOnly(customer.customer_acquired_at)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.position)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.whatsapp)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.email)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.phone)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.source)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.customer_type)}</td><td className="px-4 py-3">{dash(customer.interested_product)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.customer_size)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.customer_level_value)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.customer_total_score)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.followup_stage)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.automatic_stage_judgement)}</td><td className="whitespace-nowrap px-4 py-3">{dateOnly(customer.latest_followup_date)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.followup_requirement)}</td><td className="max-w-80 px-4 py-3">{noteSummary(customer.notes)}</td>
              {user?.role === "Admin" && <td className="whitespace-nowrap px-4 py-3"><button disabled={removing === customer.id} onClick={() => void remove(customer.id, customer.company_name)} className="text-rose-600 disabled:opacity-50">{removing === customer.id ? "删除中…" : "删除"}</button></td>}
            </tr>)}
            {data?.items.length === 0 && <tr><td colSpan={user?.role === "Admin" ? 20 : 19} className="px-4 py-12 text-center text-slate-500">没有匹配的客户。</td></tr>}
          </tbody>
        </table>
      </div>
    </section>

    <div className="mt-4 flex flex-col gap-3 text-sm lg:flex-row lg:items-center lg:justify-between">
      <span className="text-slate-500">共 {data?.total ?? 0} 位客户 · 第 {currentPage} 页 / 共 {totalPages} 页 · 每页 {pageSize} 位</span>
      <div className="flex flex-wrap items-center gap-2">
        <button disabled={currentPage <= 1} onClick={() => goToPage(currentPage - 1)} className="rounded border px-3 py-1 disabled:opacity-40">上一页</button>
        {visiblePages(currentPage, totalPages).map((item) => typeof item === "string" ? <span key={item} className="px-1 text-slate-400">…</span> : <button key={item} onClick={() => goToPage(item)} aria-current={item === currentPage ? "page" : undefined} className={`rounded border px-3 py-1 ${item === currentPage ? "border-blue-600 bg-blue-600 text-white" : ""}`}>{item}</button>)}
        <button disabled={currentPage >= totalPages} onClick={() => goToPage(currentPage + 1)} className="rounded border px-3 py-1 disabled:opacity-40">下一页</button>
        <form onSubmit={submitJump} className="ml-0 flex items-center gap-2 border-l pl-0 sm:ml-2 sm:pl-3">
          <label htmlFor="customer-page-jump" className="whitespace-nowrap">跳转到：</label>
          <input id="customer-page-jump" type="number" min="1" max={totalPages} value={jumpPage} onChange={(event) => setJumpPage(event.target.value)} className="w-20 rounded border px-2 py-1" />
          <span>页</span><button className="rounded border px-3 py-1">跳转</button>
        </form>
      </div>
      {jumpError && <p className="text-rose-600 lg:absolute">{jumpError}</p>}
    </div>
  </>;
}
