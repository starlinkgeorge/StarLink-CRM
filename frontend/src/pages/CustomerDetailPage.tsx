import axios from "axios";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { CustomerArchiveProfile } from "../components/CustomerArchiveProfile";
import {
  createQuotation,
  createFollowup,
  deleteFollowup,
  deleteFollowupAttachment,
  downloadFollowupAttachment,
  getCustomerCenter,
  getMailMessages,
  getOrders,
  updateFollowup,
  uploadFollowupAttachment,
} from "../services/crm";
import { useAuth } from "../store/auth";
import type { CustomerActivity, CustomerCenter, CustomerStatus, FollowUp, FollowUpType, MailMessage, OpportunityDealStage, OpportunityListItem, Order, QuotationListItem, QuotationStatus } from "../types";

const stageText: Record<CustomerStatus, string> = {
  Lead: "新线索",
  Contacted: "已联系",
  Quotation: "报价中",
  Negotiation: "谈判中",
  Won: "已成交",
  Lost: "已流失",
};
const opportunityStageText: Record<OpportunityDealStage, string> = {
  "New Inquiry": "新询盘", Contacted: "已联系", Quoted: "已报价",
  Negotiating: "谈判中", Won: "已成交", Lost: "已丢单",
};
const quotationStatusText: Record<QuotationStatus, string> = {
  Draft: "草稿", Sent: "已发送", Accepted: "已接受", Rejected: "已拒绝", Expired: "已过期",
};
type DetailTab = "followups" | "opportunities" | "quotations" | "orders" | "contacts" | "attachments" | "emails";

