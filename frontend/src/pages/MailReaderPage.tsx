import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { MailRichTextEditor } from "../components/MailRichTextEditor";
import { getMailMessage, getSystemSettings, sendMail } from "../services/crm";
import type { MailMessage } from "../types";

const plainToHtml = (value: string) => value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\n/g, "<br>");
const date = (value: string | null) => value ? new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Shanghai" }).format(new Date(value)) : "—";

/** A full-width reader opened from Mail Center. It remains a real CRM route, so replying uses the normal authenticated send API. */
export function MailReaderPage() {
  const { messageId } = useParams();
  const [message, setMessage] = useState<MailMessage>();
  const [replying, setReplying] = useState(false);
  const [to, setTo] = useState(""); const [subject, setSubject] = useState("");
  const [html, setHtml] = useState(""); const [plain, setPlain] = useState("");
  const [sending, setSending] = useState(false); const [error, setError] = useState(""); const [notice, setNotice] = useState("");

  useEffect(() => {
    const id = Number(messageId);
    if (!Number.isInteger(id) || id <= 0) { setError("邮件地址无效。"); return; }
    void getMailMessage(id).then(setMessage).catch(() => setError("无法加载邮件，可能已删除或没有权限查看。"));
  }, [messageId]);

  const startReply = async () => {
    if (!message) return;
    try {
      const signature = (await getSystemSettings()).email_signature.html;
      setTo(message.direction === "incoming" ? message.from_email : (message.to_emails[0] || ""));
      setSubject(message.subject.startsWith("Re:") ? message.subject : `Re: ${message.subject}`);
      setHtml(`<br><br><hr><p><b>原始邮件</b></p>${message.html_body || plainToHtml(message.body_text)}${signature}`);
      setPlain(""); setReplying(true); setError("");
    } catch { setError("无法初始化回复编辑器。"); }
  };
  const sendReply = async (event: FormEvent) => {
    event.preventDefault();
    if (!message) return;
    setSending(true); setError("");
    try {
      await sendMail({ to_emails: to, subject, body: plain, html_body: html, reply_to_id: message.id, tracking_enabled: true });
      setReplying(false); setNotice("回复已发送。");
    } catch (caught) { setError((caught as { response?: { data?: { detail?: string } } }).response?.data?.detail || "回复发送失败。"); }
    finally { setSending(false); }
  };

  return <div className="mx-auto max-w-6xl py-2">
    <div className="mb-5 flex items-center justify-between"><Link to="/mail" className="text-sm text-blue-700">← 返回邮件中心</Link><button type="button" onClick={() => window.close()} className="text-sm text-slate-500">关闭窗口</button></div>
    {error && <p className="mb-3 rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}{notice && <p className="mb-3 rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{notice}</p>}
    {message && <section className="rounded-xl border bg-white p-6 shadow-sm"><header className="border-b pb-5"><div className="flex flex-wrap items-start justify-between gap-4"><div className="min-w-0"><h1 className="break-words text-2xl font-bold">{message.subject || "(无主题)"}</h1><p className="mt-4 break-words text-sm text-slate-700">发件人：{message.from_name || message.from_email} &lt;{message.from_email}&gt;</p><p className="break-words text-sm text-slate-700">收件人：{message.to_display.join(", ") || message.to_emails.join(", ")}</p>{message.cc_emails.length > 0 && <p className="break-words text-sm text-slate-700">抄送：{message.cc_emails.join(", ")}</p>}<p className="mt-2 text-xs text-slate-500">{date(message.sent_at)}</p></div><button type="button" onClick={() => void startReply()} className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white">回复</button></div></header><article className="mail-reader-body mt-6 break-words text-[15px] leading-8" dangerouslySetInnerHTML={{ __html: message.html_body || plainToHtml(message.body_text) }} />{message.attachments.length > 0 && <div className="mt-7 border-t pt-4"><p className="mb-2 text-sm font-medium">附件</p>{message.attachments.map((attachment) => <span key={attachment.id} className="mr-2 inline-block rounded border px-3 py-1.5 text-sm">📎 {attachment.file_name}</span>)}</div>}</section>}
    {replying && <form onSubmit={(event) => void sendReply(event)} className="mt-5 rounded-xl border bg-white shadow-sm"><div className="space-y-1 border-b px-5 py-3"><input required value={to} onChange={(event) => setTo(event.target.value)} placeholder="收件人" className="w-full border-b px-1 py-2 text-sm outline-none" /><input required value={subject} onChange={(event) => setSubject(event.target.value)} placeholder="主题" className="w-full border-b px-1 py-2 text-sm outline-none" /></div><div className="p-5"><MailRichTextEditor value={html} onChange={(nextHtml, nextText) => { setHtml(nextHtml); setPlain(nextText); }} /></div><footer className="flex justify-end gap-3 border-t px-5 py-3"><button type="button" onClick={() => setReplying(false)} className="px-4 py-2 text-sm text-slate-600">取消</button><button disabled={sending} type="submit" className="rounded-lg bg-blue-700 px-5 py-2 text-sm font-medium text-white disabled:opacity-50">{sending ? "发送中…" : "发送回复"}</button></footer></form>}
  </div>;
}
