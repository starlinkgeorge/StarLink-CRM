import type { OpportunityDealStage } from "../types";

export const opportunityDealStages: OpportunityDealStage[] = [
  "New Inquiry",
  "Contacted",
  "Quoted",
  "Negotiating",
  "Won",
  "Lost",
];

export const opportunityDealStageLabels: Record<OpportunityDealStage, string> = {
  "New Inquiry": "新询盘",
  Contacted: "已联系",
  Quoted: "已报价",
  Negotiating: "谈判中",
  Won: "赢单",
  Lost: "输单",
};

export function opportunityDealStageClass(stage: OpportunityDealStage) {
  if (stage === "Won") return "bg-emerald-100 text-emerald-700";
  if (stage === "Lost") return "bg-slate-200 text-slate-600";
  if (stage === "Negotiating") return "bg-violet-100 text-violet-700";
  if (stage === "Quoted") return "bg-amber-100 text-amber-700";
  if (stage === "Contacted") return "bg-sky-100 text-sky-700";
  return "bg-blue-100 text-blue-700";
}
