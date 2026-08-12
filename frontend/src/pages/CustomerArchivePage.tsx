import { useCallback, useEffect, useRef, useState, type FormEvent, type UIEvent } from "react";
import { Link } from "react-router-dom";

import { customerArchiveOptions } from "../constants/customerArchiveOptions";
import { FollowupReminderBadge } from "../components/FollowupReminderBadge";
import api from "../services/api";
import { downloadCustomerArchive, getCustomers, type CustomerFilters } from "../services/crm";
import { useAuth } from "../store/auth";
import type { CustomerPage } from "../types";

const pageSize = 10;
const tableWidthClass = "min-w-[3200px]";
const inputClass = "mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100";

type Filters = {
  q: string; customer_name: string; company_name: string; country: string; customer_acquired_from: string; customer_acquired_to: string;
  position: string; whatsapp: string; email: string; phone: string; source: string; customer_type: string; interested_product: string;
  customer_size: string; customer_level_value: string; customer_total_score_min: string; customer_total_score_max: string;
  followup_stage: string; automatic_stage_judgement: string; latest_followup_from: string; latest_followup_to: string;
  followup_requirement: string; response_status: string; notes: string;
};

const blank: Filters = {
  q: "", customer_name: "", company_name: "", country: "", customer_acquired_from: "", customer_acquired_to: "",
  position: "", whatsapp: "", email: "", phone: "", source: "", customer_type: "", interested_product: "",
  customer_size: "", customer_level_value: "", customer_total_score_min: "", customer_total_score_max: "",
  followup_stage: "", automatic_stage_judgement: "", latest_followup_from: "", latest_followup_to: "",
  followup_requirement: "", response_status: "", notes: "",
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

function ArchiveSelect({ label, value, onChange, options }: {
  label: string; value: string; onChange: (value: string) => void; options: readonly (string | number)[];
}) {
  return <label className="block text-sm font-medium text-slate-700">
    {label}
    <select value={value} onChange={(event) => onChange(event.target.value)} className={inputClass}>
      <option value="">不限 / 全部</option>
      {options.map((option) => <option key={option} value={option}>{option}</option>)}
    </select>
  </label>;
}

function ArchiveInput({ label, value, onChange, type = "text", placeholder, min }: {
  label: string; value: string; onChange: (value: string) => void; type?: "text" | "date" | "number"; placeholder?: string; min?: number;
}) {
  return <label className="block text-sm font-medium text-slate-700">
    {label}
    <input type={type} min={min} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder ?? label} className={inputClass} />
  </label>;
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
  const [exporting, setExporting] = useState(false);
  const topScrollRef = useRef<HTMLDivElement>(null);
  const tableScrollRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async (nextOffset = offset, nextFilters = active) => {
    const params: CustomerFilters = {
      limit: pageSize, offset: nextOffset,
      q: nextFilters.q || undefined, customer_name: nextFilters.customer_name || undefined, company_name: nextFilters.company_name || undefined,
      country: nextFilters.country || undefined, customer_acquired_from: nextFilters.customer_acquired_from || undefined, customer_acquired_to: nextFilters.customer_acquired_to || undefined,
      position: nextFilters.position || undefined, whatsapp: nextFilters.whatsapp || undefined, email: nextFilters.email || undefined, phone: nextFilters.phone || undefined,
      source: nextFilters.source || undefined, customer_type: nextFilters.customer_type || undefined, interested_product: nextFilters.interested_product || undefined,
      customer_size: nextFilters.customer_size ? Number(nextFilters.customer_size) : undefined,
      customer_level_value: nextFilters.customer_level_value ? Number(nextFilters.customer_level_value) : undefined,
      customer_total_score_min: nextFilters.customer_total_score_min ? Number(nextFilters.customer_total_score_min) : undefined,
      customer_total_score_max: nextFilters.customer_total_score_max ? Number(nextFilters.customer_total_score_max) : undefined,
      followup_stage: nextFilters.followup_stage || undefined, automatic_stage_judgement: nextFilters.automatic_stage_judgement || undefined,
      latest_followup_from: nextFilters.latest_followup_from || undefined, latest_followup_to: nextFilters.latest_followup_to || undefined,
      followup_requirement: nextFilters.followup_requirement || undefined, response_status: nextFilters.response_status || undefined, notes: nextFilters.notes || undefined,
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
  const syncHorizontalScroll = (source: HTMLDivElement, target: HTMLDivElement | null) => { if (target && target.scrollLeft !== source.scrollLeft) target.scrollLeft = source.scrollLeft; };
  const handleTopScroll = (event: UIEvent<HTMLDivElement>) => syncHorizontalScroll(event.currentTarget, tableScrollRef.current);
  const handleTableScroll = (event: UIEvent<HTMLDivElement>) => syncHorizontalScroll(event.currentTarget, topScrollRef.current);
  const goToPage = (page: number) => { const safePage = Math.min(Math.max(page, 1), totalPages); setJumpError(""); setOffset((safePage - 1) * pageSize); };

  function submit(event: FormEvent) { event.preventDefault(); setJumpPage(""); setJumpError(""); setOffset(0); setActive(filters); }
  function reset() { setFilters(blank); setActive(blank); setJumpPage(""); setJumpError(""); setOffset(0); }
  function submitJump(event: FormEvent) {
    event.preventDefault();
    const targetPage = Number(jumpPage);
    if (!Number.isInteger(targetPage) || targetPage < 1 || targetPage > totalPages) { setJumpError(`请输入 1 至 ${totalPages} 之间的页码。`); return; }
    goToPage(targetPage);
  }

  async function exportArchive() {
    setExporting(true);
    try {
      const blob = await downloadCustomerArchive();
      const href = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = href;
      link.download = `StarLink-CRM-客户档案表-${new Date().toISOString().slice(0, 10)}.xlsx`;
      document.body.appendChild(link); link.click(); link.remove(); window.URL.revokeObjectURL(href);
    } catch { setError("导出客户档案失败，请稍后重试。"); } finally { setExporting(false); }
  }

  async function remove(id: number, company: string) {
    if (!window.confirm(`确定删除客户“${company}”吗？关联客户记录时系统会拒绝删除以保护数据。`)) return;
    setRemoving(id);
    try {
      await api.delete(`/customers/${id}`);
      const nextOffset = data?.items.length === 1 && offset > 0 ? offset - pageSize : offset;
      await load(nextOffset, active);
      if (nextOffset !== offset) setOffset(nextOffset);
    } catch { setError("无法删除客户：该客户可能已关联商机、报价、询盘或跟进记录。"); } finally { setRemoving(null); }
  }

  return <>
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div><p className="text-sm text-slate-500">客户档案表标准字段</p><h2 className="text-3xl font-bold">客户管理</h2></div>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => void exportArchive()} disabled={exporting} className="rounded-lg border border-blue-600 bg-white px-4 py-2 font-semibold text-blue-700 disabled:cursor-not-allowed disabled:opacity-50">{exporting ? "正在导出…" : "导出全部客户"}</button>
        {user?.role !== "Viewer" && <Link to="/customers/new" className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white">新增客户</Link>}
      </div>
    </div>

    <form onSubmit={submit} className="mt-6 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
      <div className="mb-4"><h3 className="font-semibold text-slate-900">客户档案筛选</h3><p className="mt-1 text-sm text-slate-500">可组合多个条件筛选；日期范围包含起止日期。</p></div>
      <div className="grid gap-x-4 gap-y-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        <ArchiveInput label="全文搜索" value={filters.q} onChange={(value) => set("q", value)} placeholder="客户、公司、联系方式、备注等" />
        <ArchiveInput label="客户名" value={filters.customer_name} onChange={(value) => set("customer_name", value)} />
        <ArchiveInput label="公司名" value={filters.company_name} onChange={(value) => set("company_name", value)} />
        <ArchiveInput label="国家" value={filters.country} onChange={(value) => set("country", value)} />
        <ArchiveInput label="获得客户时间（从）" type="date" value={filters.customer_acquired_from} onChange={(value) => set("customer_acquired_from", value)} />
        <ArchiveInput label="获得客户时间（至）" type="date" value={filters.customer_acquired_to} onChange={(value) => set("customer_acquired_to", value)} />
        <ArchiveInput label="职位" value={filters.position} onChange={(value) => set("position", value)} />
        <ArchiveInput label="WhatsApp" value={filters.whatsapp} onChange={(value) => set("whatsapp", value)} />
        <ArchiveInput label="邮箱" value={filters.email} onChange={(value) => set("email", value)} />
        <ArchiveInput label="电话" value={filters.phone} onChange={(value) => set("phone", value)} />
        <ArchiveSelect label="来源" value={filters.source} onChange={(value) => set("source", value)} options={customerArchiveOptions.source} />
        <ArchiveSelect label="客户类型" value={filters.customer_type} onChange={(value) => set("customer_type", value)} options={customerArchiveOptions.customerType} />
        <ArchiveSelect label="兴趣产品" value={filters.interested_product} onChange={(value) => set("interested_product", value)} options={customerArchiveOptions.interestedProduct} />
        <ArchiveSelect label="客户体量" value={filters.customer_size} onChange={(value) => set("customer_size", value)} options={customerArchiveOptions.customerSize} />
        <ArchiveSelect label="客户等级" value={filters.customer_level_value} onChange={(value) => set("customer_level_value", value)} options={customerArchiveOptions.customerLevelValue} />
        <ArchiveInput label="客户总分（最低）" type="number" min={0} value={filters.customer_total_score_min} onChange={(value) => set("customer_total_score_min", value)} />
        <ArchiveInput label="客户总分（最高）" type="number" min={0} value={filters.customer_total_score_max} onChange={(value) => set("customer_total_score_max", value)} />
        <ArchiveSelect label="跟进阶段" value={filters.followup_stage} onChange={(value) => set("followup_stage", value)} options={customerArchiveOptions.followupStage} />
        <ArchiveInput label="自动判断阶段" value={filters.automatic_stage_judgement} onChange={(value) => set("automatic_stage_judgement", value)} />
        <ArchiveInput label="最近跟进日期（从）" type="date" value={filters.latest_followup_from} onChange={(value) => set("latest_followup_from", value)} />
        <ArchiveInput label="最近跟进日期（至）" type="date" value={filters.latest_followup_to} onChange={(value) => set("latest_followup_to", value)} />
        <ArchiveInput label="是否需要跟进" value={filters.followup_requirement} onChange={(value) => set("followup_requirement", value)} placeholder="按现有系统状态搜索" />
        <ArchiveSelect label="是否回复" value={filters.response_status} onChange={(value) => set("response_status", value)} options={customerArchiveOptions.responseStatus} />
        <ArchiveInput label="备注" value={filters.notes} onChange={(value) => set("notes", value)} placeholder="搜索备注内容" />
      </div>
      <div className="mt-5 flex flex-wrap gap-2 border-t pt-4"><button className="rounded-md bg-slate-900 px-5 py-2 text-sm font-semibold text-white">筛选</button><button type="button" onClick={reset} className="rounded-md border border-slate-300 px-5 py-2 text-sm font-semibold text-slate-700">重置</button></div>
    </form>

    {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}
    <section className="mt-6 overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
      <div className="border-b bg-slate-50 px-4 py-2"><p className="mb-1 text-xs text-slate-500">左右拖动此滚动条查看全部客户档案字段</p><div ref={topScrollRef} onScroll={handleTopScroll} className="overflow-x-auto" aria-label="客户列表横向滚动条"><div className={`${tableWidthClass} h-3`} /></div></div>
      <div ref={tableScrollRef} onScroll={handleTableScroll} className="overflow-x-auto">
        <table className={`${tableWidthClass} text-left text-sm`}>
          <thead className="bg-slate-50 text-slate-500"><tr><th className="min-w-32 px-4 py-3">客户名</th><th className="min-w-48 px-4 py-3">公司名</th><th className="min-w-32 px-4 py-3">国家</th><th className="min-w-36 px-4 py-3">获得客户时间</th><th className="min-w-28 px-4 py-3">职位</th><th className="min-w-40 px-4 py-3">WhatsApp</th><th className="min-w-56 px-4 py-3">邮箱</th><th className="min-w-36 px-4 py-3">电话</th><th className="min-w-28 px-4 py-3">来源</th><th className="min-w-32 px-4 py-3">客户类型</th><th className="min-w-56 px-4 py-3">兴趣产品</th><th className="min-w-28 px-4 py-3">客户体量</th><th className="min-w-28 px-4 py-3">客户等级</th><th className="min-w-28 px-4 py-3">客户总分</th><th className="min-w-36 px-4 py-3">跟进阶段</th><th className="min-w-40 px-4 py-3">自动判断阶段</th><th className="min-w-36 px-4 py-3">最近跟进日期</th><th className="min-w-36 px-4 py-3">建议跟进日期</th><th className="min-w-44 px-4 py-3">跟进提醒</th><th className="min-w-36 px-4 py-3">是否需要跟进</th><th className="min-w-80 px-4 py-3">备注</th>{user?.role === "Admin" && <th className="min-w-24 px-4 py-3">操作</th>}</tr></thead>
          <tbody>
            {data?.items.map((customer) => <tr key={customer.id} className="border-t align-top"><td className="whitespace-nowrap px-4 py-3">{dash(customer.contact_name)}</td><td className="px-4 py-3 font-medium text-blue-700"><Link to={`/customers/${customer.id}`}>{customer.company_name}</Link></td><td className="whitespace-nowrap px-4 py-3">{dash(customer.country)}</td><td className="whitespace-nowrap px-4 py-3">{dateOnly(customer.customer_acquired_at)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.position)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.whatsapp)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.email)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.phone)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.source)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.customer_type)}</td><td className="px-4 py-3">{dash(customer.interested_product)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.customer_size)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.customer_level_value)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.customer_total_score)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.followup_stage)}</td><td className="whitespace-nowrap px-4 py-3">{dash(customer.automatic_stage_judgement)}</td><td className="whitespace-nowrap px-4 py-3">{dateOnly(customer.latest_followup_date)}</td><td className="whitespace-nowrap px-4 py-3">{dateOnly(customer.suggested_followup_date)}</td><td className="px-4 py-3"><FollowupReminderBadge status={customer.calculated_followup_reminder_status} label={customer.calculated_followup_reminder_label} /></td><td className="whitespace-nowrap px-4 py-3">{dash(customer.followup_requirement)}</td><td className="max-w-80 px-4 py-3">{noteSummary(customer.notes)}</td>{user?.role === "Admin" && <td className="whitespace-nowrap px-4 py-3"><button type="button" disabled={removing === customer.id} onClick={() => void remove(customer.id, customer.company_name)} className="text-rose-600 disabled:opacity-50">{removing === customer.id ? "删除中…" : "删除"}</button></td>}</tr>)}
            {data?.items.length === 0 && <tr><td colSpan={user?.role === "Admin" ? 22 : 21} className="px-4 py-12 text-center text-slate-500">没有匹配的客户。</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
    <div className="mt-4 flex flex-col gap-3 text-sm lg:flex-row lg:items-center lg:justify-between"><span className="text-slate-500">共 {data?.total ?? 0} 位客户 · 第 {currentPage} 页 / 共 {totalPages} 页 · 每页 {pageSize} 位</span><div className="flex flex-wrap items-center gap-2"><button type="button" disabled={currentPage <= 1} onClick={() => goToPage(currentPage - 1)} className="rounded border px-3 py-1 disabled:opacity-40">上一页</button>{visiblePages(currentPage, totalPages).map((item) => typeof item === "string" ? <span key={item} className="px-1 text-slate-400">…</span> : <button type="button" key={item} onClick={() => goToPage(item)} aria-current={item === currentPage ? "page" : undefined} className={`rounded border px-3 py-1 ${item === currentPage ? "border-blue-600 bg-blue-600 text-white" : ""}`}>{item}</button>)}<button type="button" disabled={currentPage >= totalPages} onClick={() => goToPage(currentPage + 1)} className="rounded border px-3 py-1 disabled:opacity-40">下一页</button><form onSubmit={submitJump} className="ml-0 flex items-center gap-2 border-l pl-0 sm:ml-2 sm:pl-3"><label htmlFor="customer-page-jump" className="whitespace-nowrap">跳转到：</label><input id="customer-page-jump" type="number" min="1" max={totalPages} value={jumpPage} onChange={(event) => setJumpPage(event.target.value)} className="w-20 rounded border px-2 py-1" /><span>页</span><button className="rounded border px-3 py-1">跳转</button></form></div>{jumpError && <p className="text-rose-600 lg:absolute">{jumpError}</p>}</div>
  </>;
}
