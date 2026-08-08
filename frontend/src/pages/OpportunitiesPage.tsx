import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import {
  createOpportunity,
  getCustomers,
  getOpportunities,
  type OpportunityPayload,
} from "../services/crm";
import {
  opportunityDealStageClass,
  opportunityDealStageLabels,
  opportunityDealStages,
} from "../constants/opportunityDealStages";
import { useAuth } from "../store/auth";
import type {
  Customer,
  OpportunityDealStage,
  OpportunityPage,
} from "../types";

const PAGE_SIZE = 20;

export function OpportunitiesPage() {
  const { user } = useAuth();
  const [data, setData] = useState<OpportunityPage | null>(null);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [offset, setOffset] = useState(0);
  const [query, setQuery] = useState("");
  const [dealStage, setDealStage] = useState("");
  const [active, setActive] = useState({ q: "", deal_stage: "" });
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<OpportunityPayload>({
    customer_id: 0,
    name: "",
    currency: "USD",
    deal_stage: "New Inquiry",
    probability: 10,
  });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(
    async (currentOffset = offset, filters = active) => {
      try {
        setData(
          await getOpportunities({
            limit: PAGE_SIZE,
            offset: currentOffset,
            ...filters,
          }),
        );
        setError("");
      } catch {
        setError("无法加载商机列表。");
      }
    },
    [active, offset],
  );

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    getCustomers({ limit: 100, offset: 0 })
      .then((page) => setCustomers(page.items))
      .catch(() => undefined);
  }, []);

  function search(event: FormEvent) {
    event.preventDefault();
    setOffset(0);
    setActive({ q: query, deal_stage: dealStage });
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await createOpportunity(form);
      setForm({
        customer_id: 0,
        name: "",
        currency: "USD",
        deal_stage: "New Inquiry",
        probability: 10,
      });
      setShowCreate(false);
      setOffset(0);
      await load(0, active);
    } catch {
      setError("无法创建商机，请检查客户和必填字段。");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">销售机会管理</p>
          <h2 className="text-3xl font-bold">商机管理</h2>
        </div>
        <div className="flex gap-3">
          <Link
            to="/pipeline"
            className="rounded-lg border border-blue-600 px-4 py-2 font-semibold text-blue-700"
          >
            销售漏斗看板
          </Link>
          {user?.role !== "Viewer" && (
            <button
              onClick={() => setShowCreate(!showCreate)}
              className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white"
            >
              {showCreate ? "取消新增" : "新增商机"}
            </button>
          )}
        </div>
      </div>

      {showCreate && (
        <form
          onSubmit={submit}
          className="mt-6 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"
        >
          <h3 className="font-bold">创建商机</h3>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <select
              required
              value={form.customer_id || ""}
              onChange={(event) => setForm({ ...form, customer_id: Number(event.target.value) })}
              className="rounded-lg border px-3 py-2"
            >
              <option value="">选择客户 *</option>
              {customers.map((customer) => (
                <option key={customer.id} value={customer.id}>{customer.company_name}</option>
              ))}
            </select>
            <input
              required
              maxLength={255}
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              placeholder="商机名称 *"
              className="rounded-lg border px-3 py-2"
            />
            <input
              maxLength={500}
              value={form.interested_product ?? ""}
              onChange={(event) => setForm({ ...form, interested_product: event.target.value })}
              placeholder="产品需求"
              className="rounded-lg border px-3 py-2"
            />
            <select
              value={form.deal_stage ?? "New Inquiry"}
              onChange={(event) => setForm({ ...form, deal_stage: event.target.value as OpportunityDealStage })}
              className="rounded-lg border px-3 py-2"
            >
              {opportunityDealStages.map((stage) => (
                <option key={stage} value={stage}>{opportunityDealStageLabels[stage]}</option>
              ))}
            </select>
            <input
              type="number"
              min="0"
              max="100"
              value={form.probability ?? ""}
              onChange={(event) => setForm({ ...form, probability: Number(event.target.value) })}
              placeholder="成交概率 (%)"
              className="rounded-lg border px-3 py-2"
            />
            <input
              type="number"
              min="0"
              step="0.01"
              value={form.amount ?? ""}
              onChange={(event) => setForm({ ...form, amount: event.target.value })}
              placeholder="预计金额"
              className="rounded-lg border px-3 py-2"
            />
            <input
              required
              minLength={3}
              maxLength={3}
              value={form.currency ?? "USD"}
              onChange={(event) => setForm({ ...form, currency: event.target.value.toUpperCase() })}
              placeholder="币种"
              className="rounded-lg border px-3 py-2"
            />
            <input
              type="date"
              value={form.expected_close_date ?? ""}
              onChange={(event) => setForm({ ...form, expected_close_date: event.target.value || undefined })}
              className="rounded-lg border px-3 py-2"
            />
            <input
              maxLength={500}
              value={form.next_action ?? ""}
              onChange={(event) => setForm({ ...form, next_action: event.target.value || null })}
              placeholder="下一步行动"
              className="rounded-lg border px-3 py-2"
            />
          </div>
          <button
            disabled={saving}
            className="mt-4 rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white disabled:opacity-60"
          >
            {saving ? "保存中..." : "创建商机"}
          </button>
        </form>
      )}

      <form
        onSubmit={search}
        className="mt-6 flex flex-wrap gap-3 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200"
      >
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="搜索商机、客户或产品"
          className="min-w-64 flex-1 rounded-lg border px-3 py-2"
        />
        <select
          value={dealStage}
          onChange={(event) => setDealStage(event.target.value)}
          className="rounded-lg border px-3 py-2"
        >
          <option value="">全部销售阶段</option>
          {opportunityDealStages.map((stage) => (
            <option key={stage} value={stage}>{opportunityDealStageLabels[stage]}</option>
          ))}
        </select>
        <button className="rounded-lg bg-slate-900 px-4 py-2 font-semibold text-white">筛选</button>
      </form>

      {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}
      <section className="mt-6 overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-left text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="px-5 py-3">商机</th>
                <th className="px-5 py-3">客户</th>
                <th className="px-5 py-3">产品</th>
                <th className="px-5 py-3">预计金额</th>
                <th className="px-5 py-3">销售阶段</th>
                <th className="px-5 py-3">概率</th>
                <th className="px-5 py-3">预计成交</th>
                <th className="px-5 py-3">负责人</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((item) => (
                <tr key={item.id} className="border-t">
                  <td className="px-5 py-4 font-medium">
                    <Link to={`/opportunities/${item.id}`} className="text-blue-700 hover:underline">{item.name}</Link>
                  </td>
                  <td className="px-5 py-4">{item.customer_company}</td>
                  <td className="px-5 py-4">{item.interested_product ?? "—"}</td>
                  <td className="px-5 py-4">{item.amount ? `${item.currency} ${Number(item.amount).toLocaleString()}` : "—"}</td>
                  <td className="px-5 py-4">
                    <span className={`rounded-full px-2 py-1 text-xs font-medium ${opportunityDealStageClass(item.deal_stage)}`}>
                      {opportunityDealStageLabels[item.deal_stage]}
                    </span>
                  </td>
                  <td className="px-5 py-4">{item.probability}%</td>
                  <td className="px-5 py-4">{item.expected_close_date ?? "—"}</td>
                  <td className="px-5 py-4">{item.owner_name ?? "—"}</td>
                </tr>
              ))}
              {data?.items.length === 0 && (
                <tr><td colSpan={8} className="px-5 py-12 text-center text-slate-500">暂无商机</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
      <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
        <span>共 {data?.total ?? 0} 个商机</span>
        <div className="flex gap-2">
          <button
            disabled={offset === 0}
            onClick={() => { const next = Math.max(0, offset - PAGE_SIZE); setOffset(next); void load(next); }}
            className="rounded border px-3 py-1 disabled:opacity-40"
          >上一页</button>
          <button
            disabled={!data || offset + PAGE_SIZE >= data.total}
            onClick={() => { const next = offset + PAGE_SIZE; setOffset(next); void load(next); }}
            className="rounded border px-3 py-1 disabled:opacity-40"
          >下一页</button>
        </div>
      </div>
    </>
  );
}
