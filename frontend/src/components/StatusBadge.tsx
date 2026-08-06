import type { CustomerStatus } from "../types";

const colors: Record<CustomerStatus, string> = { Lead: "bg-slate-100 text-slate-700", Contacted: "bg-blue-100 text-blue-700", Quotation: "bg-violet-100 text-violet-700", Negotiation: "bg-amber-100 text-amber-800", Won: "bg-emerald-100 text-emerald-700", Lost: "bg-rose-100 text-rose-700" };
export function StatusBadge({ status }: { status: CustomerStatus }) { return <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${colors[status]}`}>{status}</span>; }
