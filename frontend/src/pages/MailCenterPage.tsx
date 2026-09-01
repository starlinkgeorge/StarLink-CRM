import axios from "axios";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { downloadMailAttachment, getMailMessage, getMailMessages, sendMail, syncMail } from "../services/crm";
import { useAuth } from "../store/auth";
import type { MailMessage } from "../types";

type Folder = "inbox" | "sent";

function dateLabel(value: string | null) {
  return value ? new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Shanghai" }).format(new Date(value)) : "—";
}

export function MailCenterPage() {
  const { user } = useAuth();
  const [folder, setFolder] = useState<Folder>("inbox");
  const [messages, setMessages] = useState<MailMessage[]>([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState<MailMessage | null>(null);
  const [query, setQuery] = useState("");
  const [composeOpen, setComposeOpen] = useState(false);
  const [toEmails, setToEmails] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [replyTo, setReplyTo] = useState<number | undefined>();
  const [syncing, setSyncing] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const page = await getMailMessages({ folder, query: query || undefined, limit: 100 });
      setMessages(page.items); setTotal(page.total);
      if (selected && !page.items.some((item) => item.id === selected.id)) setSelected(null);
    } catch { setError("无法加载邮件列表。"); }
  }, [folder, query, selected]);

  useEffect(() => { void load(); }, [load]);

  async function openMessage(message: MailMessage) {
    try { setSelected(await getMailMessage(message.id)); setError(""); } catch { setError("无法加载邮件详情。"); }
  }
  function beginCompose(message?: MailMessage) {
    const recipient = message ? (message.direction === "incoming" ? message.from_email : message.to_emails[0]) : "";
    setToEmails(recipient || ""); setSubject(message ? (message.subject.startsWith("Re:") ? message.subject : `Re: ${message.subject}`) : ""); setBody(""); setFiles([]); setReplyTo(message?.id); setComposeOpen(true);
  }
  async function synchronize() {
    setSyncing(true); setError("");
    try { const result = await syncMail(); await load(); window.alert(`已同步 ${result.imported} 封邮件，跳过重复邮件 ${result.skipped} 封。`); }
    catch (err) { setError(axios.isAxiosError(err) ? err.response?.data?.detail ?? "同步失败。" : "同步失败。"); }
    finally { setSyncing(false); }
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); setSending(true); setError("");
    try { const sent = await sendMail({ to_emails: toEmails, subject, body, reply_to_id: replyTo, files }); setFolder("sent"); setComposeOpen(false); setSelected(sent); await load(); }
    catch (err) { setError(axios.isAxiosError(err) ? err.response?.data?.detail ?? "发送失败。" : "发送失败。"); }
    finally { setSending(false); }
  }
  async function download(messageId: number, attachmentId: number) {
    try { const blob = await downloadMailAttachment(messageId, attachmentId); const url = URL.createObjectURL(blob); window.open(url, "_blank", "noopener,noreferrer"); window.setTimeout(() => URL.revokeObjectURL(url), 60_000); }
    catch { setError("无法下载附件。"); }
  }

  return <>
    <header className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-sm text-slate-500">Foxmail / QQ 邮箱</p><h2 className="text-3xl font-bold text-slate-950">邮件中心</h2></div><div className="flex gap-2"><button type="button" onClick={() => beginCompose()} disabled={user?.role === "Viewer"} className="rounded bg-blue-700 px-4 py-2 font-semibold text-white disabled:opacity-50">发送邮件</button>{user?.role === "Admin" && <button type="button" onClick={() => void synchronize()} disabled={syncing} className="rounded border border-blue-600 px-4 py-2 font-semibold text-blue-700 disabled:opacity-50">{syncing ? "同步中…" : "手动同步"}</button>}</div></header>
    {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
    <section className="mt-5 grid gap-4 lg:grid-cols-[minmax(300px,0.9fr)_minmax(0,1.5fr)]"><div className="overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200"><div className="flex border-b border-slate-200"><button type="button" onClick={() => setFolder("inbox")} className={`flex-1 px-3 py-3 text-sm font-semibold ${folder === "inbox" ? "border-b-2 border-blue-600 text-blue-700" : "text-slate-500"}`}>收件箱</button><button type="button" onClick={() => setFolder("sent")} className={`flex-1 px-3 py-3 text-sm font-semibold ${folder === "sent" ? "border-b-2 border-blue-600 text-blue-700" : "text-slate-500"}`}>已发送</button></div><div className="p-3"><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索主题、邮箱或正文" className="w-full rounded border border-slate-300 px-3 py-2 text-sm" /></div><p className="px-3 pb-2 text-xs text-slate-500">共 {total} 封</p><div className="max-h-[62vh] overflow-y-auto border-t border-slate-100">{messages.map((message) => <button key={message.id} type="button" onClick={() => void openMessage(message)} className={`block w-full border-b border-slate-100 px-4 py-3 text-left hover:bg-blue-50 ${selected?.id === message.id ? "bg-blue-50" : ""}`}><div className="flex justify-between gap-2 text-sm"><strong className="truncate">{folder === "inbox" ? message.from_email : message.to_emails.join(", ")}</strong><span className="shrink-0 text-xs text-slate-500">{dateLabel(message.sent_at)}</span></div><p className="mt-1 truncate text-sm text-slate-800">{message.subject || "(无主题)"}</p><p className="mt-1 truncate text-xs text-slate-500">{message.body_text || "无正文"}</p></button>)}{!messages.length && <p className="p-5 text-center text-sm text-slate-500">暂无邮件。管理员可点击“手动同步”。</p>}</div></div>
      <div className="min-h-96 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">{selected ? <><div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 pb-4"><div><h3 className="text-xl font-bold">{selected.subject || "(无主题)"}</h3><p className="mt-2 text-sm text-slate-600">发件人：{selected.from_email}</p><p className="text-sm text-slate-600">收件人：{selected.to_emails.join(", ") || "—"}</p><p className="text-xs text-slate-500">{dateLabel(selected.sent_at)}</p>{selected.customer_id && <Link to={`/customers/${selected.customer_id}`} className="mt-2 inline-block text-sm text-blue-700">查看关联客户 →</Link>}</div>{user?.role !== "Viewer" && <button type="button" onClick={() => beginCompose(selected)} className="rounded border border-blue-600 px-3 py-1.5 text-sm font-medium text-blue-700">回复</button>}</div><p className="mt-5 whitespace-pre-wrap text-sm leading-6 text-slate-800">{selected.body_text || "无正文"}</p>{selected.attachments.length > 0 && <div className="mt-6 border-t pt-4"><h4 className="font-semibold">附件</h4><div className="mt-2 flex flex-wrap gap-2">{selected.attachments.map((attachment) => <button key={attachment.id} type="button" onClick={() => void download(selected.id, attachment.id)} className="rounded border px-2 py-1 text-sm text-blue-700">{attachment.file_name} ({Math.ceil(attachment.size_bytes / 1024)} KB)</button>)}</div></div>}</> : <p className="pt-24 text-center text-sm text-slate-500">从左侧选择一封邮件查看详情。</p>}</div></section>
    {composeOpen && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4"><form onSubmit={submit} className="w-full max-w-2xl rounded-xl bg-white p-5 shadow-xl"><div className="flex justify-between gap-3"><h3 className="text-xl font-bold">{replyTo ? "回复邮件" : "发送邮件"}</h3><button type="button" onClick={() => setComposeOpen(false)} className="text-slate-500">关闭</button></div><label className="mt-4 block text-sm font-medium">收件人（多个邮箱用逗号分隔）<input required type="text" value={toEmails} onChange={(event) => setToEmails(event.target.value)} className="mt-1 w-full rounded border px-3 py-2" /></label><label className="mt-3 block text-sm font-medium">主题<input required maxLength={500} value={subject} onChange={(event) => setSubject(event.target.value)} className="mt-1 w-full rounded border px-3 py-2" /></label><label className="mt-3 block text-sm font-medium">正文<textarea value={body} onChange={(event) => setBody(event.target.value)} className="mt-1 min-h-48 w-full rounded border px-3 py-2" /></label><label className="mt-3 block text-sm font-medium">附件（单个最大 10 MB）<input type="file" multiple onChange={(event) => setFiles(Array.from(event.target.files ?? []))} className="mt-1 block text-sm" />{files.length > 0 && <span className="text-xs text-slate-500">{files.map((file) => file.name).join("、")}</span>}</label><div className="mt-5 flex justify-end gap-2"><button type="button" onClick={() => setComposeOpen(false)} className="rounded border px-4 py-2">取消</button><button disabled={sending} className="rounded bg-blue-700 px-4 py-2 font-semibold text-white disabled:opacity-50">{sending ? "发送中…" : "发送"}</button></div></form></div>}
  </>;
}
