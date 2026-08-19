import { useCallback, useEffect, useState, type FormEvent } from "react";
import type { AxiosError } from "axios";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  createQuotation,
  getOpportunity,
  getProducts,
  replaceOpportunityProducts,
  updateOpportunity,
} from "../services/crm";
import {
  opportunityDealStageClass,
  opportunityDealStageLabels,
  opportunityDealStages,
} from "../constants/opportunityDealStages";
import { useAuth } from "../store/auth";
import type {
  OpportunityDealStage,
  OpportunityDetail,
  OpportunityProduct,
  Product,
} from "../types";

export function OpportunityDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [opportunity, setOpportunity] = useState<OpportunityDetail | null>(null);
  const [catalog, setCatalog] = useState<Product[]>([]);
  const [productLines, setProductLines] = useState<OpportunityProduct[]>([]);
  const [selectedProduct, setSelectedProduct] = useState("");
  const [dealStage, setDealStage] = useState<OpportunityDealStage>("New Inquiry");
  const [amount, setAmount] = useState("");
  const [probability, setProbability] = useState("10");
  const [closeDate, setCloseDate] = useState("");
  const [nextAction, setNextAction] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [orderNotice, setOrderNotice] = useState<{ orderId: number; message: string } | null>(null);
  const editable = user?.role !== "Viewer";

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const item = await getOpportunity(id);
      setOpportunity(item);
      setProductLines(item.products);
      setDealStage(item.deal_stage);
      setAmount(item.amount ?? "");
      setProbability(String(item.probability));
      setCloseDate(item.expected_close_date ?? "");
      setNextAction(item.next_action ?? "");
      setError("");
      setOrderNotice(null);
    } catch (requestError: unknown) {
      const detail = (requestError as AxiosError<{ detail?: string }>).response?.data?.detail;
      setError(detail || "无法加载商机详情。");
    }
  }, [id]);

  useEffect(() => {
    void load();
    void getProducts({ limit: 100, offset: 0, is_active: true })
      .then((page) => setCatalog(page.items))
      .catch(() => undefined);
  }, [load]);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!opportunity) return;
    setSaving(true);
    try {
      const enteringWon = opportunity.deal_stage !== "Won" && dealStage === "Won";
      const item = await updateOpportunity(opportunity.id, {
        deal_stage: dealStage,
        amount: amount || undefined,
        probability: Number(probability),
        expected_close_date: closeDate || undefined,
        next_action: nextAction || null,
      });
      setOpportunity(item);
      setProductLines(item.products);
      setDealStage(item.deal_stage);
      setError("");
      if (enteringWon && item.order_id && item.order_no) {
        setOrderNotice({
          orderId: item.order_id,
          message: item.order_auto_created
            ? `商机已赢单，订单 ${item.order_no} 已自动创建。`
            : `该商机已存在订单 ${item.order_no}。`,
        });
      } else {
        setOrderNotice(null);
      }
    } catch (requestError: unknown) {
      const detail = (requestError as AxiosError<{ detail?: string }>).response?.data?.detail;
      setOrderNotice(null);
      setError(detail || "无法更新商机，请检查销售阶段、概率和金额。");
    } finally {
      setSaving(false);
    }
  }

  function addProduct() {
    const product = catalog.find((item) => item.id === Number(selectedProduct));
    if (!product || productLines.some((item) => item.product_id === product.id)) return;
    setProductLines([
      ...productLines,
      {
        product_id: product.id,
        sku: product.sku,
        name: product.name,
        quantity: "1",
        target_price: product.reference_price,
        reference_price: product.reference_price,
        currency_code: product.currency_code,
        image_url: product.images.find((image) => image.is_primary)?.image_url
          ?? product.images[0]?.image_url
          ?? null,
      },
    ]);
    setSelectedProduct("");
  }

  async function saveProducts() {
    if (!opportunity) return;
    setSaving(true);
    try {
      const item = await replaceOpportunityProducts(
        opportunity.id,
        productLines.map((line) => ({
          product_id: line.product_id,
          quantity: line.quantity,
          target_price: line.target_price ?? undefined,
        })),
      );
      setOpportunity(item);
      setProductLines(item.products);
      setError("");
    } catch {
      setError("无法保存商机产品。");
    } finally {
      setSaving(false);
    }
  }

  async function createQuote() {
    if (!opportunity) return;
    setSaving(true);
    try {
      const quotation = await createQuotation({
        opportunity_id: opportunity.id,
        currency: opportunity.currency,
      });
      navigate(`/quotations/${quotation.id}`);
    } catch {
      setError("无法创建报价，请先保存至少一个商机产品。");
      setSaving(false);
    }
  }

  if (!opportunity) return <p className="text-slate-500">{error || "加载中..."}</p>;

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link to="/opportunities" className="text-sm text-blue-700">← 返回商机列表</Link>
        {editable && (
          <div className="flex gap-2">
            {opportunity.order_id ? (
              <Link to={`/orders/${opportunity.order_id}`} className="rounded-lg border border-emerald-600 px-4 py-2 font-semibold text-emerald-700">查看订单</Link>
            ) : opportunity.deal_stage === "Won" ? (
              <Link to={`/orders/new?customer_id=${opportunity.customer_id}&opportunity_id=${opportunity.id}`} className="rounded-lg border border-emerald-600 px-4 py-2 font-semibold text-emerald-700">创建订单</Link>
            ) : null}
            <button type="button" disabled={saving} onClick={() => void createQuote()} className="rounded-lg bg-emerald-600 px-4 py-2 font-semibold text-white disabled:opacity-60">创建报价</button>
          </div>
        )}
      </div>
      <div className="mt-4">
        <p className="text-sm text-slate-500">{opportunity.public_id}</p>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <h2 className="text-3xl font-bold">{opportunity.name}</h2>
          <span className={`rounded-full px-3 py-1 text-sm font-medium ${opportunityDealStageClass(opportunity.deal_stage)}`}>
            {opportunityDealStageLabels[opportunity.deal_stage]}
          </span>
        </div>
        <Link to={`/customers/${opportunity.customer_id}`} className="mt-1 inline-block text-blue-700">
          {opportunity.customer_company}
        </Link>
        {opportunity.reminder_status !== "None" && (
          <div className={`mt-3 inline-flex rounded-full px-3 py-1 text-sm font-medium ${
            opportunity.reminder_status === "Quote Follow-up Due"
              ? "bg-rose-100 text-rose-700"
              : "bg-violet-100 text-violet-700"
          }`}>
            {opportunity.reminder_status === "Quote Follow-up Due"
              ? `报价待跟进：${opportunity.quote_followup_due_date ?? "请尽快处理"}`
              : `长期无活动：最后活动于 ${new Date(opportunity.last_activity_at).toLocaleDateString()}`}
          </div>
        )}
      </div>
      {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}
      {orderNotice && <p className="mt-4 rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{orderNotice.message} <Link className="font-semibold underline" to={`/orders/${orderNotice.orderId}`}>查看订单</Link></p>}

      <section className="mt-6 grid gap-5 lg:grid-cols-2">
        <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <h3 className="font-bold">商机资料</h3>
          <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
            <div><dt className="text-slate-500">产品需求</dt><dd>{opportunity.interested_product ?? "—"}</dd></div>
            <div><dt className="text-slate-500">负责人</dt><dd>{opportunity.owner_name ?? "—"}</dd></div>
            <div><dt className="text-slate-500">预计金额</dt><dd>{opportunity.amount ? `${opportunity.currency} ${opportunity.amount}` : "—"}</dd></div>
            <div><dt className="text-slate-500">预计成交</dt><dd>{opportunity.expected_close_date ?? "—"}</dd></div>
            <div><dt className="text-slate-500">成交概率</dt><dd>{opportunity.probability}%</dd></div>
            <div><dt className="text-slate-500">下一步行动</dt><dd>{opportunity.next_action ?? "—"}</dd></div>
          </dl>
          <p className="mt-5 whitespace-pre-wrap text-sm">{opportunity.inquiry_content ?? "暂无询盘内容。"}</p>
          {editable && (
            <form onSubmit={save} className="mt-5 grid gap-3 border-t pt-5 sm:grid-cols-2">
              <select
                value={dealStage}
                onChange={(event) => setDealStage(event.target.value as OpportunityDealStage)}
                className="rounded border px-3 py-2"
              >
                {opportunityDealStages.map((stage) => (
                  <option key={stage} value={stage}>{opportunityDealStageLabels[stage]}</option>
                ))}
              </select>
              <input type="number" min="0" max="100" value={probability} onChange={(event) => setProbability(event.target.value)} placeholder="成交概率 (%)" className="rounded border px-3 py-2" />
              <input type="number" min="0" step="0.01" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="预计金额" className="rounded border px-3 py-2" />
              <input type="date" value={closeDate} onChange={(event) => setCloseDate(event.target.value)} className="rounded border px-3 py-2" />
              <input maxLength={500} value={nextAction} onChange={(event) => setNextAction(event.target.value)} placeholder="下一步行动" className="rounded border px-3 py-2 sm:col-span-2" />
              <button disabled={saving} className="w-fit rounded bg-blue-600 px-4 py-2 font-semibold text-white disabled:opacity-60">保存销售进展</button>
            </form>
          )}
        </article>

        <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <h3 className="font-bold">客户与联系人</h3>
          <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm">
            <Link to={`/customers/${opportunity.customer_id}`} className="font-semibold text-blue-700">{opportunity.customer.company_name}</Link>
            <p className="mt-1 text-slate-600">{[opportunity.customer.country, opportunity.customer.email, opportunity.customer.whatsapp].filter(Boolean).join(" · ") || "暂无客户联系信息"}</p>
          </div>
          <div className="mt-4 space-y-3">
            {opportunity.contacts.map((contact) => (
              <div key={contact.id} className="border-l-2 border-blue-500 pl-3 text-sm">
                <strong>{contact.name}</strong>{contact.position && <span className="text-slate-500"> · {contact.position}</span>}
                <p className="mt-1 text-slate-600">{[contact.email, contact.phone, contact.whatsapp].filter(Boolean).join(" · ") || "暂无联系信息"}</p>
              </div>
            ))}
            {opportunity.contacts.length === 0 && <p className="text-sm text-slate-500">暂无独立联系人，客户主联系人仍可在客户详情中维护。</p>}
          </div>
        </article>
      </section>

      <section className="mt-5 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
        <h3 className="font-bold">销售阶段变化</h3>
        <div className="mt-4 space-y-4">
          {opportunity.deal_stage_history.map((history) => (
            <div key={history.id} className="border-l-2 border-blue-500 pl-4 text-sm">
              <strong>
                {history.old_deal_stage ? opportunityDealStageLabels[history.old_deal_stage] : "创建商机"}
                {" → "}
                <span className={`rounded-full px-2 py-1 text-xs ${opportunityDealStageClass(history.new_deal_stage)}`}>
                  {opportunityDealStageLabels[history.new_deal_stage]}
                </span>
              </strong>
              <p className="mt-2 text-slate-500">{new Date(history.created_at).toLocaleString()}</p>
            </div>
          ))}
          {opportunity.deal_stage_history.length === 0 && <p className="text-sm text-slate-500">暂无阶段记录。</p>}
        </div>
      </section>

      <section className="mt-5 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
        <div className="flex flex-wrap justify-between gap-3">
          <div>
            <h3 className="font-bold">商机产品</h3>
            <p className="text-sm text-slate-500">创建报价时将复制这里的产品、数量和目标价。</p>
          </div>
          {editable && (
            <div className="flex gap-2">
              <select value={selectedProduct} onChange={(event) => setSelectedProduct(event.target.value)} className="rounded border px-3 py-2">
                <option value="">选择产品</option>
                {catalog.filter((product) => !productLines.some((line) => line.product_id === product.id)).map((product) => (
                  <option key={product.id} value={product.id}>{product.sku} · {product.name}</option>
                ))}
              </select>
              <button onClick={addProduct} className="rounded border px-3 py-2 text-blue-700">添加</button>
            </div>
          )}
        </div>
        <div className="mt-4 space-y-3">
          {productLines.map((line, index) => (
            <div key={line.product_id} className="grid items-center gap-3 rounded-lg bg-slate-50 p-3 md:grid-cols-[1fr_120px_160px_auto]">
              <div>
                <Link to={`/products/${line.product_id}`} className="font-medium text-blue-700">{line.name}</Link>
                <p className="text-xs text-slate-500">{line.sku} · 参考 {line.currency_code} {line.reference_price ?? "—"}</p>
              </div>
              <input disabled={!editable} type="number" min="0.01" step="0.01" value={line.quantity} onChange={(event) => setProductLines(productLines.map((item, current) => current === index ? { ...item, quantity: event.target.value } : item))} className="rounded border px-2 py-1" />
              <input disabled={!editable} type="number" min="0" step="0.01" value={line.target_price ?? ""} onChange={(event) => setProductLines(productLines.map((item, current) => current === index ? { ...item, target_price: event.target.value || null } : item))} className="rounded border px-2 py-1" />
              {editable && <button onClick={() => setProductLines(productLines.filter((_, current) => current !== index))} className="text-rose-600">移除</button>}
            </div>
          ))}
          {productLines.length === 0 && <p className="text-sm text-slate-500">暂无商机产品。</p>}
        </div>
        {editable && <button onClick={() => void saveProducts()} disabled={saving} className="mt-4 rounded bg-slate-900 px-4 py-2 font-semibold text-white disabled:opacity-60">保存产品明细</button>}
      </section>

      <section className="mt-5 grid gap-5 lg:grid-cols-2">
        <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <h3 className="font-bold">关联报价</h3>
          <div className="mt-3 space-y-3">
            {opportunity.quotations.map((quotation) => (
              <Link key={quotation.id} to={`/quotations/${quotation.id}`} className="block rounded-lg bg-slate-50 p-3 hover:ring-1 hover:ring-blue-300">
                <div className="flex flex-wrap items-center justify-between gap-2"><strong className="text-blue-700">{quotation.quotation_number}</strong><span className="text-sm text-slate-500">{quotation.status}</span></div>
                <p className="mt-1 text-sm">{quotation.currency} {quotation.total_amount}</p>
              </Link>
            ))}
            {opportunity.quotations.length === 0 && <p className="text-sm text-slate-500">暂无关联报价。</p>}
          </div>
        </article>
        <article className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <h3 className="font-bold">关联跟进记录</h3>
          <p className="mt-1 text-sm text-slate-500">完整跟进和编辑入口位于客户详情页。</p>
          <div className="mt-3 space-y-3">
            {opportunity.followups.length ? opportunity.followups.map((followup) => (
              <div key={followup.id} className="rounded bg-slate-50 p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2"><strong>{followup.type}</strong><span className="text-slate-500">跟进日期：{followup.followup_date}</span>{followup.next_followup_date && <span className="text-slate-500">下次：{followup.next_followup_date}</span>}</div>
                <p className="mt-1 whitespace-pre-wrap">{followup.content}</p>
                {followup.attachments.length > 0 && <p className="mt-2 text-xs text-slate-500">附件：{followup.attachments.map((attachment) => attachment.file_name).join("、")}</p>}
              </div>
            )) : <p className="text-sm text-slate-500">暂无记录。</p>}
          </div>
        </article>
      </section>
    </>
  );
}
