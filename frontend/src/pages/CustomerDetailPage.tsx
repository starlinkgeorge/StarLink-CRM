import axios from "axios";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { StatusBadge } from "../components/StatusBadge";
import { CustomerArchiveProfile } from "../components/CustomerArchiveProfile";
import {
  assignTag,
  createFollowup,
  createTag,
  deleteFollowup,
  deleteFollowupAttachment,
  downloadFollowupAttachment,
  getCustomerCenter,
  getTags,
  removeTag,
  updateFollowup,
  updateCustomerScore,
  updateCustomer,
  uploadFollowupAttachment,
} from "../services/crm";
import { useAuth } from "../store/auth";
import type { CustomerActivity, CustomerCenter, CustomerScoreHistory, CustomerStatus, FollowUp, FollowUpType, OpportunityListItem, OpportunityStage, QuotationListItem, QuotationStatus, Tag } from "../types";

const stages: CustomerStatus[] = ["Lead", "Contacted", "Quotation", "Negotiation", "Won", "Lost"];
const stageText: Record<CustomerStatus, string> = {
  Lead: "新线索",
  Contacted: "已联系",
  Quotation: "报价中",
  Negotiation: "谈判中",
  Won: "已成交",
  Lost: "已流失",
};
const opportunityStageText: Record<OpportunityStage, string> = {
  Lead: "初始商机", Qualified: "已确认", Proposal: "方案/报价",
  Negotiation: "谈判中", Won: "已成交", Lost: "已丢失",
};
const quotationStatusText: Record<QuotationStatus, string> = {
  Draft: "草稿", Sent: "已发送", Accepted: "已接受", Rejected: "已拒绝", Expired: "已过期",
};

function localDateString() {
  const now = new Date();
  const localTime = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return localTime.toISOString().slice(0, 10);
}

