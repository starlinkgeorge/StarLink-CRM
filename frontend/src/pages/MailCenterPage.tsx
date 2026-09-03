import axios from "axios";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { downloadMailAttachment, getCustomers, getMailFolderCounts, getMailMessage, getMailMessages, markMailRead, markMailUnread, sendMail, syncMail } from "../services/crm";
import { useAuth } from "../store/auth";
import type { Customer, MailFolderCounts, MailMessage } from "../types";

type Folder = "inbox" | "sent" | "unread";
type ComposeMode = "new" | "reply" | "forward";

const dateLabel = (value: string | null) => value ? new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Shanghai" }).format(new Date(value)) : "—";
const trackingLabel = (message: MailMessage) => !message.tracking_enabled ? "未启用打开追踪" : message.open_count > 0 ? `已打开 ${message.open_count} 次` : "未打开";
const senderLabel = (message: MailMessage) => message.direction === "incoming" ? (message.from_name ? `${message.from_name} <${message.from_email}>` : message.from_email) : (message.to_display[0] ?? message.to_emails[0] ?? "—");

export function MailCenterPage() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const composeFromUrlHandled = useRef(false);
  const [folder, setFolder] = useState<Folder>(searchParams.get("folder") === "sent" ? "sent" : "inbox");
  const [messages, setMessages] = useState<MailMessage[]>([]);
  const [selected, setSelected] = useState<MailMessage | null>(null);
  const [counts, setCounts] = useState<MailFolderCounts>({ inbox: 0, sent: 0, unread: 0 });
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [query, setQuery] = useState("");
  const [customerId, setCustomerId] = useState(searchParams.get("customer_id") ?? "");
  const [composeOpen, setComposeOpen] = useState(false);
  const [composeMode, setComposeMode] = useState<ComposeMode>("new");
  const [toEmails, setToEmails] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [replyTo, setReplyTo] = useState<number | undefined>();
  const [forwardOf, setForwardOf] = useState<number | undefined>();
  const [includeForwardAttachments, setIncludeForwardAttachments] = useState(true);
  const [trackingEnabled, setTrackingEnabled] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [page, nextCounts] = await Promise.all([
        getMailMessages({ folder, query: query || undefined, customer_id: customerId ? Number(customerId) : undefined, limit: 100 }),
        getMailFolderCounts(),
      ]);
      setMessages(page.items); setCounts(nextCounts);
    } catch { setError("无法加载邮件中心。"); }
  }, [customerId, folder, query]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { void getCustomers({ limit: 100, offset: 0 }).then((page) => setCustomers(page.items)).catch(() => undefined); }, []);
  useEffect(() => { const id = Number(searchParams.get("message_id")); if (id > 0) void openMessage(id); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (composeFromUrlHandled.current || searchParams.get("compose") !== "1" || !customers.length) return;
    const customer = customers.find((item) => String(item.id) === customerId);
    composeFromUrlHandled.current = true;
    setComposeMode("new");
    setToEmails(customer?.email ?? "");
    setSubject("");
    setBody("");
    setFiles([]);
    setReplyTo(undefined);
    setForwardOf(undefined);
    setTrackingEnabled(true);
    setComposeOpen(true);
  }, [customerId, customers, searchParams]);

  async function openMessage(messageId: number) {
    try {
      let message = await getMailMessage(messageId);
      if (message.direction === "incoming" && !message.is_read) message = await markMailRead(message.id);
      setSelected(message); setError(""); await load();
    } catch { setError("无法加载邮件详情。"); }
  }

  function beginCompose(mode: ComposeMode, message?: MailMessage) {
    const recipient = message ? (message.direction === "incoming" ? message.from_email : message.to_emails[0]) : "";
    const original = message ? `\n\n---------- 原始邮件 ----------\n发件人：${senderLabel(message)}\n收件人：${message.to_display.join(", ") || message.to_emails.join(", ")}\n时间：${dateLabel(message.sent_at)}\n主题：${message.subject}\n\n${message.body_text}` : "";
    setComposeMode(mode); setToEmails(mode === "reply" ? recipient || "" : "");
    setSubject(message ? (mode === "forward" ? (message.subject.startsWith("Fwd:") ? message.subject : `Fwd: ${message.subject}`) : (message.subject.startsWith("Re:") ? message.subject : `Re: ${message.subject}`)) : "");
    setBody(mode === "forward" ? original : ""); setFiles([]); setReplyTo(mode === "reply" ? message?.id : undefined); setForwardOf(mode === "forward" ? message?.id : undefined); setIncludeForwardAttachments(true); setTrackingEnabled(true); setComposeOpen(true);
  }

  async function synchronize() {
    setSyncing(true); setError("");
    try { const result = await syncMail(); await load(); window.alert(`已同步 ${result.imported} 封邮件，跳过 ${result.skipped} 封。`); }
    catch (err) { setError(axios.isAxiosError(err) ? err.response?.data?.detail ?? "同步失败。" : "同步失败。"); }
    finally { setSyncing(false); }
  }

  async function submit(event: FormEvent) {
    event.preventDefault(); setSending(true); setError("");
    try {
      const forwardedFiles = composeMode === "forward" && forwardOf && includeForwardAttachments && selected
        ? await Promise.all(selected.attachments.map(async (attachment) => new File([await downloadMailAttachment(selected.id, attachment.id)], attachment.file_name, { type: attachment.content_type ?? "application/octet-stream" }))) : [];
      const sent = await sendMail({ to_emails: toEmails, subject, body, customer_id: customerId ? Number(customerId) : undefined, reply_to_id: replyTo, forward_of_id: forwardOf, tracking_enabled: trackingEnabled, files: [...files, ...forwardedFiles] });
      setFolder("sent"); setComposeOpen(false); setSelected(sent); await load();
    } catch (err) { setError(axios.isAxiosError(err) ? err.response?.data?.detail ?? "发送失败。" : "发送失败。"); }
    finally { setSending(false); }
  }

  async function toggleReadState() {
    if (!selected) return;
    try { setSelected(selected.is_read ? await markMailUnread(selected.id) : await markMailRead(selected.id)); await load(); }
    catch { setError("无法更新已读状态。"); }
  }

  async function download(messageId: number, attachmentId: number) {
    try { const blob = await downloadMailAttachment(messageId, attachmentId); const url = URL.createObjectURL(blob); window.open(url, "_blank", "noopener,noreferrer"); window.setTimeout(() => URL.revokeObjectURL(url), 60_000); }
    catch { setError("无法下载附件。"); }
  }

  const folders: Array<{ id: Folder; label: string; count: number }> = [
    { id: "inbox", label: "收件箱", count: counts.inbox }, { id: "sent", label: "已发送", count: counts.sent }, { id: "unread", label: "未读", count: counts.unread },
  ];

  return <>
    <header className="mb-4 flex flex-wrap items-start justify-between gap-3"><div><p className="text-sm text-slate-500">Foxmail / QQ 邮箱</p><h2 className="text-3xl font-bold text-slate-950">邮件中心</h2></div>{user?.role === "Admin" && <button type="button" onClick={() => void synchronize()} disabled={syncing} className="rounded border border-blue-600 px-4 py-2 text-sm font-semibold text-blue-700 disabled:opacity-50">{syncing ? "同步中…" : "手动同步"}</button>}</header>
    {error && <p className="mb-3 text-sm text-rose-600">{error}</p>}
    <section className="grid min-h-[calc(100vh-12rem)] overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200 lg:grid-cols-[13rem_minmax(19rem,0.9fr)_minmax(24rem,1.3fr)]">
      <aside className="border-b border-slate-200 bg-slate-50 p-3 lg:border-b-0 lg:border-r"><button type="button" onClick={() => beginCompose("new")} disabled={user?.role === "Viewer"} className="w-full rounded bg-blue-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">写邮件</button><nav className="mt-4 space-y-1">{folders.map((item) => <button key={item.id} type="button" onClick={() => { setFolder(item.id); setSelected(null); }} className={`flex w-full items-center justify-between rounded px-3 py-2 text-sm ${folder === item.id ? "bg-blue-100 font-semibold text-blue-800" : "text-slate-700 hover:bg-slate-200"}`}><span>{item.label}</span><span className="rounded-full bg-white px-2 py-0.5 text-xs text-slate-500">{item.count}</span></button>)}</nav></aside>
      <section className="flex min-h-0 flex-col border-b border-slate-200 lg:border-b-0 lg:border-r"><div className="space-y-2 border-b border-slate-200 p-3"><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索主题、邮箱或正文" className="w-full rounded border border-slate-300 px-3 py-2 text-sm" /><select value={customerId} onChange={(event) => setCustomerId(event.target.value)} className="w-full rounded border border-slate-300 px-3 py-2 text-sm"><option value="">全部客户</option>{customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.company_name}</option>)}</select></div><div className="min-h-0 flex-1 overflow-y-auto">{messages.map((message) => <button key={message.id} type="button" onClick={() => void openMessage(message.id)} className={`block w-full border-b border-slate-100 px-4 py-3 text-left hover:bg-blue-50 ${selected?.id === message.id ? "bg-blue-50" : ""} ${message.direction === "incoming" && !message.is_read ? "border-l-4 border-l-blue-600 bg-blue-50/50" : ""}`}><div className="flex justify-between gap-2 text-sm"><strong className="truncate">{senderLabel(message)}</strong><span className="shrink-0 text-xs text-slate-500">{dateLabel(message.sent_at)}</span></div><p className={`mt-1 truncate text-sm ${message.direction === "incoming" && !message.is_read ? "font-semibold text-slate-950" : "text-slate-800"}`}>{message.subject || "(无主题)"}</p><p className="mt-1 truncate text-xs text-slate-500">{message.body_text || "无正文"}</p><div className="mt-1 flex flex-wrap gap-2 text-xs">{message.direction === "incoming" && !message.is_read && <span className="font-medium text-blue-700">未读</span>}{message.has_attachments && <span className="text-slate-500">有附件</span>}{message.customer_id && <span className="text-slate-500">已关联客户</span>}{message.direction === "outgoing" && <span className={message.open_count > 0 ? "text-emerald-700" : "text-slate-500"}>{trackingLabel(message)}</span>}</div></button>)}{!messages.length && <p className="p-8 text-center text-sm text-slate-500">暂无邮件。</p>}</div></section>
      <section className="min-h-0 overflow-y-auto p-5">{selected ? <><div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 pb-4"><div><h3 className="text-xl font-bold text-slate-950">{selected.subject || "(无主题)"}</h3><p className="mt-3 text-sm text-slate-600">发件人：{selected.from_name ? `${selected.from_name} <${selected.from_email}>` : selected.from_email}</p><p className="text-sm text-slate-600">收件人：{selected.to_display.join(", ") || selected.to_emails.join(", ") || "—"}</p>{selected.cc_display.length > 0 && <p className="text-sm text-slate-600">抄送：{selected.cc_display.join(", ")}</p>}<p className="text-xs text-slate-500">{dateLabel(selected.sent_at)}</p>{selected.customer_id && <Link to={`/customers/${selected.customer_id}`} className="mt-2 inline-block text-sm text-blue-700">查看关联客户 →</Link>}</div><div className="flex flex-wrap gap-2">{selected.direction === "incoming" && <button type="button" onClick={() => void toggleReadState()} className="rounded border px-3 py-1.5 text-sm">{selected.is_read ? "标记未读" : "标记已读"}</button>}{user?.role !== "Viewer" && <><button type="button" onClick={() => beginCompose("reply", selected)} className="rounded border border-blue-600 px-3 py-1.5 text-sm font-medium text-blue-700">回复</button><button type="button" onClick={() => beginCompose("forward", selected)} className="rounded border border-blue-600 px-3 py-1.5 text-sm font-medium text-blue-700">转发</button></>}</div></div>{selected.direction === "outgoing" && <section className="mt-4 rounded-lg bg-slate-50 p-3 text-sm"><strong className={selected.open_count > 0 ? "text-emerald-700" : "text-slate-700"}>{trackingLabel(selected)}</strong>{selected.tracking_enabled && <><p className="mt-1 text-slate-600">首次打开：{dateLabel(selected.first_opened_at)}</p><p className="text-slate-600">最近打开：{dateLabel(selected.last_opened_at)}</p></>}<p className="mt-2 text-xs text-slate-500">邮件打开追踪可能受邮件客户端图片加载和隐私保护影响，仅供参考。</p></section>}<p className="mt-5 whitespace-pre-wrap text-sm leading-6 text-slate-800">{selected.body_text || "无正文"}</p>{selected.attachments.length > 0 && <div className="mt-6 border-t pt-4"><h4 className="font-semibold">附件</h4><div className="mt-2 flex flex-wrap gap-2">{selected.attachments.map((attachment) => <button key={attachment.id} type="button" onClick={() => void download(selected.id, attachment.id)} className="rounded border px-2 py-1 text-sm text-blue-700">{attachment.file_name} ({Math.ceil(attachment.size_bytes / 1024)} KB)</button>)}</div></div>}</> : <p className="pt-20 text-center text-sm text-slate-500">从中间列表选择一封邮件查看详情。</p>}</section>
    </section>
    {composeOpen && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4"><form onSubmit={submit} className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white p-5 shadow-xl"><div className="flex justify-between gap-3"><h3 className="text-xl font-bold">{composeMode === "forward" ? "转发邮件" : composeMode === "reply" ? "回复邮件" : "发送邮件"}</h3><button type="button" onClick={() => setComposeOpen(false)} className="text-slate-500">关闭</button></div><label className="mt-4 block text-sm font-medium">收件人（多个邮箱用逗号分隔）<input required value={toEmails} onChange={(event) => setToEmails(event.target.value)} className="mt-1 w-full rounded border px-3 py-2" /></label><label className="mt-3 block text-sm font-medium">主题<input required maxLength={500} value={subject} onChange={(event) => setSubject(event.target.value)} className="mt-1 w-full rounded border px-3 py-2" /></label><label className="mt-3 block text-sm font-medium">正文<textarea value={body} onChange={(event) => setBody(event.target.value)} className="mt-1 min-h-48 w-full rounded border px-3 py-2" /></label>{composeMode === "forward" && selected?.attachments.length ? <label className="mt-3 flex items-center gap-2 text-sm"><input type="checkbox" checked={includeForwardAttachments} onChange={(event) => setIncludeForwardAttachments(event.target.checked)} />附带原邮件附件（{selected.attachments.length} 个）</label> : null}<label className="mt-3 flex items-center gap-2 text-sm font-medium"><input type="checkbox" checked={trackingEnabled} onChange={(event) => setTrackingEnabled(event.target.checked)} />追踪邮件打开</label><p className="mt-1 text-xs text-slate-500">邮件打开追踪可能受邮件客户端图片加载和隐私保护影响，仅供参考。</p><label className="mt-3 block text-sm font-medium">附件（单个最大 10 MB）<input type="file" multiple onChange={(event) => setFiles(Array.from(event.target.files ?? []))} className="mt-1 block text-sm" />{files.length > 0 && <span className="text-xs text-slate-500">{files.map((file) => file.name).join("、")}</span>}</label><div className="mt-5 flex justify-end gap-2"><button type="button" onClick={() => setComposeOpen(false)} className="rounded border px-4 py-2">取消</button><button disabled={sending} className="rounded bg-blue-700 px-4 py-2 font-semibold text-white disabled:opacity-50">{sending ? "发送中…" : "发送"}</button></div></form></div>}
  </>;
}
