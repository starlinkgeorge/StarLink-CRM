import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getOpportunityPipeline } from "../services/crm";
import type { OpportunityPipeline } from "../types";
import { salesStageClass, salesStageLabels } from "./OpportunitiesPage";

export function PipelinePage() {
  const [pipeline, setPipeline] = useState<OpportunityPipeline | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getOpportunityPipeline().then(setPipeline).catch(() => setError("无法加载销售漏斗。"));
  }, []);

  return <>
    <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-sm text-slate-500">按销售阶段查看全部可见商机</p><h2 className="text-3xl font-bold">销售漏斗</h2></div><Link to="/opportunities" className="rounded-lg border border-blue-600 px-4 py-2 font-semibold text-blue-700">商机列表</Link></div>
    {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}
    {!pipeline && !error && <p className="mt-6 text-slate-500">加载中...</p>}
    {pipeline && <div className="mt-6 flex gap-4 overflow-x-auto pb-4">{pipeline.columns.map((column) => <section key={column.sales_stage} className="w-72 shrink-0 rounded-xl bg-slate-100 p-3"><div className="flex items-center justify-between"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${salesStageClass(column.sales_stage)}`}>{salesStageLabels[column.sales_stage]}</span><strong className="text-sm text-slate-600">{column.count}</strong></div><div className="mt-3 space-y-3">{column.opportunities.map((opportunity) => <Link key={opportunity.id} to={`/opportunities/${opportunity.id}`} className="block rounded-lg bg-white p-3 shadow-sm ring-1 ring-slate-200 hover:ring-blue-300"><strong className="line-clamp-2 text-sm">{opportunity.name}</strong><p className="mt-1 truncate text-xs text-slate-500">{opportunity.customer_company}</p><div className="mt-3 flex items-end justify-between gap-2 text-xs"><span>{opportunity.amount ? `${opportunity.currency} ${Number(opportunity.amount).toLocaleString()}` : "未填写金额"}</span><strong>{opportunity.probability}%</strong></div>{opportunity.next_action && <p className="mt-2 line-clamp-2 text-xs text-slate-600">下一步：{opportunity.next_action}</p>}{opportunity.expected_close_date && <p className="mt-1 text-xs text-slate-500">预计：{opportunity.expected_close_date}</p>}</Link>)}{column.opportunities.length === 0 && <p className="py-8 text-center text-sm text-slate-400">暂无商机</p>}</div></section>)}</div>}
  </>;
}
