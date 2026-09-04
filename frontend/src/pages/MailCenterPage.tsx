import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { MailRichTextEditor } from "../components/MailRichTextEditor";
import {
  bulkUpdateMail, createMailFolder, deleteMailFolder, downloadMailAttachment,
  getCustomers, getMailFolderCounts, getMailFolders, getMailMessage,
  getMailMessages, getSystemSettings, saveMailDraft, sendMail,
  sendMailIndividually, syncMail,
} from "../services/crm";
import { useAuth } from "../store/auth";
import type { Customer, MailFolder, MailFolderCounts, MailMessage } from "../types";

type Folder = "inbox" | "sent" | "unread" | "drafts" | "starred";

const addresses = (value: string) => [...new Set(value.split(/[,;\r\n]+/)
  .map((entry) => entry.trim().toLowerCase())
  .filter((entry) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(entry)))];
const display = (message: MailMessage) => message.direction === "incoming"
  ? (message.from_name || message.from_email)
  : (message.to_display[0] || message.to_emails[0] || "—");
const date = (value: string | null) => value
  ? new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Shanghai" }).format(new Date(value))
  : "—";

function TrackingStatus({ message, detailed = false }: { message: MailMessage; detailed?: boolean }) {
  if (message.direction !== "outgoing") return null;
  if (!message.tracking_enabled) return <p className="mt-1 text-xs text-slate-500">未启用打开追踪</p>;
  if (!message.open_count) return <p className="mt-1 text-xs font-medium text-slate-500">未打开</p>;
  if (!detailed) return <p className="mt-1 text-xs font-medium text-emerald-700">已打开 · {message.open_count} 次</p>;
  return <div className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-950">
    <p className="font-semibold">已打开 {message.open_count} 次</p>
    <p>首次打开：{date(message.first_opened_at)}</p>
    <p>最近打开：{date(message.last_opened_at)}</p>
    <p className="mt-1 text-emerald-800">邮件打开追踪可能受邮件客户端图片加载和隐私保护影响，仅供参考。</p>
  </div>;
}

