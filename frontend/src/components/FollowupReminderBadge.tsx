import type { CalculatedFollowupReminderStatus } from "../types";

const badgeClasses: Record<CalculatedFollowupReminderStatus, string> = {
  overdue: "bg-rose-100 text-rose-800",
  today: "bg-orange-100 text-orange-800",
  upcoming: "bg-amber-100 text-amber-800",
  not_needed: "bg-emerald-100 text-emerald-800",
  unfollowed: "bg-violet-100 text-violet-800",
  stage_unset: "bg-slate-100 text-slate-700",
  not_applicable: "bg-slate-100 text-slate-600",
};

const icons: Record<CalculatedFollowupReminderStatus, string> = {
  overdue: "🔴",
  today: "🟠",
  upcoming: "🟡",
  not_needed: "🟢",
  unfollowed: "⚪",
  stage_unset: "⚪",
  not_applicable: "—",
};

export function FollowupReminderBadge({
  status,
  label,
}: {
  status: CalculatedFollowupReminderStatus;
  label: string;
}) {
  return (
    <span className={`inline-flex whitespace-nowrap rounded-full px-2 py-1 text-xs font-semibold ${badgeClasses[status]}`}>
      {icons[status]} {label}
    </span>
  );
}