function localDateString() {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(new Date());
  const part = (type: string) => parts.find((item) => item.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
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

function followupCountdown(followupDate: string) {
  const today = localDateString();
  const toUtcMillis = (value: string) => {
    const [year, month, day] = value.split("-").map(Number);
    return Date.UTC(year, month - 1, day);
  };
  const millis = toUtcMillis(followupDate) - toUtcMillis(today);
  const days = Math.round(millis / 86_400_000);
  if (days < 0) return `已逾期 ${Math.abs(days)} 天`;
  if (days === 0) return "今天需要跟进";
  return `还有 ${days} 天`;
}

function mailDateTime(value: string | null) {
  return value ? new Intl.DateTimeFormat("zh-CN", { timeZone: "Asia/Shanghai", dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "—";
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
  const navigate = useNavigate();
  const { user } = useAuth();
  const [customer, setCustomer] = useState<CustomerCenter | null>(null);
  const [timeline, setTimeline] = useState<CustomerActivity[]>([]);
  const [opportunities, setOpportunities] = useState<OpportunityListItem[]>([]);
  const [quotations, setQuotations] = useState<QuotationListItem[]>([]);
  const [error, setError] = useState("");
  const [content, setContent] = useState("");
  const [type, setType] = useState<FollowUpType>("Email");
  const [followupDate, setFollowupDate] = useState(localDateString());
  const [nextDate, setNextDate] = useState("");
  const [opportunityId, setOpportunityId] = useState("");
  const [attachmentFiles, setAttachmentFiles] = useState<File[]>([]);
  const [attachmentInputKey, setAttachmentInputKey] = useState(0);
  const [editingFollowupId, setEditingFollowupId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [creatingQuotation, setCreatingQuotation] = useState(false);
  const [orders, setOrders] = useState<Order[]>([]);
  const [emails, setEmails] = useState<MailMessage[]>([]);
  const [activeTab, setActiveTab] = useState<DetailTab>("followups");
  const [profileEditRequest, setProfileEditRequest] = useState(0);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const [center, orderPage, mailPage] = await Promise.all([
        getCustomerCenter(id),
        getOrders({ limit: 20, offset: 0, customer_id: Number(id) }),
        getMailMessages({ customer_id: Number(id), folder: "all", limit: 100 }),
      ]);
      setCustomer(center);
      setTimeline(center.activities);
      setOpportunities(center.opportunities);
      setQuotations(center.quotations);
      setOrders(orderPage.items);
      setEmails(mailPage.items);
      setError("");
    } catch {
      setError("无法加载客户详情。");
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const editable = user?.role !== "Viewer";

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

  async function createCustomerQuotation() {
    if (!customer || !editable || creatingQuotation) return;
    setCreatingQuotation(true);
    setError("");
    try {
      const quotation = await createQuotation({ customer_id: customer.id });
      navigate(`/quotations/${quotation.id}`, {
        state: { notice: "报价草稿已创建，请在此添加产品并填写付款、交期和运费。" },
      });
    } catch {
      setError("无法创建报价草稿，请确认客户存在且您有管理权限后重试。");
      setCreatingQuotation(false);
    }
  }

  if (!customer) return <p className="text-slate-500">{error || "加载中…"}</p>;
  const attachments = customer.followups.flatMap((followup) =>
    followup.attachments.map((attachment) => ({ attachment, followup })),
  );

  const suggestedFollowupDate = customer.suggested_followup_date;
  const tabItems: { id: DetailTab; label: string; count: number }[] = [
    { id: "followups", label: "跟进记录", count: customer.followups.length },
    { id: "opportunities", label: "商机", count: opportunities.length },
    { id: "quotations", label: "报价", count: quotations.length },
    { id: "orders", label: "订单", count: orders.length },
    { id: "contacts", label: "联系人", count: customer.contacts.length },
    { id: "attachments", label: "附件", count: attachments.length },
    { id: "emails", label: "邮件", count: emails.length },
  ];

  return (
    <>
      <Link to="/customers" className="text-sm text-blue-700">← 返回客户列表</Link>
      <header className="mt-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">客户中心 · {customer.country ?? "未填写国家/地区"}</p>
          <div className="flex flex-wrap items-center gap-2"><h2 className="text-2xl font-bold text-slate-950">{customer.company_name}</h2>{customer.is_cold_customer && <span className="rounded-full bg-orange-100 px-2 py-0.5 text-xs font-semibold text-orange-800">冷客户</span>}</div>
          <p className="mt-0.5 text-sm text-slate-600">{customer.contact_name ?? "未设置主联系人"}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {editable && <Link to={`/orders/new?customer_id=${customer.id}`} className="rounded border border-emerald-600 px-3 py-1.5 text-sm font-medium text-emerald-700 hover:bg-emerald-50">新建订单</Link>}
          {editable && <button type="button" onClick={() => void createCustomerQuotation()} disabled={creatingQuotation} className="rounded bg-blue-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60">{creatingQuotation ? "正在创建…" : "创建报价"}</button>}
          {editable && <button type="button" onClick={() => setProfileEditRequest((value) => value + 1)} className="rounded border border-blue-600 px-3 py-1.5 text-sm font-medium text-blue-700 hover:bg-blue-50">编辑客户档案</button>}
        </div>
      </header>

      {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}

      <section className="mt-4 flex flex-wrap divide-x divide-slate-200 overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
        {tabItems.map((item) => <div key={item.id} className="min-w-28 flex-1 px-4 py-2 text-center"><span className="text-xs text-slate-500">{item.label}</span><span className="ml-2 text-lg font-bold text-slate-800">{item.count}</span></div>)}
      </section>

      <section className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-white px-4 py-3 shadow-sm ring-1 ring-slate-200">
        <h3 className="text-sm font-semibold">跟进提醒</h3>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span className="text-slate-600">下次建议跟进：<strong className="text-slate-900">{suggestedFollowupDate ?? "—"}</strong></span>
          {suggestedFollowupDate && <span className={suggestedFollowupDate < localDateString() ? "font-medium text-rose-700" : "font-medium text-blue-700"}>{followupCountdown(suggestedFollowupDate)}</span>}
        </div>
      </section>

      <section className="mt-4">
        <CustomerArchiveProfile customer={customer} editable={editable} onSaved={load} editRequest={profileEditRequest} showEditAction={false} />
      </section>

      {customer.original_inquiry && <details className="mt-3 rounded-xl bg-white p-4 text-sm shadow-sm ring-1 ring-slate-200"><summary className="cursor-pointer font-medium text-slate-700">原始询盘内容</summary><p className="mt-2 whitespace-pre-wrap text-slate-600">{customer.original_inquiry}</p></details>}

      <section className="mt-4 overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
        <div className="flex overflow-x-auto border-b border-slate-200 px-2">
          {tabItems.map((item) => <button key={item.id} type="button" onClick={() => setActiveTab(item.id)} className={`whitespace-nowrap border-b-2 px-3 py-3 text-sm font-medium ${activeTab === item.id ? "border-blue-600 text-blue-700" : "border-transparent text-slate-500 hover:text-slate-800"}`}>{item.label}<span className="ml-1 text-xs">{item.count}</span></button>)}
        </div>
        <div className="p-4">
          {activeTab === "followups" && <>
        <div className="flex items-center justify-between">
          <h3 className="font-bold">跟进记录</h3>
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
          </>}
          {activeTab === "opportunities" && <><div className="flex items-center justify-between"><h3 className="font-bold">商机</h3><Link to="/opportunities" className="text-sm text-blue-700">查看全部商机</Link></div><div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{opportunities.map((opportunity) => <Link key={opportunity.id} to={`/opportunities/${opportunity.id}`} className="rounded-lg bg-slate-50 p-3 hover:bg-blue-50"><div className="flex items-start justify-between gap-2"><strong>{opportunity.name}</strong><span className="whitespace-nowrap rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-700">{opportunityStageText[opportunity.deal_stage]}</span></div><p className="mt-2 truncate text-sm text-slate-600">{opportunity.interested_product ?? "未填写产品需求"}</p><p className="mt-2 text-sm font-medium">{opportunity.amount ? `${opportunity.currency} ${Number(opportunity.amount).toLocaleString()}` : "金额未填写"}</p><p className="mt-1 text-xs text-slate-500">成交概率：{opportunity.probability}% · 创建于 {new Date(opportunity.created_at).toLocaleDateString()}</p></Link>)}{!opportunities.length && <p className="text-sm text-slate-500">该客户暂无商机。</p>}</div></>}
          {activeTab === "quotations" && <><div className="flex items-center justify-between"><h3 className="font-bold">报价</h3><Link to="/quotations" className="text-sm text-blue-700">查看全部报价</Link></div><div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{quotations.map((quotation) => <article key={quotation.id} className="rounded-lg bg-slate-50 p-3"><div className="flex items-start justify-between gap-2"><Link to={`/quotations/${quotation.id}`} className="font-semibold text-blue-700">{quotation.quotation_number}</Link><span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs">{quotationStatusText[quotation.status]}</span></div><p className="mt-2 text-sm">{quotation.currency} {Number(quotation.total_amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>{quotation.opportunity_id && <Link to={`/opportunities/${quotation.opportunity_id}`} className="mt-2 inline-block text-sm text-blue-700">{quotation.opportunity_name ?? "关联商机"}</Link>}<p className="mt-2 text-xs text-slate-500">日期：{new Date(quotation.created_at).toLocaleDateString()}</p></article>)}{!quotations.length && <p className="text-sm text-slate-500">暂无报价；可点击页面顶部“创建报价”。</p>}</div></>}
          {activeTab === "orders" && <><div className="flex items-center justify-between gap-3"><div><h3 className="font-bold">订单</h3><p className="mt-1 text-sm text-slate-500">订单、履约状态和订单利润统一在订单管理中维护。</p></div><Link to={`/orders?customer_id=${customer.id}`} className="text-sm text-blue-700">查看全部 →</Link></div><div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{orders.map((order) => <Link key={order.id} to={`/orders/${order.id}`} className="rounded-lg bg-slate-50 p-3 hover:bg-blue-50"><div className="flex items-center justify-between gap-2"><strong>{order.order_no}</strong><span className="text-sm text-slate-600">{order.currency} {order.order_amount}</span></div><p className="mt-2 text-sm text-slate-600">{order.order_date} · {order.payment_status}</p><p className="mt-1 text-sm">{order.profit_accounting_status === "Pending" ? "利润：待核算" : `利润：¥${order.profit}`}</p></Link>)}{!orders.length && <p className="text-sm text-slate-500">该客户暂无订单。</p>}</div></>}
          {activeTab === "contacts" && <><h3 className="font-bold">联系人</h3><div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{customer.contacts.length ? customer.contacts.map((contact) => <div key={contact.id} className="rounded-lg bg-slate-50 p-3 text-sm"><p className="font-semibold">{contact.name}</p><p className="text-slate-500">{contact.position ?? "未填写职位"}</p><p className="mt-1 text-slate-600">{contact.email ?? "未填写邮箱"}</p><p className="text-slate-600">{contact.phone ?? contact.whatsapp ?? "未填写电话"}</p></div>) : <p className="text-sm text-slate-500">暂无其他联系人。</p>}</div></>}
          {activeTab === "attachments" && <><div className="flex items-center justify-between gap-3"><div><h3 className="font-bold">客户附件</h3><p className="mt-1 text-sm text-slate-500">来自跟进记录的文件。</p></div><span className="text-sm text-slate-500">共 {attachments.length} 个</span></div><div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{attachments.map(({ attachment, followup }) => <article key={attachment.id} className="rounded-lg bg-slate-50 p-3 text-sm"><button type="button" onClick={() => void openFollowupFile(followup.id, attachment.id)} className="font-medium text-blue-700">{attachment.file_name}</button><p className="mt-1 text-slate-500">{followup.type} · {followup.followup_date}</p><p className="text-xs text-slate-500">{Math.ceil(attachment.size_bytes / 1024)} KB · {new Date(attachment.created_at).toLocaleString()}</p></article>)}{!attachments.length && <p className="text-sm text-slate-500">暂无客户附件。</p>}</div></>}
          {activeTab === "emails" && <><div className="flex items-center justify-between"><div><h3 className="font-bold">邮件</h3><p className="mt-1 text-sm text-slate-500">已自动匹配到该客户的邮件往来。</p></div><div className="flex gap-3 text-sm text-blue-700"><Link to={`/mail?customer_id=${customer.id}&compose=1`}>写邮件</Link><Link to={`/mail?customer_id=${customer.id}`}>邮件中心 →</Link></div></div><div className="mt-4 space-y-2">{emails.map((message) => <Link key={message.id} to={`/mail?customer_id=${customer.id}&message_id=${message.id}`} className="block rounded-lg bg-slate-50 p-3 hover:bg-blue-50"><div className="flex flex-wrap justify-between gap-2"><strong>{message.subject || "(无主题)"}</strong><span className="text-xs text-slate-500">{mailDateTime(message.sent_at)}</span></div><p className="mt-1 text-sm text-slate-600">{message.direction === "incoming" ? `收到 · 发件人：${message.from_email}` : `发出 · 收件人：${message.to_emails.join(", ")}`}</p>{message.direction === "outgoing" && <p className={`mt-1 text-xs ${message.open_count > 0 ? "text-emerald-700" : "text-slate-500"}`}>{message.tracking_enabled ? (message.open_count > 0 ? `已打开 ${message.open_count} 次 · 最近打开：${mailDateTime(message.last_opened_at)}` : "未打开") : "未启用打开追踪"}</p>}<p className="mt-1 truncate text-sm text-slate-500">{message.body_text || "无正文"}</p></Link>)}{!emails.length && <p className="text-sm text-slate-500">该客户暂无已关联邮件。</p>}</div></>}
        </div>
      </section>
    </>
  );
}
