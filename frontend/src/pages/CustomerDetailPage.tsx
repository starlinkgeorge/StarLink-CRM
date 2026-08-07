import axios from "axios";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { StatusBadge } from "../components/StatusBadge";
import {
  assignTag,
  createFollowup,
  createTag,
  getCustomer,
  getCustomerTimeline,
  getTags,
  removeTag,
  updateCustomer,
} from "../services/crm";
import { useAuth } from "../store/auth";
import type { CustomerActivity, CustomerDetail, CustomerStatus, Tag } from "../types";

const stages: CustomerStatus[] = ["Lead", "Contacted", "Quotation", "Negotiation", "Won", "Lost"];
const stageText: Record<CustomerStatus, string> = {
  Lead: "新线索",
  Contacted: "已联系",
  Quotation: "报价中",
  Negotiation: "谈判中",
  Won: "已成交",
  Lost: "已流失",
};

function ActivityItem({ activity }: { activity: CustomerActivity }) {
  const isFollowup = activity.event_type === "followup";
  const isStatusChange = activity.event_type === "status_changed";
  const lineColor = isFollowup
    ? "border-blue-500 before:bg-blue-600"
    : isStatusChange
      ? "border-amber-500 before:bg-amber-600"
      : "border-emerald-500 before:bg-emerald-600";
  const title = isFollowup
    ? `${activity.followup_type ?? "跟进"} 跟进`
    : isStatusChange
      ? "销售阶段变更"
      : "创建客户";

  return (
    <article
      className={`relative border-l-2 pb-2 pl-5 before:absolute before:-left-[5px] before:top-1 before:h-2 before:w-2 before:rounded-full ${lineColor}`}
    >
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-sm">
        <strong>{title}</strong>
        <time className="text-slate-500">{new Date(activity.occurred_at).toLocaleString()}</time>
        {activity.next_followup_date && (
          <span className="text-amber-700">下次跟进：{activity.next_followup_date}</span>
        )}
      </div>
      {isStatusChange && activity.new_status && (
        <p className="mt-1 text-sm text-slate-700">
          {activity.old_status ? stageText[activity.old_status] : "未设置"} → {stageText[activity.new_status]}
        </p>
      )}
      {isFollowup && <p className="mt-1 whitespace-pre-wrap text-sm">{activity.content}</p>}
      {activity.event_type === "customer_created" && (
        <p className="mt-1 text-sm text-slate-600">客户档案已创建</p>
      )}
    </article>
  );
}

