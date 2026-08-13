import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { getBusinessAnalytics } from "../services/crm";
import type {
  AnalyticsBreakdownItem,
  AnalyticsCurrencyAmount,
  AnalyticsPeriod,
  AnalyticsTrendPoint,
  BusinessAnalyticsOverview,
} from "../types";

const periodOptions: Array<[AnalyticsPeriod, string]> = [
  ["today", "今日"],
  ["week", "本周"],
  ["month", "本月"],
  ["year", "本年"],
  ["custom", "自定义"],
];

const numberFormat = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 });

function currencyText(amounts: AnalyticsCurrencyAmount[]) {
  if (!amounts.length) return "—";
  return amounts.map((item) => `${item.currency} ${numberFormat.format(Number(item.amount))}`).join(" / ");
}

function changeText(value: number | null) {
  if (value === null) return "无上期可比数据";
  if (value === 0) return "较上期持平";
  return `${value > 0 ? "较上期 +" : "较上期 "}${value}%`;
}

function StatCard({ title, value, subtext, to }: { title: string; value: string | number; subtext?: string; to?: string }) {
  const content = <>
    <p className="text-sm text-slate-500">{title}</p>
    <p className="mt-2 text-2xl font-bold tracking-tight text-slate-900">{value}</p>
    {subtext && <p className="mt-2 text-xs text-slate-500">{subtext}</p>}
  </>;
  const className = "rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200 transition";
  return to ? <Link to={to} className={`${className} hover:-translate-y-0.5 hover:shadow-md`}>{content}</Link> : <article className={className}>{content}</article>;
}

function EmptyState({ text = "当前时间范围暂无数据" }: { text?: string }) {
  return <p className="py-8 text-center text-sm text-slate-500">{text}</p>;
}

function BreakdownBars({
  items,
  countryLinks = false,
  showPercentage = true,
}: {
  items: AnalyticsBreakdownItem[];
  countryLinks?: boolean;
  showPercentage?: boolean;
}) {
  if (!items.length) return <EmptyState />;
  const maximum = Math.max(1, ...items.map((item) => item.count));
  return <div className="space-y-3">
    {items.map((item) => {
      const row = <>
        <div className="flex items-center justify-between gap-3 text-sm"><span className="truncate">{item.value}</span><span className="whitespace-nowrap text-slate-500">{item.count}{showPercentage ? ` · ${item.percentage}%` : ""}</span></div>
        <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-blue-600" style={{ width: `${(item.count / maximum) * 100}%` }} /></div>
      </>;
      return countryLinks && item.value !== "Not configured" ? <Link key={item.value} to={`/customers?country=${encodeURIComponent(item.value)}`} className="block rounded-md p-1 hover:bg-blue-50">{row}</Link> : <div key={item.value}>{row}</div>;
    })}
  </div>;
}

