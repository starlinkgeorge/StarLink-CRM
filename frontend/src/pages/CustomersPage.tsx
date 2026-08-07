import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { StatusBadge } from "../components/StatusBadge";
import { getCustomerCategories, getCustomers, getTags, type CustomerFilters } from "../services/crm";
import { useAuth } from "../store/auth";
import type { CustomerCategory, CustomerPage, Tag } from "../types";

const PAGE_SIZE = 20;
const salesStages = ["", "Lead", "Contacted", "Quotation", "Negotiation", "Won", "Lost"];
const stageText: Record<string, string> = {
  "": "全部销售阶段",
  Lead: "新线索",
  Contacted: "已联系",
  Quotation: "报价中",
  Negotiation: "谈判中",
  Won: "已成交",
  Lost: "已流失",
};
const customerTypes = [
  "",
  "Kindergarten",
  "School",
  "Distributor",
  "Wholesaler",
  "Retailer",
  "Project Contractor",
  "Other",
];
const sources = ["", "Alibaba", "Website", "Facebook", "LinkedIn", "Other"];

type FilterForm = {
  q: string;
  sales_stage: string;
  level: string;
  country: string;
  customer_type: string;
  source: string;
  interested_product: string;
  tag_id: string;
  category_id: string;
  score_min: string;
  score_max: string;
};

const emptyFilters: FilterForm = {
  q: "",
  sales_stage: "",
  level: "",
  country: "",
  customer_type: "",
  source: "",
  interested_product: "",
  tag_id: "",
  category_id: "",
  score_min: "",
  score_max: "",
};

