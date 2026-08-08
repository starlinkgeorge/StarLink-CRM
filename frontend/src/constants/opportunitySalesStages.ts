import type { OpportunitySalesStage } from "../types";

// V7 compatibility values retained for the Dashboard and the legacy API endpoint.
export const salesStages: OpportunitySalesStage[] = [
  "New Lead",
  "Contacted",
  "Requirement Confirmed",
  "Quotation Sent",
  "Negotiation",
  "Won",
  "Lost",
];

export const salesStageLabels: Record<OpportunitySalesStage, string> = {
  "New Lead": "新线索",
  Contacted: "已联系",
  "Requirement Confirmed": "需求确认",
  "Quotation Sent": "已发送报价",
  Negotiation: "谈判中",
  Won: "已成交",
  Lost: "已丢失",
};

export function salesStageClass(stage: OpportunitySalesStage) {
  if (stage === "Won") return "bg-emerald-100 text-emerald-700";
  if (stage === "Lost") return "bg-slate-200 text-slate-600";
  if (stage === "Negotiation") return "bg-amber-100 text-amber-700";
  if (stage === "Quotation Sent") return "bg-violet-100 text-violet-700";
  return "bg-blue-100 text-blue-700";
}