function TrendChart({ points }: { points: AnalyticsTrendPoint[] }) {
  if (!points.length) return <EmptyState />;
  const width = 760;
  const height = 240;
  const pad = 28;
  const max = Math.max(1, ...points.flatMap((item) => [item.new_customer_count, item.quotation_count, item.won_opportunity_count]));
  const coordinates = (key: keyof Pick<AnalyticsTrendPoint, "new_customer_count" | "quotation_count" | "won_opportunity_count">) => points.map((item, index) => {
    const x = points.length === 1 ? width / 2 : pad + (index * (width - pad * 2)) / (points.length - 1);
    const y = height - pad - (item[key] / max) * (height - pad * 2);
    return `${x},${y}`;
  }).join(" ");
  const labelIndexes = points.length <= 7 ? points.map((_, index) => index) : [0, Math.floor((points.length - 1) / 2), points.length - 1];
  const lineMeta: Array<[keyof Pick<AnalyticsTrendPoint, "new_customer_count" | "quotation_count" | "won_opportunity_count">, string, string]> = [
    ["new_customer_count", "新增客户", "#2563eb"],
    ["quotation_count", "报价数", "#f59e0b"],
    ["won_opportunity_count", "赢单商机", "#16a34a"],
  ];
  return <>
    <div className="mb-3 flex flex-wrap gap-4 text-xs text-slate-600">{lineMeta.map(([, label, color]) => <span key={label}><i className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />{label}</span>)}</div>
    <div className="overflow-x-auto"><svg viewBox={`0 0 ${width} ${height}`} className="min-w-[620px] w-full" role="img" aria-label="新增客户、报价和赢单趋势图">
      {[0, 0.5, 1].map((ratio) => <line key={ratio} x1={pad} x2={width - pad} y1={height - pad - ratio * (height - pad * 2)} y2={height - pad - ratio * (height - pad * 2)} stroke="#e2e8f0" />)}
      {lineMeta.map(([key, , color]) => <polyline key={key} fill="none" stroke={color} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" points={coordinates(key)} />)}
      {labelIndexes.map((index) => {
        const x = points.length === 1 ? width / 2 : pad + (index * (width - pad * 2)) / (points.length - 1);
        return <text key={index} x={x} y={height - 6} textAnchor="middle" fontSize="11" fill="#64748b">{points[index].bucket}</text>;
      })}
    </svg></div>
  </>;
}

export function BusinessAnalyticsPage() {
  const [period, setPeriod] = useState<AnalyticsPeriod>("month");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [data, setData] = useState<BusinessAnalyticsOverview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (period === "custom" && (!startDate || !endDate)) {
      setData(null);
      setError("");
      return;
    }
    let active = true;
    setLoading(true);
    getBusinessAnalytics({ period, start_date: period === "custom" ? startDate : undefined, end_date: period === "custom" ? endDate : undefined })
      .then((result) => { if (active) { setData(result); setError(""); } })
      .catch((requestError: unknown) => {
        if (!active) return;
        const message = requestError instanceof Error ? requestError.message : "无法加载经营分析数据，请稍后重试。";
        setError(message);
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [period, startDate, endDate]);

  const customerDrilldown = useMemo(() => data ? `/customers?customer_acquired_from=${data.date_range.start_date}&customer_acquired_to=${data.date_range.end_date}` : "/customers", [data]);
  const followup = data?.followup_summary;
  const kpis = data?.kpis;

  return <>
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="text-sm text-slate-500">以 CRM 实际业务数据为准</p><h2 className="mt-1 text-3xl font-bold text-slate-950">经营分析</h2></div>
      <div className="text-sm text-slate-500">{data ? `${data.date_range.start_date} 至 ${data.date_range.end_date} · Asia/Shanghai` : "默认本月"}</div>
    </div>

    <section className="mt-6 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <div className="flex flex-wrap items-center gap-2">
        {periodOptions.map(([value, label]) => <button type="button" key={value} onClick={() => setPeriod(value)} className={`rounded-lg px-4 py-2 text-sm font-medium ${period === value ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}>{label}</button>)}
      </div>
      {period === "custom" && <div className="mt-4 flex flex-wrap items-end gap-3"><label className="text-sm text-slate-700">开始日期<input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} className="mt-1 block rounded-lg border border-slate-300 px-3 py-2" /></label><label className="text-sm text-slate-700">结束日期<input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} className="mt-1 block rounded-lg border border-slate-300 px-3 py-2" /></label>{(!startDate || !endDate) && <span className="pb-2 text-sm text-slate-500">请选择开始和结束日期</span>}</div>}
    </section>

    {error && <p className="mt-4 rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
    {loading && !data && <p className="mt-6 text-sm text-slate-500">正在汇总经营数据…</p>}

    {data && kpis && <>
      <section className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <StatCard title="新增客户" value={kpis.new_customer_count} subtext={changeText(kpis.new_customer_change_percent)} to={customerDrilldown} />
        <StatCard title="报价次数" value={kpis.quotation_count} subtext={changeText(kpis.quotation_count_change_percent)} to="/quotations" />
        <StatCard title="报价金额" value={currencyText(kpis.quotation_amounts)} subtext="按币种分别统计，不跨币种相加" />
        <StatCard title="赢单商机数" value={kpis.won_opportunity_count} subtext={changeText(kpis.won_opportunity_change_percent)} to="/opportunities?deal_stage=Won" />
        <StatCard title="赢单金额" value={currencyText(kpis.won_amounts)} subtext="取赢单商机最新报价的最终金额" />
        <StatCard title="报价 → 赢单转化率" value={kpis.quote_to_win_rate === null ? "—" : `${kpis.quote_to_win_rate}%`} subtext={`已产生报价的商机：${kpis.quoted_opportunity_count}`} />
      </section>

      <section className="mt-6 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><h3 className="text-lg font-bold">业务趋势</h3><p className="mt-1 text-sm text-slate-500">新增客户、报价次数与赢单商机数</p><div className="mt-4"><TrendChart points={data.trend} /></div></section>

      <section className="mt-6 grid gap-5 xl:grid-cols-2">
        <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><h3 className="font-bold">客户来源分析</h3><div className="mt-4"><BreakdownBars items={data.source_analysis} /></div></article>
        <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><h3 className="font-bold">客户国家 / 地区 TOP 10</h3><p className="mt-1 text-xs text-slate-500">点击国家可查看对应客户</p><div className="mt-4"><BreakdownBars items={data.country_analysis} countryLinks /></div></article>
        <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><h3 className="font-bold">客户兴趣产品</h3><div className="mt-4"><BreakdownBars items={data.interested_product_analysis} /></div></article>
        <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><h3 className="font-bold">客户类型</h3><div className="mt-4"><BreakdownBars items={data.customer_type_analysis} /></div></article>
      </section>

      <section className="mt-6 grid gap-5 xl:grid-cols-2">
        <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><h3 className="font-bold">报价产品 TOP 10</h3><div className="mt-4 overflow-x-auto"><table className="min-w-full text-left text-sm"><thead className="border-b text-slate-500"><tr><th className="pb-2 pr-4">SKU</th><th className="pb-2 pr-4">产品</th><th className="pb-2 pr-4">报价次数</th><th className="pb-2 pr-4">数量</th><th className="pb-2">报价金额</th></tr></thead><tbody>{data.quoted_products.map((item) => <tr key={`${item.sku}-${item.product_name}`} className="border-b last:border-0"><td className="py-3 pr-4 whitespace-nowrap">{item.sku}</td><td className="py-3 pr-4">{item.product_name}</td><td className="py-3 pr-4">{item.quotation_count}</td><td className="py-3 pr-4">{numberFormat.format(Number(item.total_quantity))}</td><td className="py-3 whitespace-nowrap">{currencyText(item.quotation_amounts)}</td></tr>)}{!data.quoted_products.length && <tr><td colSpan={5}><EmptyState /></td></tr>}</tbody></table></div></article>
        <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><h3 className="font-bold">销售漏斗</h3><p className="mt-1 text-sm text-slate-500">按客户跟进阶段统计；历史阶段单独保留</p><div className="mt-4"><BreakdownBars items={data.sales_funnel.map((item) => ({ value: item.stage, count: item.count, percentage: 0 }))} showPercentage={false} /></div></article>
      </section>

      <section className="mt-6 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-bold">跟进效率</h3><p className="mt-1 text-sm text-slate-500">提醒范围沿用现有客户跟进提醒规则</p></div><Link to="/followup-reminders" className="text-sm font-medium text-blue-700">打开跟进提醒 →</Link></div><div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5"><StatCard title="本周期新增跟进" value={followup?.created_followup_count ?? 0} /><StatCard title="已逾期" value={followup?.overdue_count ?? 0} to="/followup-reminders?status=overdue" /><StatCard title="今天需要跟进" value={followup?.today_count ?? 0} to="/followup-reminders?status=today" /><StatCard title="未来 3 天" value={followup?.upcoming_count ?? 0} to="/followup-reminders?status=upcoming" /><StatCard title="尚未跟进" value={followup?.unfollowed_count ?? 0} to="/followup-reminders?status=unfollowed" /></div></section>
    </>}
  </>;
}
