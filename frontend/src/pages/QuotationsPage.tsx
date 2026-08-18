import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { deleteQuotation, getQuotations } from "../services/crm";
import { useAuth } from "../store/auth";
import type { QuotationPage, QuotationStatus } from "../types";

const PAGE_SIZE = 20;
const statuses: QuotationStatus[] = ["Draft", "Sent", "Accepted", "Rejected", "Expired"];
const labels: Record<QuotationStatus, string> = {
  Draft: "草稿",
  Sent: "已发送",
  Accepted: "已接受",
  Rejected: "已拒绝",
  Expired: "已过期",
};

export function QuotationsPage() {
  const { user } = useAuth();
  const canDelete = user?.role === "Admin";
  const [data, setData] = useState<QuotationPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<QuotationStatus | "">("");
  const [filters, setFilters] = useState<{ q: string; status: QuotationStatus | "" }>({
    q: "",
    status: "",
  });
  const [error, setError] = useState("");
  const [deletingQuotationId, setDeletingQuotationId] = useState<number | null>(null);

  const load = useCallback(
    async (currentOffset = offset, active = filters) => {
      try {
        setData(
          await getQuotations({
            limit: PAGE_SIZE,
            offset: currentOffset,
            q: active.q,
            status: active.status,
          }),
        );
        setError("");
      } catch {
        setError("无法加载报价列表。");
      }
    },
    [offset, filters],
  );

  useEffect(() => {
    void load();
  }, [load]);

  function search(event: FormEvent) {
    event.preventDefault();
    setOffset(0);
    setFilters({ q: query, status });
  }

  async function removeQuotation(quotationId: number, quotationNumber: string) {
    const confirmed = window.confirm(
      `确定要删除报价“${quotationNumber}”吗？报价版本和明细会被删除，此操作不可恢复；客户、产品和商机不会被删除。`,
    );
    if (!confirmed) return;
    setDeletingQuotationId(quotationId);
    try {
      await deleteQuotation(quotationId);
      setError("");
      const nextOffset = data?.items.length === 1 && offset > 0 ? offset - PAGE_SIZE : offset;
      if (nextOffset !== offset) setOffset(nextOffset);
      else await load(nextOffset);
    } catch {
      setError("无法删除报价。请确认当前账户拥有管理员权限后重试。");
    } finally {
      setDeletingQuotationId(null);
    }
  }

  return (
    <>
      <div>
        <p className="text-sm text-slate-500">Opportunity → Quotation → PDF</p>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-3xl font-bold">报价管理</h2>
          {user?.role !== "Viewer" && (
            <Link to="/quotations/new" className="rounded-lg bg-blue-700 px-4 py-2 font-semibold text-white hover:bg-blue-800">
              创建报价
            </Link>
          )}
        </div>
      </div>

      <form
        onSubmit={search}
        className="mt-6 flex flex-wrap gap-3 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200"
      >
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="搜索报价编号或客户公司"
          className="min-w-64 flex-1 rounded-lg border px-3 py-2"
        />
        <select
          value={status}
          onChange={(event) => setStatus(event.target.value as QuotationStatus | "")}
          className="rounded-lg border px-3 py-2"
        >
          <option value="">全部状态</option>
          {statuses.map((item) => (
            <option key={item} value={item}>
              {labels[item]}
            </option>
          ))}
        </select>
        <button className="rounded-lg bg-slate-900 px-4 py-2 font-semibold text-white">
          筛选
        </button>
      </form>

      {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}

      <div className="mt-6 overflow-x-auto rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-4 py-3">报价编号</th>
              <th className="px-4 py-3">客户</th>
              <th className="px-4 py-3">商机</th>
              <th className="px-4 py-3">金额</th>
              <th className="px-4 py-3">状态</th>
              <th className="px-4 py-3">更新时间</th>
              {canDelete && <th className="px-4 py-3">操作</th>}
            </tr>
          </thead>
          <tbody>
            {data?.items.map((item) => (
              <tr key={item.id} className="border-t">
                <td className="px-4 py-3 font-medium text-blue-700">
                  <Link to={`/quotations/${item.id}`}>{item.quotation_number}</Link>
                </td>
                <td className="px-4 py-3">
                  <Link to={`/customers/${item.customer_id}`} className="text-blue-700">
                    {item.customer_company}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  {item.opportunity_id ? (
                    <Link to={`/opportunities/${item.opportunity_id}`} className="text-blue-700">
                      {item.opportunity_name}
                    </Link>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="px-4 py-3">
                  {item.currency}{" "}
                  {Number(item.total_amount).toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                  })}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2 py-1 text-xs ${
                      item.status === "Draft"
                        ? "bg-amber-100 text-amber-700"
                        : item.status === "Sent"
                          ? "bg-blue-100 text-blue-700"
                          : "bg-slate-100 text-slate-700"
                    }`}
                  >
                    {labels[item.status]}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-500">
                  {new Date(item.updated_at).toLocaleString()}
                </td>
                {canDelete && (
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      disabled={deletingQuotationId === item.id}
                      onClick={() => void removeQuotation(item.id, item.quotation_number)}
                      className="text-rose-600 disabled:opacity-50"
                    >
                      {deletingQuotationId === item.id ? "删除中..." : "删除"}
                    </button>
                  </td>
                )}
              </tr>
            ))}
            {data?.items.length === 0 && (
              <tr>
                <td colSpan={canDelete ? 7 : 6} className="px-4 py-10 text-center text-slate-500">
                  暂无报价。请从商机详情创建第一份报价。
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex justify-between text-sm">
        <span className="text-slate-500">共 {data?.total ?? 0} 份报价</span>
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