export function MailCenterPage() {
  const { user } = useAuth();
  const [folder, setFolder] = useState<Folder>("inbox");
  const [mailFolderId, setMailFolderId] = useState<number>();
  const [folders, setFolders] = useState<MailFolder[]>([]);
  const [items, setItems] = useState<MailMessage[]>([]);
  const [selected, setSelected] = useState<MailMessage | null>(null);
  const [counts, setCounts] = useState<MailFolderCounts>({ inbox: 0, sent: 0, unread: 0, drafts: 0, starred: 0 });
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [query, setQuery] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [compose, setCompose] = useState(false);
  const [moreRecipients, setMoreRecipients] = useState(false);
  const [to, setTo] = useState(""); const [cc, setCc] = useState(""); const [bcc, setBcc] = useState("");
  const [subject, setSubject] = useState(""); const [html, setHtml] = useState(""); const [plain, setPlain] = useState("");
  const [files, setFiles] = useState<File[]>([]); const [tracking, setTracking] = useState(true);
  const [sending, setSending] = useState(false); const [syncing, setSyncing] = useState(false);
  const [replyTo, setReplyTo] = useState<number>(); const [forwardOf, setForwardOf] = useState<number>(); const [draftId, setDraftId] = useState<number>();
  const [failedRecipients, setFailedRecipients] = useState<string[]>([]); const [notice, setNotice] = useState(""); const [error, setError] = useState("");

  const load = useCallback(async () => {
    const [page, nextCounts, nextFolders] = await Promise.all([
      getMailMessages({ folder: mailFolderId ? "all" : folder, mail_folder_id: mailFolderId, query: query || undefined, customer_id: customerId ? Number(customerId) : undefined, limit: 100 }),
      getMailFolderCounts(), getMailFolders(),
    ]);
    setItems(page.items); setCounts(nextCounts); setFolders(nextFolders);
  }, [folder, mailFolderId, query, customerId]);
  useEffect(() => { void load().catch(() => setError("无法加载邮件中心。")); }, [load]);
  useEffect(() => { void getCustomers({ limit: 100, offset: 0 }).then((page) => setCustomers(page.items)); }, []);

  const clearCompose = () => { setTo(""); setCc(""); setBcc(""); setSubject(""); setHtml(""); setPlain(""); setFiles([]); setTracking(true); setReplyTo(undefined); setForwardOf(undefined); setDraftId(undefined); setFailedRecipients([]); setMoreRecipients(false); };
  const openCompose = async (kind: "new" | "reply" | "all" | "forward") => {
    clearCompose(); const signature = (await getSystemSettings()).email_signature.html;
    if (!selected || kind === "new") { setHtml(signature); setCompose(true); return; }
    const own = user?.email.toLowerCase();
    const people = [selected.direction === "incoming" ? selected.from_email : selected.to_emails[0], ...selected.to_emails, ...selected.cc_emails].filter((entry, index, all) => entry && entry.toLowerCase() !== own && all.indexOf(entry) === index);
    if (kind !== "forward") setTo(people[0] || "");
    if (kind === "all") { setCc(people.slice(1).join(", ")); setMoreRecipients(true); }
    setSubject(`${kind === "forward" ? "Fwd:" : "Re:"} ${selected.subject}`);
    setHtml(`<br><br><hr><p><b>原始邮件</b></p>${selected.html_body || selected.body_text.replace(/\n/g, "<br>")}${signature}`);
    setReplyTo(kind === "forward" ? undefined : selected.id); setForwardOf(kind === "forward" ? selected.id : undefined); setCompose(true);
  };
  const open = async (message: MailMessage) => { const detail = await getMailMessage(message.id); setSelected(detail); if (!detail.is_read) await bulkUpdateMail([detail.id], { is_read: true }); await load(); };
  const sync = async () => { setSyncing(true); setError(""); try { const result = await syncMail(); await load(); setNotice(result.imported ? `同步完成，新增 ${result.imported} 封邮件` : "已同步，没有新邮件"); } catch (caught) { setError((caught as { response?: { data?: { detail?: string } } }).response?.data?.detail || "同步失败，请检查邮箱配置。"); } finally { setSyncing(false); } };
  const send = async (event: FormEvent, individually: boolean, recipientOverride?: string[]) => {
    event.preventDefault(); const recipients = recipientOverride || addresses(to);
    if (!recipients.length) { setError("请填写有效收件人邮箱。"); return; }
    if (individually && !window.confirm(`将分别发送给 ${recipients.length} 位收件人。`)) return;
    setSending(true); setError("");
    try {
      const data = { to_emails: recipients.join(","), cc_emails: cc, bcc_emails: bcc, subject, body: plain, html_body: html, customer_id: customerId ? +customerId : undefined, reply_to_id: replyTo, forward_of_id: forwardOf, draft_id: draftId, tracking_enabled: tracking, files };
      if (individually) { const result = await sendMailIndividually(data); setFailedRecipients(result.failed_addresses); setNotice(`分别发送：成功 ${result.sent.length}，失败 ${result.failed_addresses.length}`); if (result.failed_addresses.length) { await load(); return; } } else await sendMail(data);
      setCompose(false); setMailFolderId(undefined); setFolder("sent"); await load();
    } catch (caught) { setError((caught as { response?: { data?: { detail?: string } } }).response?.data?.detail || "邮件发送失败。"); } finally { setSending(false); }
  };
  const retryFailed = async () => { const retry = [...failedRecipients]; setFailedRecipients([]); await send({ preventDefault() {} } as FormEvent, true, retry); };
  const editDraft = () => { if (!selected?.is_draft) return; clearCompose(); setTo(selected.to_emails.join(", ")); setCc(selected.cc_emails.join(", ")); setBcc(selected.bcc_emails.join(", ")); setMoreRecipients(Boolean(selected.cc_emails.length || selected.bcc_emails.length)); setSubject(selected.subject); setHtml(selected.html_body || selected.body_text.replace(/\n/g, "<br>")); setPlain(selected.body_text); setDraftId(selected.id); setCompose(true); };
  const addFolder = async () => { const name = window.prompt("客户文件夹名称"); if (!name?.trim()) return; try { await createMailFolder({ name: name.trim() }); await load(); } catch { setError("无法创建文件夹。"); } };
  const nav: Array<[Folder, string, number]> = [["inbox", "收件箱", counts.inbox], ["sent", "已发送", counts.sent], ["drafts", "草稿", counts.drafts], ["starred", "星标", counts.starred], ["unread", "未读", counts.unread]];

  return <>
    <header className="mb-4 flex items-center justify-between"><div><p className="text-sm text-slate-500">Foxmail / QQ 邮箱</p><h2 className="text-3xl font-bold">邮件中心</h2></div>{user?.role === "Admin" && <button type="button" disabled={syncing} onClick={() => void sync()} className="rounded-lg border border-blue-600 px-4 py-2 text-sm text-blue-700 disabled:opacity-50">{syncing ? "同步中…" : "手动同步"}</button>}</header>
    {notice && <p className="mb-2 text-sm text-emerald-700">{notice}</p>}{error && <p className="mb-2 text-sm text-rose-600">{error}</p>}
    <section className="grid h-[calc(100vh-10rem)] min-h-[38rem] overflow-hidden rounded-xl border bg-white xl:grid-cols-[13rem_minmax(20rem,1fr)_minmax(27rem,1.2fr)]">
      <aside className="overflow-y-auto border-r bg-slate-50 p-3"><button type="button" onClick={() => void openCompose("new")} className="w-full rounded-lg bg-blue-700 py-2.5 text-sm font-semibold text-white">＋ 写邮件</button><nav className="mt-4 space-y-1">{nav.map(([key, label, count]) => <button key={key} type="button" onClick={() => { setMailFolderId(undefined); setFolder(key); }} className={`flex w-full justify-between rounded px-3 py-2 text-sm ${!mailFolderId && folder === key ? "bg-blue-100 text-blue-800" : "hover:bg-slate-200"}`}><span>{label}</span><span>{count}</span></button>)}</nav><div className="mt-5 border-t pt-3"><div className="mb-1 flex items-center justify-between px-1 text-xs font-semibold text-slate-500"><span>客户文件夹</span><button type="button" onClick={() => void addFolder()} className="text-blue-700">＋</button></div>{folders.map((entry) => <div key={entry.id} className={`flex items-center rounded text-sm ${mailFolderId === entry.id ? "bg-blue-100 text-blue-800" : "hover:bg-slate-200"}`}><button type="button" onClick={() => setMailFolderId(entry.id)} className="flex min-w-0 flex-1 justify-between px-3 py-2 text-left"><span className="truncate">{entry.name}</span><span>{entry.unread_count ? `${entry.unread_count}/${entry.message_count}` : entry.message_count}</span></button><button type="button" aria-label={`删除${entry.name}`} onClick={() => { if (window.confirm(`删除文件夹“${entry.name}”？邮件不会删除。`)) void deleteMailFolder(entry.id).then(() => { if (mailFolderId === entry.id) setMailFolderId(undefined); return load(); }).catch(() => setError("无法删除文件夹。")); }} className="px-2 text-slate-400 hover:text-rose-600">×</button></div>)}</div></aside>
      <section className="flex min-h-0 flex-col border-r"><div className="space-y-2 border-b p-3"><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索邮件" className="w-full rounded border px-3 py-2 text-sm" /><select value={customerId} onChange={(event) => setCustomerId(event.target.value)} className="w-full rounded border px-2 py-2 text-sm"><option value="">全部客户</option>{customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.company_name}</option>)}</select></div><div className="min-h-0 flex-1 overflow-y-auto">{items.map((message) => <button key={message.id} type="button" onClick={() => void open(message)} className={`flex w-full gap-2 border-b px-3 py-3 text-left hover:bg-slate-50 ${!message.is_read ? "border-l-4 border-l-blue-600 bg-blue-50/60" : ""}`}><span className="text-amber-400">{message.is_starred ? "★" : "☆"}</span><span className="min-w-0 flex-1"><span className="flex justify-between gap-2"><b className="truncate text-sm">{display(message)}</b><time className="text-xs text-slate-500">{date(message.sent_at)}</time></span><span className="block truncate text-sm">{message.subject || "(无主题)"}{message.has_attachments && "  📎"}</span><span className="block truncate text-xs text-slate-500">{message.body_text}</span><TrackingStatus message={message} /></span></button>)}</div></section>
      <section className="min-h-0 overflow-y-auto p-5">{selected ? <><div className="flex justify-between gap-3 border-b pb-4"><div><h3 className="text-xl font-bold">{selected.subject || "(无主题)"}</h3><p className="mt-2 text-sm">发件人：{selected.from_name || selected.from_email} &lt;{selected.from_email}&gt;</p><p className="text-sm">收件人：{selected.to_display.join(", ") || selected.to_emails.join(", ")}</p>{selected.cc_emails.length > 0 && <p className="text-sm">抄送：{selected.cc_emails.join(", ")}</p>}<p className="text-xs text-slate-500">{date(selected.sent_at)}</p>{selected.customer_id && <Link to={`/customers/${selected.customer_id}`} className="text-sm text-blue-700">查看关联客户 →</Link>}<TrackingStatus message={selected} detailed /></div><div className="flex h-fit flex-wrap gap-2 text-sm"><button type="button" onClick={() => void bulkUpdateMail([selected.id], { is_starred: !selected.is_starred }).then(load)}>{selected.is_starred ? "★" : "☆"}</button><button type="button" onClick={() => void bulkUpdateMail([selected.id], { is_read: false }).then(load)}>标记未读</button>{selected.is_draft ? <button type="button" onClick={editDraft}>编辑草稿</button> : <><button type="button" onClick={() => void openCompose("reply")}>回复</button><button type="button" onClick={() => void openCompose("all")}>回复全部</button><button type="button" onClick={() => void openCompose("forward")}>转发</button></>}</div></div><article className="mt-5 break-words text-sm leading-7" dangerouslySetInnerHTML={{ __html: selected.html_body || selected.body_text.replace(/\n/g, "<br>") }} />{selected.attachments.map((attachment) => <button key={attachment.id} type="button" onClick={() => void downloadMailAttachment(selected.id, attachment.id).then((blob) => window.open(URL.createObjectURL(blob), "_blank"))} className="mt-3 mr-2 rounded border px-2 py-1 text-sm text-blue-700">📎 {attachment.file_name}</button>)}</> : <p className="pt-24 text-center text-sm text-slate-500">选择邮件查看详情。</p>}</section>
    </section>
    {compose && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 p-4"><form onSubmit={(event) => void send(event, false)} className="flex max-h-[88vh] w-full max-w-4xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl"><header className="flex justify-between border-b px-5 py-3"><b>写邮件</b><button type="button" onClick={() => setCompose(false)}>×</button></header><div className="space-y-1 px-5 py-3"><input required value={to} onChange={(event) => setTo(event.target.value)} placeholder="收件人（逗号、分号或换行分隔）" className="w-full border-b px-1 py-2 text-sm outline-none" />{moreRecipients ? <><input value={cc} onChange={(event) => setCc(event.target.value)} placeholder="抄送" className="w-full border-b px-1 py-2 text-sm outline-none" /><input value={bcc} onChange={(event) => setBcc(event.target.value)} placeholder="密送" className="w-full border-b px-1 py-2 text-sm outline-none" /></> : <button type="button" onClick={() => setMoreRecipients(true)} className="text-xs text-blue-700">抄送 / 密送</button>}<input required value={subject} onChange={(event) => setSubject(event.target.value)} placeholder="主题" className="w-full border-b px-1 py-2 text-sm outline-none" /></div><div className="min-h-0 flex-1 overflow-y-auto px-5 pb-3"><MailRichTextEditor value={html} onChange={(nextHtml, nextText) => { setHtml(nextHtml); setPlain(nextText); }} /></div>{failedRecipients.length > 0 && <div className="border-t bg-amber-50 px-5 py-2 text-sm text-amber-900">发送失败：{failedRecipients.join(", ")} <button type="button" disabled={sending} onClick={() => void retryFailed()} className="ml-2 font-medium text-blue-700">仅重试失败项</button></div>}<footer className="flex flex-wrap items-center gap-3 border-t px-5 py-3"><button disabled={sending} type="submit" className="rounded-lg bg-blue-700 px-5 py-2 text-sm text-white disabled:opacity-50">{sending ? "发送中…" : "发送"}</button><button disabled={sending} type="button" onClick={(event) => void send(event as unknown as FormEvent, true)} className="rounded-lg border border-blue-600 px-4 py-2 text-sm text-blue-700">分别发送{addresses(to).length > 1 ? `（${addresses(to).length}）` : ""}</button><label className="text-sm"><input type="checkbox" checked={tracking} onChange={(event) => setTracking(event.target.checked)} /> 追踪打开</label><label className="text-sm">📎 <input type="file" multiple className="hidden" onChange={(event) => setFiles([...files, ...Array.from(event.target.files || [])])} />附件</label>{files.map((file, index) => <span key={`${file.name}-${index}`} className="text-xs">{file.name} <button type="button" onClick={() => setFiles(files.filter((_, fileIndex) => fileIndex !== index))}>×</button></span>)}<span className="flex-1" /><button type="button" onClick={() => void saveMailDraft({ to_emails: to, cc_emails: cc, bcc_emails: bcc, subject, body: plain, html_body: html, draft_id: draftId, files }).then((draft) => { setDraftId(draft.id); setNotice("草稿已保存"); })} className="text-sm text-slate-600">保存草稿</button></footer></form></div>}
  </>;
}