function ReminderBadge({ followupDate }: { followupDate: string }) {
  const today = localDateString();
  if (followupDate < today) {
    return <span className="rounded-full bg-rose-100 px-2 py-0.5 text-xs font-medium text-rose-700">已逾期 · {followupDate}</span>;
  }
  if (followupDate === today) {
    return <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">今日待跟进</span>;
  }
  return <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">计划跟进 · {followupDate}</span>;
}

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
        {activity.followup_date && <span className="text-slate-500">{activity.followup_date}</span>}
        {activity.next_followup_date && <ReminderBadge followupDate={activity.next_followup_date} />}
        {activity.opportunity_id && <Link to={`/opportunities/${activity.opportunity_id}`} className="text-blue-700">关联商机</Link>}
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
  const [customer, setCustomer] = useState<CustomerCenter | null>(null);
  const [timeline, setTimeline] = useState<CustomerActivity[]>([]);
  const [opportunities, setOpportunities] = useState<OpportunityListItem[]>([]);
  const [quotations, setQuotations] = useState<QuotationListItem[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [scoreHistory, setScoreHistory] = useState<CustomerScoreHistory[]>([]);
  const [error, setError] = useState("");
  const [content, setContent] = useState("");
  const [type, setType] = useState<FollowUpType>("Email");
  const [followupDate, setFollowupDate] = useState(localDateString());
  const [nextDate, setNextDate] = useState("");
  const [opportunityId, setOpportunityId] = useState("");
  const [attachmentFiles, setAttachmentFiles] = useState<File[]>([]);
  const [attachmentInputKey, setAttachmentInputKey] = useState(0);
  const [editingFollowupId, setEditingFollowupId] = useState<number | null>(null);
  const [tagId, setTagId] = useState("");
  const [newTag, setNewTag] = useState("");
  const [scoreInput, setScoreInput] = useState("");
  const [scoreReason, setScoreReason] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const center = await getCustomerCenter(id);
      setCustomer(center);
      setTimeline(center.activities);
      setOpportunities(center.opportunities);
      setQuotations(center.quotations);
      setScoreHistory(center.score_history);
      setScoreInput(String(center.customer_score));
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
  // V10 returns the server-calculated current reminder.  It avoids relying on
  // the page's visible-history ordering and remains correct after edits/deletes.
  const currentReminder = customer?.next_followup_date;

  async function addFollowup(event: FormEvent) {
    event.preventDefault();
    if (!customer || !user) return;
    setSaving(true);
    try {
      const payload = {
        opportunity_id: opportunityId ? Number(opportunityId) : null,
        type,
        followup_date: followupDate,
        content,
        next_followup_date: nextDate || (editingFollowupId ? null : undefined),
      };
      const followup = editingFollowupId
        ? await updateFollowup(editingFollowupId, payload)
        : await createFollowup({ customer_id: customer.id, user_id: user.id, ...payload });
      await Promise.all(
        attachmentFiles.map((file) => uploadFollowupAttachment(followup.id, file)),
      );
      setContent("");
      setFollowupDate(localDateString());
      setNextDate("");
      setOpportunityId("");
      setAttachmentFiles([]);
      setAttachmentInputKey((value) => value + 1);
      setEditingFollowupId(null);
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

  function editFollowup(followup: FollowUp) {
    setEditingFollowupId(followup.id);
    setType(followup.type);
    setFollowupDate(followup.followup_date);
    setContent(followup.content);
    setNextDate(followup.next_followup_date ?? "");
    setOpportunityId(followup.opportunity_id ? String(followup.opportunity_id) : "");
    setAttachmentFiles([]);
    setAttachmentInputKey((value) => value + 1);
  }

  function cancelFollowupEdit() {
    setEditingFollowupId(null);
    setType("Email");
    setFollowupDate(localDateString());
    setContent("");
    setNextDate("");
    setOpportunityId("");
    setAttachmentFiles([]);
    setAttachmentInputKey((value) => value + 1);
  }

  async function removeFollowupRecord(followup: FollowUp) {
    if (!window.confirm("确认删除这条跟进记录及其附件吗？")) return;
    try {
      await deleteFollowup(followup.id);
      if (editingFollowupId === followup.id) cancelFollowupEdit();
      await load();
    } catch {
      setError("无法删除跟进记录。");
    }
  }

  async function removeFollowupFile(followupId: number, attachmentId: number) {
    try {
      await deleteFollowupAttachment(followupId, attachmentId);
      await load();
    } catch {
      setError("无法删除附件。");
    }
  }

  async function openFollowupFile(followupId: number, attachmentId: number) {
    try {
      const blob = await downloadFollowupAttachment(followupId, attachmentId);
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener,noreferrer");
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch {
      setError("无法下载附件。");
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

  async function saveScore(event: FormEvent) {
    event.preventDefault();
    if (!customer || scoreInput === "") return;
    const score = Number(scoreInput);
    if (!Number.isInteger(score) || score < 0 || score > 100) {
      setError("评分必须是 0 到 100 的整数。");
      return;
    }
    setSaving(true);
    try {
      await updateCustomerScore(customer.id, { score, reason: scoreReason.trim() || undefined });
      setScoreReason("");
      await load();
    } catch (err) {
      setError(axios.isAxiosError(err) ? err.response?.data?.detail ?? "无法保存客户评分。" : "无法保存客户评分。");
    } finally {
      setSaving(false);
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
  const attachments = customer.followups.flatMap((followup) =>
    followup.attachments.map((attachment) => ({ attachment, followup })),
  );

  return (
    <>
      <Link to="/customers" className="text-sm text-blue-700">← 返回客户列表</Link>
      <div className="mt-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">客户中心 · {customer.country ?? "未填写国家/地区"}</p>
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

      <section className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <article className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200"><p className="text-sm text-slate-500">联系人</p><p className="mt-1 text-2xl font-bold">{customer.contacts.length}</p></article>
        <article className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200"><p className="text-sm text-slate-500">商机</p><p className="mt-1 text-2xl font-bold">{opportunities.length}</p></article>
        <article className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200"><p className="text-sm text-slate-500">报价</p><p className="mt-1 text-2xl font-bold">{quotations.length}</p></article>
        <article className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200"><p className="text-sm text-slate-500">跟进记录</p><p className="mt-1 text-2xl font-bold">{customer.followups.length}</p></article>
        <article className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200"><p className="text-sm text-slate-500">客户附件</p><p className="mt-1 text-2xl font-bold">{attachments.length}</p></article>
      </section>

      <section className="mt-5 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">当前跟进提醒</h3>
            <p className="mt-1 text-sm text-slate-500">以客户最新一条跟进记录设置的日期为准</p>
          </div>
          {currentReminder ? <ReminderBadge followupDate={currentReminder} /> : <span className="text-sm text-slate-500">暂无待跟进提醒</span>}
        </div>
      </section>

      <section className="mt-7">
        <CustomerArchiveProfile customer={customer} editable={editable} onSaved={load} />
      </section>

      <section className="mt-7 grid gap-5 lg:grid-cols-2">
        <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <h3 className="font-bold">客户档案</h3>
          <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
            <div><dt className="text-slate-500">客户分类</dt><dd>{customer.category?.name ?? "—"}</dd></div>
            <div><dt className="text-slate-500">客户评分</dt><dd className="font-semibold">{customer.customer_score} / 100（{customer.level}）</dd></div>
            <div><dt className="text-slate-500">等级</dt><dd>{customer.level}</dd></div>
            <div><dt className="text-slate-500">客户类型</dt><dd>{customer.customer_type ?? "—"}</dd></div>
            <div><dt className="text-slate-500">来源</dt><dd>{customer.source ?? "—"}</dd></div>
            <div><dt className="text-slate-500">来源平台</dt><dd>{customer.source_platform ?? "—"}</dd></div>
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
          {customer.original_inquiry && (
            <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm">
              <p className="font-medium text-slate-700">原始询盘内容</p>
              <p className="mt-1 whitespace-pre-wrap text-slate-600">{customer.original_inquiry}</p>
            </div>
          )}
          {editable && (
            <form onSubmit={saveScore} className="mt-5 rounded-lg bg-slate-50 p-3">
              <p className="text-sm font-semibold">更新客户等级评分</p>
              <div className="mt-2 flex flex-wrap gap-2">
                <input type="number" min="0" max="100" value={scoreInput} onChange={(event) => setScoreInput(event.target.value)} className="w-28 rounded border px-2 py-1 text-sm" />
                <input value={scoreReason} onChange={(event) => setScoreReason(event.target.value)} maxLength={500} placeholder="评分原因（可选）" className="min-w-52 flex-1 rounded border px-2 py-1 text-sm" />
                <button disabled={saving} className="rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white disabled:opacity-60">保存评分</button>
              </div>
              <p className="mt-1 text-xs text-slate-500">80-100 自动为 A，50-79 为 B，0-49 为 C。</p>
            </form>
          )}
          {scoreHistory.length > 0 && (
            <div className="mt-4 text-xs text-slate-500">
              最近评分：{scoreHistory.slice(0, 3).map((item) => `${item.new_score}分（${new Date(item.created_at).toLocaleDateString()}）`).join(" · ")}
            </div>
          )}

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
                <p className="text-slate-500">{contact.position ?? "未填写职位"}</p>
                <p className="mt-1 text-slate-600">{contact.email ?? "未填写邮箱"}</p>
                <p className="text-slate-600">{contact.phone ?? contact.whatsapp ?? "未填写电话"}</p>
              </div>
            )) : <p className="text-sm text-slate-500">暂无其他联系人。</p>}
          </div>
        </article>
      </section>

      <section className="mt-5 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
        <div className="flex items-center justify-between">
          <h3 className="font-bold">商机</h3>
          <Link to="/opportunities" className="text-sm text-blue-700">查看全部商机</Link>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {opportunities.map((opportunity) => (
            <Link key={opportunity.id} to={`/opportunities/${opportunity.id}`} className="rounded-lg bg-slate-50 p-4 hover:bg-blue-50">
              <div className="flex items-start justify-between gap-2"><strong>{opportunity.name}</strong><span className="whitespace-nowrap rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-700">{opportunityStageText[opportunity.stage]}</span></div>
              <p className="mt-2 truncate text-sm text-slate-600">{opportunity.interested_product ?? "未填写产品需求"}</p>
              <p className="mt-2 text-sm font-medium">{opportunity.amount ? `${opportunity.currency} ${Number(opportunity.amount).toLocaleString()}` : "金额未填写"}</p>
            </Link>
          ))}
          {!opportunities.length && <p className="text-sm text-slate-500">该客户暂无商机。</p>}
        </div>
      </section>

      <section className="mt-5 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
        <div className="flex items-center justify-between gap-3">
          <div><h3 className="font-bold">报价</h3><p className="mt-1 text-sm text-slate-500">客户所有报价及其当前状态</p></div>
          <Link to="/quotations" className="text-sm text-blue-700">查看全部报价</Link>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {quotations.map((quotation) => (
            <article key={quotation.id} className="rounded-lg bg-slate-50 p-4">
              <div className="flex items-start justify-between gap-2"><Link to={`/quotations/${quotation.id}`} className="font-semibold text-blue-700">{quotation.quotation_number}</Link><span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs">{quotationStatusText[quotation.status]}</span></div>
              <p className="mt-2 text-sm">{quotation.currency} {Number(quotation.total_amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
              {quotation.opportunity_id && <Link to={`/opportunities/${quotation.opportunity_id}`} className="mt-2 inline-block text-sm text-blue-700">{quotation.opportunity_name ?? "关联商机"}</Link>}
              <p className="mt-2 text-xs text-slate-500">更新于 {new Date(quotation.updated_at).toLocaleString()}</p>
            </article>
          ))}
          {!quotations.length && <p className="text-sm text-slate-500">暂无报价；可在商机详情中创建第一份报价。</p>}
        </div>
      </section>

      <section className="mt-5 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
        <div className="flex items-center justify-between gap-3"><div><h3 className="font-bold">客户附件</h3><p className="mt-1 text-sm text-slate-500">来自跟进记录的文件，统一在客户中心查看。</p></div><span className="text-sm text-slate-500">共 {attachments.length} 个</span></div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {attachments.map(({ attachment, followup }) => (
            <article key={attachment.id} className="rounded-lg bg-slate-50 p-3 text-sm"><button type="button" onClick={() => void openFollowupFile(followup.id, attachment.id)} className="font-medium text-blue-700">{attachment.file_name}</button><p className="mt-1 text-slate-500">{followup.type} · {followup.followup_date}</p><p className="text-xs text-slate-500">{Math.ceil(attachment.size_bytes / 1024)} KB · {new Date(attachment.created_at).toLocaleString()}</p></article>
          ))}
          {!attachments.length && <p className="text-sm text-slate-500">暂无客户附件。</p>}
        </div>
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
              <select value={type} onChange={(event) => setType(event.target.value as FollowUpType)} className="mt-1 w-full rounded border px-3 py-2">
                <option>Email</option><option>WhatsApp</option><option>Alibaba</option><option>Phone</option><option>Meeting</option>
              </select>
            </label>
            <label className="text-sm font-medium">
              跟进日期
              <input required type="date" value={followupDate} onChange={(event) => setFollowupDate(event.target.value)} className="mt-1 w-full rounded border px-3 py-2" />
            </label>
            <label className="text-sm font-medium">
              下次跟进日期
              <input type="date" value={nextDate} onChange={(event) => setNextDate(event.target.value)} className="mt-1 w-full rounded border px-3 py-2" />
            </label>
            <label className="text-sm font-medium md:col-span-2">
              关联商机
              <select value={opportunityId} onChange={(event) => setOpportunityId(event.target.value)} className="mt-1 w-full rounded border px-3 py-2">
                <option value="">仅关联客户</option>
                {opportunities.map((opportunity) => <option key={opportunity.id} value={opportunity.id}>{opportunity.name}</option>)}
              </select>
            </label>
            <label className="text-sm font-medium md:col-span-2">
              跟进内容
              <textarea required maxLength={5000} value={content} onChange={(event) => setContent(event.target.value)} placeholder="记录本次沟通内容、客户需求或下一步动作" className="mt-1 min-h-24 w-full rounded border px-3 py-2" />
            </label>
            <label className="text-sm font-medium md:col-span-2">
              附件（PDF、图片、Office 或 TXT，单个不超过 10 MB）
              <input key={attachmentInputKey} type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.webp,.doc,.docx,.xls,.xlsx,.txt" onChange={(event) => setAttachmentFiles(Array.from(event.target.files ?? []))} className="mt-1 block w-full text-sm" />
              {attachmentFiles.length > 0 && <p className="mt-1 text-xs text-slate-500">待上传：{attachmentFiles.map((file) => file.name).join("、")}</p>}
            </label>
            <div className="flex flex-wrap gap-2">
              <button disabled={saving} className="w-fit rounded bg-blue-600 px-4 py-2 font-semibold text-white disabled:opacity-60">
                {saving ? "保存中…" : editingFollowupId ? "保存修改" : "添加跟进"}
              </button>
              {editingFollowupId && <button type="button" onClick={cancelFollowupEdit} className="rounded border px-4 py-2 font-semibold">取消编辑</button>}
            </div>
          </form>
        )}
        <div className="mt-6 border-t pt-5">
          <h4 className="font-semibold">跟进记录</h4>
          <div className="mt-3 space-y-3">
            {customer.followups.map((followup) => (
              <article key={followup.id} className="rounded-lg bg-slate-50 p-4 text-sm">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <strong>{followup.type}</strong>
                    <span className="ml-2 text-slate-500">{followup.followup_date}</span>
                    {followup.opportunity_id && <Link to={`/opportunities/${followup.opportunity_id}`} className="ml-2 text-blue-700">关联商机</Link>}
                  </div>
                  {editable && <div className="flex gap-3"><button type="button" onClick={() => editFollowup(followup)} className="text-blue-700">编辑</button><button type="button" onClick={() => void removeFollowupRecord(followup)} className="text-rose-600">删除</button></div>}
                </div>
                <p className="mt-2 whitespace-pre-wrap">{followup.content}</p>
                {followup.next_followup_date && <div className="mt-2"><ReminderBadge followupDate={followup.next_followup_date} /></div>}
                {followup.attachments.length > 0 && <div className="mt-3 flex flex-wrap gap-2">{followup.attachments.map((attachment) => <span key={attachment.id} className="rounded border bg-white px-2 py-1 text-xs"><button type="button" onClick={() => void openFollowupFile(followup.id, attachment.id)} className="text-blue-700">{attachment.file_name}</button>{editable && <button type="button" onClick={() => void removeFollowupFile(followup.id, attachment.id)} className="ml-2 text-rose-600">×</button>}</span>)}</div>}
              </article>
            ))}
            {!customer.followups.length && <p className="text-sm text-slate-500">暂无跟进记录。</p>}
          </div>
        </div>
        <div className="mt-5 space-y-4">
          {timeline.map((activity) => <ActivityItem key={activity.event_id} activity={activity} />)}
          {!timeline.length && <p className="text-sm text-slate-500">暂无客户活动。</p>}
        </div>
      </section>
    </>
  );
}