export function CustomersPage() {
  const { user } = useAuth();
  const [data, setData] = useState<CustomerPage | null>(null);
  const [tags, setTags] = useState<Tag[]>([]);
  const [categories, setCategories] = useState<CustomerCategory[]>([]);
  const [filters, setFilters] = useState<FilterForm>(emptyFilters);
  const [active, setActive] = useState<FilterForm>(emptyFilters);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getTags(), getCustomerCategories(true)])
      .then(([tagData, categoryData]) => { setTags(tagData); setCategories(categoryData); })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    const { tag_id: tagId, category_id: categoryId, score_min: scoreMin, score_max: scoreMax, ...filterValues } = active;
    const params: CustomerFilters = {
      limit: PAGE_SIZE,
      offset,
      ...filterValues,
      tag_id: tagId ? Number(tagId) : undefined,
      category_id: categoryId ? Number(categoryId) : undefined,
      score_min: scoreMin ? Number(scoreMin) : undefined,
      score_max: scoreMax ? Number(scoreMax) : undefined,
    };
    setError("");
    getCustomers(params)
      .then(setData)
      .catch(() => setError("无法加载客户列表。"));
  }, [offset, active]);

  const search = (event: FormEvent) => {
    event.preventDefault();
    setOffset(0);
    setActive(filters);
  };

  const reset = () => {
    setFilters(emptyFilters);
    setActive(emptyFilters);
    setOffset(0);
  };

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">外贸客户管理</p>
          <h2 className="text-3xl font-bold">客户</h2>
        </div>
        {user?.role !== "Viewer" && (
          <Link
            to="/customers/new"
            className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white"
          >
            新增客户
          </Link>
        )}
      </div>

      <form
        onSubmit={search}
        className="mt-6 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200"
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <input
            value={filters.q}
            onChange={(event) => setFilters({ ...filters, q: event.target.value })}
            placeholder="公司、联系人、国家或邮箱"
            className="rounded-lg border px-3 py-2"
          />
          <select
            value={filters.customer_type}
            onChange={(event) => setFilters({ ...filters, customer_type: event.target.value })}
            className="rounded-lg border px-3 py-2"
          >
            {customerTypes.map((type) => (
              <option key={type || "all"} value={type}>
                {type || "全部客户类型"}
              </option>
            ))}
          </select>
          <input
            value={filters.interested_product}
            onChange={(event) =>
              setFilters({ ...filters, interested_product: event.target.value })
            }
            placeholder="感兴趣产品"
            className="rounded-lg border px-3 py-2"
          />
          <select
            value={filters.sales_stage}
            onChange={(event) => setFilters({ ...filters, sales_stage: event.target.value })}
            className="rounded-lg border px-3 py-2"
          >
            {salesStages.map((stage) => (
              <option key={stage || "all"} value={stage}>
                {stageText[stage]}
              </option>
            ))}
          </select>
          <select
            value={filters.source}
            onChange={(event) => setFilters({ ...filters, source: event.target.value })}
            className="rounded-lg border px-3 py-2"
          >
            {sources.map((source) => (
              <option key={source || "all"} value={source}>
                {source || "全部客户来源"}
              </option>
            ))}
          </select>
          <select
            value={filters.level}
            onChange={(event) => setFilters({ ...filters, level: event.target.value })}
            className="rounded-lg border px-3 py-2"
          >
            <option value="">全部等级</option>
            <option>A</option><option>B</option><option>C</option>
          </select>
          <input
            value={filters.country}
            onChange={(event) => setFilters({ ...filters, country: event.target.value })}
            placeholder="国家/地区"
            className="rounded-lg border px-3 py-2"
          />
          <select
            value={filters.tag_id}
            onChange={(event) => setFilters({ ...filters, tag_id: event.target.value })}
            className="rounded-lg border px-3 py-2"
          >
            <option value="">全部标签</option>
            {tags.map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}
          </select>
          <select value={filters.category_id} onChange={(event) => setFilters({ ...filters, category_id: event.target.value })} className="rounded-lg border px-3 py-2">
            <option value="">全部客户分类</option>
            {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
          </select>
          <select value={filters.score_min} onChange={(event) => setFilters({ ...filters, score_min: event.target.value })} className="rounded-lg border px-3 py-2">
            <option value="">最低评分</option><option value="80">80+（A）</option><option value="50">50+（B）</option><option value="0">0+（C）</option>
          </select>
          <select value={filters.score_max} onChange={(event) => setFilters({ ...filters, score_max: event.target.value })} className="rounded-lg border px-3 py-2">
            <option value="">最高评分</option><option value="49">0-49（C）</option><option value="79">50-79（B）</option><option value="100">80-100（A）</option>
          </select>
        </div>
        <div className="mt-3 flex gap-2">
          <button className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white">
            搜索
          </button>
          <button type="button" onClick={reset} className="rounded-lg border px-4 py-2 text-sm">
            重置
          </button>
        </div>
      </form>

      {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}
      <div className="mt-6 overflow-x-auto rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-4 py-3">公司</th>
              <th className="px-4 py-3">联系人</th>
              <th className="px-4 py-3">客户类型</th>
              <th className="px-4 py-3">客户分类</th>
              <th className="px-4 py-3">来源</th>
              <th className="px-4 py-3">感兴趣产品</th>
              <th className="px-4 py-3">国家</th>
              <th className="px-4 py-3">等级</th>
              <th className="px-4 py-3">评分</th>
              <th className="px-4 py-3">阶段</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((customer) => (
              <tr key={customer.id} className="border-t">
                <td className="px-4 py-3 font-medium text-blue-700">
                  <Link to={`/customers/${customer.id}`}>{customer.company_name}</Link>
                </td>
                <td className="px-4 py-3">{customer.contact_name ?? "—"}</td>
                <td className="px-4 py-3">{customer.customer_type ?? "—"}</td>
                <td className="px-4 py-3">{customer.category?.name ?? "—"}</td>
                <td className="px-4 py-3">{customer.source ?? "—"}</td>
                <td className="px-4 py-3">{customer.interested_product ?? "—"}</td>
                <td className="px-4 py-3">{customer.country ?? "—"}</td>
                <td className="px-4 py-3">{customer.level}</td>
                <td className="px-4 py-3 font-semibold">{customer.customer_score}</td>
                <td className="px-4 py-3"><StatusBadge status={customer.sales_stage} /></td>
              </tr>
            ))}
            {data?.items.length === 0 && (
              <tr><td colSpan={10} className="px-4 py-10 text-center text-slate-500">没有匹配的客户。</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="mt-4 flex justify-between text-sm">
        <span className="text-slate-500">共 {data?.total ?? 0} 位客户</span>
        <div className="flex gap-2">
          <button
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            className="rounded border px-3 py-1 disabled:opacity-40"
          >
            上一页
          </button>
          <button
            disabled={!data || offset + PAGE_SIZE >= data.total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
            className="rounded border px-3 py-1 disabled:opacity-40"
          >
            下一页
          </button>
        </div>
      </div>
    </>
  );
}
