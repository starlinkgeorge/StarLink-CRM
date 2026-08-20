import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { getOrderProfitAnalytics } from "../services/crm";
import { getApiErrorMessage } from "../services/api";
import type { OrderProfitAnalytics as ProfitAnalytics, OrderProfitPeriod, OrderProfitSummary } from "../types";

const cardOrder: Exclude<OrderProfitPeriod, "custom">[] = ["today", "month", "quarter", "half_year", "year"];
const cardLabels: Record<Exclude<OrderProfitPeriod, "custom">, string> = {
  today: "今日利润",
  month: "本月利润",
  quarter: "本季度利润",
  half_year: "近6个月利润",
  year: "本年度利润",
};
const formatRmb = (value: string | null | undefined) => {
  if (value === null || value === undefined) return "—";
  const amount = Number(value);
  return `${amount < 0 ? "-" : ""}¥${Math.abs(amount).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};
const currencyAmounts = (summary: OrderProfitSummary) => summary.order_amounts.length
  ? summary.order_amounts.map((item) => `${item.currency} ${item.amount}`).join(" · ")
  : "—";

export function OrderProfitAnalytics() {
  const [data, setData] = useState<ProfitAnalytics | null>(null);
  const [period, setPeriod] = useState<OrderProfitPeriod>("month");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [detailOffset, setDetailOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const appliedCustomRange = useRef<{ startDate: string; endDate: string } | null>(null);

  const load = useCallback(async (nextPeriod: OrderProfitPeriod, nextOffset = 0) => {
    setLoading(true);
    try {
      const result = await getOrderProfitAnalytics({
        period: nextPeriod,
        start_date: nextPeriod === "custom" ? appliedCustomRange.current?.startDate : undefined,
        end_date: nextPeriod === "custom" ? appliedCustomRange.current?.endDate : undefined,
        detail_limit: 50,
        detail_offset: nextOffset,
      });
      setData(result);
      setDetailOffset(nextOffset);
      setError("");
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError, "无法加载利润分析。"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load("month"); }, [load]);

  function submitCustom(event: FormEvent) {
    event.preventDefault();
    if (!startDate || !endDate) {
      setError("请选择开始日期和结束日期。");
      return;
    }
    appliedCustomRange.current = { startDate, endDate };
    setPeriod("custom");
    void load("custom");
  }

  const maximumTrendProfit = useMemo(
    () => Math.max(1, ...(data?.monthly_trend.map((item) => Math.abs(Number(item.profit_total))) ?? [1])),
    [data],
  );

  return <section className="mt-5 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div><p className="text-sm text-slate-500">基于订单日期（Asia/Shanghai）汇总，不混合不同外币金额</p><h3 className="text-xl font-bold">利润分析</h3></div>
      <form onSubmit={submitCustom} className="flex flex-wrap items-end gap-2">
        <label className="text-sm text-slate-600">开始日期<input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} className="mt-1 block rounded border px-3 py-2" /></label>
        <label className="text-sm text-slate-600">结束日期<input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} className="mt-1 block rounded border px-3 py-2" /></label>
        <button type="submit" disabled={loading} className="rounded bg-slate-900 px-4 py-2 font-semibold text-white disabled:opacity-60">查询</button>
      </form>
    </div>

    {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
    <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {cardOrder.map((key) => {
        const summary = data?.period_summaries.find((item) => cardLabels[key] === item.label);
        return <button type="button" key={key} disabled={loading} onClick={() => { setPeriod(key); void load(key); }} className={`rounded-lg border p-4 text-left transition hover:border-blue-400 ${period === key ? "border-blue-600 bg-blue-50" : "border-slate-200"}`}>
          <p className="text-sm text-slate-500">{summary?.label ?? "加载中…"}</p>
          <p className={`mt-1 text-xl font-bold ${Number(summary?.profit_total ?? 0) < 0 ? "text-rose-600" : "text-slate-900"}`}>{formatRmb(summary?.profit_total)}</p>
          <p className="mt-1 text-xs text-slate-500">{summary?.order_count ?? 0} 笔订单 · 待核算 {summary?.pending_order_count ?? 0} 笔</p>
        </button>;
      })}
    </div>

    {data && <>
      <section className="mt-6 rounded-lg bg-slate-50 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><h4 className="font-bold">{data.selected_summary.label}</h4><p className="mt-1 text-sm text-slate-500">{data.selected_summary.start_date} 至 {data.selected_summary.end_date}（含首尾）</p></div><p className="text-sm text-slate-600">订单金额：{currencyAmounts(data.selected_summary)}</p></div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="订单数量" value={`${data.selected_summary.order_count} 笔`} subtext={`已核算 ${data.selected_summary.accounted_order_count} · 待核算 ${data.selected_summary.pending_order_count}`} />
          <Metric label="人民币实收" value={formatRmb(data.selected_summary.rmb_received_total)} />
          <Metric label="采购金额 / 运费" value={`${formatRmb(data.selected_summary.purchase_cost_total)} / ${formatRmb(data.selected_summary.freight_cost_total)}`} />
          <Metric label="利润 / 利润率" value={`${formatRmb(data.selected_summary.profit_total)}${data.selected_summary.profit_margin === null ? " · —" : ` · ${Number(data.selected_summary.profit_margin).toFixed(2)}%`}`} />
        </div>
      </section>

      <section className="mt-6"><h4 className="font-bold">月度利润趋势</h4><p className="mt-1 text-sm text-slate-500">最近 12 个自然月；仅已核算订单计入人民币实收和利润。</p><div className="mt-3 overflow-x-auto"><div className="flex min-w-[680px] items-end gap-2 rounded-lg bg-slate-50 p-4" style={{ height: 240 }}>
        {data.monthly_trend.map((point) => {
          const amount = Number(point.profit_total); const height = Math.max(3, Math.round(Math.abs(amount) / maximumTrendProfit * 140));
          return <div key={point.month} className="flex min-w-12 flex-1 flex-col items-center justify-end gap-1 text-center"><span className={`text-xs ${amount < 0 ? "text-rose-600" : "text-slate-600"}`}>{formatRmb(point.profit_total)}</span><div title={`${point.month}: ${formatRmb(point.profit_total)}`} className={`w-full rounded-t ${amount < 0 ? "bg-rose-400" : "bg-blue-600"}`} style={{ height }} /><span className="text-[11px] text-slate-500">{point.month.slice(5)}</span><span className="text-[10px] text-slate-400">{point.order_count}笔</span></div>;
        })}
      </div></div></section>

      <section className="mt-6 grid gap-6 xl:grid-cols-2">
        <div><h4 className="font-bold">客户利润排行</h4><div className="mt-3 overflow-x-auto rounded-lg border"><table className="min-w-[620px] w-full text-left text-sm"><thead className="bg-slate-50 text-slate-500"><tr><th className="px-3 py-2">客户</th><th className="px-3 py-2">订单</th><th className="px-3 py-2">人民币实收</th><th className="px-3 py-2">利润</th><th className="px-3 py-2">贡献</th></tr></thead><tbody>{data.customer_ranking.map((item) => <tr key={item.customer_id} className="border-t"><td className="px-3 py-2"><Link className="text-blue-700" to={`/customers/${item.customer_id}`}>{item.customer_company}</Link></td><td className="px-3 py-2">{item.order_count}（待 {item.pending_order_count}）</td><td className="px-3 py-2">{formatRmb(item.rmb_received_total)}</td><td className="px-3 py-2">{formatRmb(item.profit_total)}</td><td className="px-3 py-2">{item.profit_contribution_percent === null ? "—" : `${Number(item.profit_contribution_percent).toFixed(2)}%`}</td></tr>)}{!data.customer_ranking.length && <tr><td colSpan={5} className="px-3 py-6 text-center text-slate-500">当前时间范围内暂无订单。</td></tr>}</tbody></table></div></div>
        <div><h4 className="font-bold">利润明细</h4><div className="mt-3 overflow-x-auto rounded-lg border"><table className="min-w-[980px] w-full text-left text-sm"><thead className="bg-slate-50 text-slate-500"><tr>{["订单号", "客户", "日期", "订单金额", "人民币实收", "采购", "运费", "利润", "利润率", "核算"].map((label) => <th key={label} className="px-3 py-2">{label}</th>)}</tr></thead><tbody>{data.details.items.map((item) => <tr key={item.id} className="border-t"><td className="px-3 py-2"><Link className="text-blue-700" to={`/orders/${item.id}`}>{item.order_no}</Link></td><td className="px-3 py-2">{item.customer_company}</td><td className="px-3 py-2">{item.order_date}</td><td className="px-3 py-2">{item.currency} {item.order_amount}</td><td className="px-3 py-2">{formatRmb(item.rmb_received_amount)}</td><td className="px-3 py-2">{formatRmb(item.purchase_cost)}</td><td className="px-3 py-2">{formatRmb(item.freight_cost)}</td><td className="px-3 py-2">{item.profit_accounting_status === "Pending" ? "—" : formatRmb(item.profit)}</td><td className="px-3 py-2">{item.profit_margin === null ? "—" : `${Number(item.profit_margin).toFixed(2)}%`}</td><td className="px-3 py-2"><span className={item.profit_accounting_status === "Pending" ? "rounded bg-amber-100 px-2 py-1 text-amber-800" : "rounded bg-emerald-100 px-2 py-1 text-emerald-800"}>{item.profit_accounting_status === "Pending" ? "待核算" : "已核算"}</span></td></tr>)}{!data.details.items.length && <tr><td colSpan={10} className="px-3 py-6 text-center text-slate-500">当前时间范围内暂无订单。</td></tr>}</tbody></table></div>
        {data.details.total > data.details.limit && <div className="mt-3 flex items-center justify-between text-sm text-slate-600"><span>共 {data.details.total} 笔</span><div className="flex gap-2"><button type="button" disabled={loading || detailOffset === 0} onClick={() => void load(period, Math.max(0, detailOffset - data.details.limit))} className="rounded border px-3 py-1 disabled:opacity-50">上一页</button><button type="button" disabled={loading || detailOffset + data.details.limit >= data.details.total} onClick={() => void load(period, detailOffset + data.details.limit)} className="rounded border px-3 py-1 disabled:opacity-50">下一页</button></div></div>}</div>
      </section>
    </>}
  </section>;
}

function Metric({ label, value, subtext }: { label: string; value: string; subtext?: string }) {
  return <div className="rounded bg-white p-3 ring-1 ring-slate-200"><p className="text-xs text-slate-500">{label}</p><p className="mt-1 font-semibold">{value}</p>{subtext && <p className="mt-1 text-xs text-slate-500">{subtext}</p>}</div>;
}