export function CustomerDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [customer, setCustomer] = useState<CustomerDetail | null>(null);
  const [timeline, setTimeline] = useState<CustomerActivity[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [error, setError] = useState("");
  const [content, setContent] = useState("");
  const [type, setType] = useState("Email");
  const [nextDate, setNextDate] = useState("");
  const [tagId, setTagId] = useState("");
  const [newTag, setNewTag] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const [customerData, timelineData] = await Promise.all([
        getCustomer(id),
        getCustomerTimeline(id),
      ]);
      setCustomer(customerData);
      setTimeline(timelineData);
      setError("");
    } catch {
      setError("无法加载客户详情。");
    }
  }, [id]);

  useEffect(() => {
    void load();
    getTags().then(setTags).catch(() => undefined);
  }, [load]);

  const editable = user?.role !== "Viewer";

  async function addFollowup(event: FormEvent) {
    event.preventDefault();
    if (!customer || !user) return;
    setSaving(true);
    try {
      await createFollowup({
        customer_id: customer.id,
        user_id: user.id,
        type,
        content,
        next_followup_date: nextDate || undefined,
      });
      setContent("");
      setNextDate("");
      await load();
    } catch (err) {
      setError(
        axios.isAxiosError(err)
          ? err.response?.data?.detail ?? "无法保存跟进记录。"
          : "无法保存跟进记录。",
      );
    } finally {
      setSaving(false);
    }
  }

  async function changeStage(salesStage: CustomerStatus) {
    if (!customer) return;
    try {
      await updateCustomer(customer.id, { sales_stage: salesStage });
      await load();
    } catch {
      setError("无法更新客户阶段。");
    }
  }

  async function addTag(event: FormEvent) {
    event.preventDefault();
    if (!customer) return;
    try {
      let selected = tagId ? tags.find((tag) => tag.id === Number(tagId)) : undefined;
      if (!selected && newTag.trim()) {
        selected = await createTag(newTag.trim());
        setTags(await getTags());
        setNewTag("");
      }
      if (selected) {
        await assignTag(customer.id, selected.id);
        setTagId("");
        await load();
      }
    } catch {
      setError("无法添加标签。");
    }
  }

  if (!customer) return <p className="text-slate-500">{error || "加载中…"}</p>;

  return (
    <>
      <Link to="/customers" className="text-sm text-blue-700">← 返回客户列表</Link>
      <div className="mt-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">{customer.country ?? "未填写国家/地区"}</p>
          <h2 className="text-3xl font-bold">{customer.company_name}</h2>
          <p className="mt-1 text-slate-600">{customer.contact_name ?? "未设置主联系人"}</p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={customer.sales_stage} />
          {editable && (
            <select
              value={customer.sales_stage}
              onChange={(event) => void changeStage(event.target.value as CustomerStatus)}
              className="rounded border px-2 py-1 text-sm"
            >
              {stages.map((stage) => <option key={stage} value={stage}>{stageText[stage]}</option>)}
            </select>
          )}
        </div>
      </div>

      {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}

      <section className="mt-7 grid gap-5 lg:grid-cols-2">
        <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <h3 className="font-bold">客户档案</h3>
          <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
            <div><dt className="text-slate-500">等级</dt><dd>{customer.level}</dd></div>
            <div><dt className="text-slate-500">客户类型</dt><dd>{customer.customer_type ?? "—"}</dd></div>
            <div><dt className="text-slate-500">来源</dt><dd>{customer.source ?? "—"}</dd></div>
            <div><dt className="text-slate-500">感兴趣产品</dt><dd>{customer.interested_product ?? "—"}</dd></div>
            <div><dt className="text-slate-500">邮箱</dt><dd>{customer.email ?? "—"}</dd></div>
            <div><dt className="text-slate-500">电话</dt><dd>{customer.phone ?? "—"}</dd></div>
            <div><dt className="text-slate-500">WhatsApp</dt><dd>{customer.whatsapp ?? "—"}</dd></div>
            <div>
              <dt className="text-slate-500">网站</dt>
              <dd>{customer.website ? <a href={customer.website} target="_blank" rel="noreferrer" className="text-blue-700 hover:underline">{customer.website}</a> : "—"}</dd>
            </div>
            <div><dt className="text-slate-500">创建时间</dt><dd>{new Date(customer.created_at).toLocaleString()}</dd></div>
            <div><dt className="text-slate-500">最近更新</dt><dd>{new Date(customer.updated_at).toLocaleString()}</dd></div>
          </dl>

          <h4 className="mt-6 text-sm font-semibold">客户标签</h4>
          <div className="mt-2 flex flex-wrap gap-2">
            {customer.tags.map((tag) => (
              <span key={tag.id} className="rounded-full bg-blue-50 px-3 py-1 text-sm text-blue-700">
                {tag.name}
                {editable && (
                  <button
                    type="button"
                    aria-label={`移除标签 ${tag.name}`}
                    onClick={() => void removeTag(customer.id, tag.id).then(load)}
                    className="ml-2 text-blue-500"
                  >×</button>
                )}
              </span>
            ))}
            {!customer.tags.length && <span className="text-sm text-slate-500">暂未添加标签</span>}
          </div>
          {editable && (
            <form onSubmit={addTag} className="mt-3 flex flex-wrap gap-2">
              <select value={tagId} onChange={(event) => setTagId(event.target.value)} className="rounded border px-2 py-1 text-sm">
                <option value="">选择已有标签</option>
                {tags.filter((tag) => !customer.tags.some((current) => current.id === tag.id)).map((tag) => (
                  <option key={tag.id} value={tag.id}>{tag.name}</option>
                ))}
              </select>
              <input value={newTag} onChange={(event) => setNewTag(event.target.value)} placeholder="或新建标签" className="rounded border px-2 py-1 text-sm" />
              <button className="rounded border px-3 py-1 text-sm">添加</button>
            </form>
          )}
        </article>

        <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <h3 className="font-bold">联系人</h3>
          <div className="mt-4 space-y-3">
            {customer.contacts.length ? customer.contacts.map((contact) => (
              <div key={contact.id} className="rounded-lg bg-slate-50 p-3 text-sm">
                <p className="font-semibold">{contact.name}</p>
                <p className="text-slate-500">{contact.position ?? "—"} · {contact.email ?? contact.phone ?? "—"}</p>
              </div>
            )) : <p className="text-sm text-slate-500">暂无其他联系人。</p>}
          </div>
        </article>
      </section>

      <section className="mt-5 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
        <div className="flex items-center justify-between">
          <h3 className="font-bold">客户活动时间线</h3>
          <span className="text-sm text-slate-500">共 {timeline.length} 条活动</span>
        </div>
        {editable && (
          <form onSubmit={addFollowup} className="mt-4 grid gap-3 md:grid-cols-2">
            <label className="text-sm font-medium">
              跟进方式
              <select value={type} onChange={(event) => setType(event.target.value)} className="mt-1 w-full rounded border px-3 py-2">
                <option>Email</option><option>WhatsApp</option><option>Phone</option><option>Meeting</option>
              </select>
            </label>
            <label className="text-sm font-medium">
              下次跟进日期
              <input type="date" value={nextDate} onChange={(event) => setNextDate(event.target.value)} className="mt-1 w-full rounded border px-3 py-2" />
            </label>
            <label className="text-sm font-medium md:col-span-2">
              跟进内容
              <textarea required maxLength={5000} value={content} onChange={(event) => setContent(event.target.value)} placeholder="记录本次沟通内容、客户需求或下一步动作" className="mt-1 min-h-24 w-full rounded border px-3 py-2" />
            </label>
            <button disabled={saving} className="w-fit rounded bg-blue-600 px-4 py-2 font-semibold text-white disabled:opacity-60">
              {saving ? "保存中…" : "添加跟进"}
            </button>
          </form>
        )}
        <div className="mt-5 space-y-4">
          {timeline.map((activity) => <ActivityItem key={activity.event_id} activity={activity} />)}
          {!timeline.length && <p className="text-sm text-slate-500">暂无客户活动。</p>}
        </div>
      </section>
    </>
  );
}
