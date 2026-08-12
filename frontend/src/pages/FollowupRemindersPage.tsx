import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { FollowupReminderBadge } from "../components/FollowupReminderBadge";
import { getCustomerFollowupReminders } from "../services/crm";
import type {
  CalculatedFollowupReminderStatus,
  CustomerFollowupReminderPage,
} from "../types";

type Filter = "" | CalculatedFollowupReminderStatus;

const filterCards: Array<{
  filter: Filter;
  title: string;
  countKey: "overdue_count" | "today_count" | "upcoming_count" | "unfollowed_count";
  className: string;
}> = [
  { filter: "overdue", title: "已逾期", countKey: "overdue_count", className: "border-rose-200 bg-rose-50 text-rose-800" },
  { filter: "today", title: "今天需要跟进", countKey: "today_count", className: "border-orange-200 bg-orange-50 text-orange-800" },
  { filter: "upcoming", title: "未来3天", countKey: "upcoming_count", className: "border-amber-200 bg-amber-50 text-amber-800" },
  { filter: "unfollowed", title: "尚未跟进", countKey: "unfollowed_count", className: "border-violet-200 bg-violet-50 text-violet-800" },
];

const dateOnly = (value: string | null) => value?.slice(0, 10) ?? "—";
const dash = (value: string | number | null) => value === null || value === "" ? "—" : value;

function validFilter(value: string | null): Filter {
  return ["overdue", "today", "upcoming", "unfollowed", "not_needed", "stage_unset"].includes(value ?? "")
    ? value as CalculatedFollowupReminderStatus
    : "";
}

export function FollowupRemindersPage() {
  const [params, setParams] = useSearchParams();
  const filter = validFilter(params.get("status"));
  const [data, setData] = useState<CustomerFollowupReminderPage | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setData(await getCustomerFollowupReminders(filter || undefined));
      setError("");
    } catch {
      setError("无法加载跟进提醒，请稍后重试。");
    }
  }, [filter]);

  useEffect(() => { void load(); }, [load]);

  function setFilter(value: Filter) {
    setParams(value ? { status: value } : {});
  }

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">按最近跟进日期与跟进阶段自动计算 · 中国时间</p>
          <h2 className="mt-1 text-3xl font-bold">跟进提醒</h2>
        </div>
        {filter && <button type="button" onClick={() => setFilter("")} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold">查看全部</button>}
      </div>

      <section className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {filterCards.map((card) => (
          <button
            type="button"
            key={card.filter}
            onClick={() => setFilter(filter === card.filter ? "" : card.filter)}
            className={`rounded-xl border p-5 text-left shadow-sm transition hover:-translate-y-0.5 ${card.className} ${filter === card.filter ? "ring-2 ring-slate-900 ring-offset-2" : ""}`}
          >
            <p className="text-sm font-medium">{card.title}</p>
            <p className="mt-2 text-3xl font-bold">{data?.summary[card.countKey] ?? "—"}</p>
          </button>
        ))}
      </section>

      {error && <p className="mt-5 text-sm text-rose-600">{error}</p>}
      <section className="mt-6 overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
        <div className="overflow-x-auto">
          <table className="min-w-[1480px] text-left text-sm">
            <thead className="bg-slate-50 text-slate-500"><tr>
              <th className="px-4 py-3">客户名</th><th className="px-4 py-3">公司名</th><th className="px-4 py-3">国家</th><th className="px-4 py-3">客户等级</th><th className="px-4 py-3">客户总分</th><th className="px-4 py-3">跟进阶段</th><th className="px-4 py-3">最近跟进日期</th><th className="px-4 py-3">建议跟进日期</th><th className="px-4 py-3">跟进提醒</th><th className="px-4 py-3">WhatsApp</th><th className="px-4 py-3">邮箱</th>
            </tr></thead>
            <tbody>
              {data?.items.map((item) => <tr key={item.id} className="border-t align-top">
                <td className="whitespace-nowrap px-4 py-3">{dash(item.customer_name)}</td>
                <td className="px-4 py-3 font-semibold text-blue-700"><Link to={`/customers/${item.id}`}>{item.company_name}</Link></td>
                <td className="whitespace-nowrap px-4 py-3">{dash(item.country)}</td><td className="whitespace-nowrap px-4 py-3">{dash(item.customer_level_value)}</td><td className="whitespace-nowrap px-4 py-3">{dash(item.customer_total_score)}</td>
                <td className="whitespace-nowrap px-4 py-3">{dash(item.followup_stage)}</td><td className="whitespace-nowrap px-4 py-3">{dateOnly(item.latest_followup_date)}</td><td className="whitespace-nowrap px-4 py-3">{dateOnly(item.suggested_followup_date)}</td>
                <td className="px-4 py-3"><FollowupReminderBadge status={item.followup_reminder.status} label={item.followup_reminder.label} /></td>
                <td className="whitespace-nowrap px-4 py-3">{dash(item.whatsapp)}</td><td className="whitespace-nowrap px-4 py-3">{dash(item.email)}</td>
              </tr>)}
              {data?.items.length === 0 && <tr><td colSpan={11} className="px-4 py-12 text-center text-slate-500">没有符合条件的客户。</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
