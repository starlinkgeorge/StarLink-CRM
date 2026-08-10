import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  createQuotationVersion,
  downloadQuotationPdf,
  generateQuotationPdf,
  getProducts,
  getQuotation,
  markQuotationSent,
  updateQuotation,
} from "../services/crm";
import { useAuth } from "../store/auth";
import type { Product, QuotationDetail, QuotationItem } from "../types";

type DraftLine = Pick<
  QuotationItem,
  | "product_id"
  | "sku_snapshot"
  | "product_name_snapshot"
  | "picture_snapshot"
  | "unit_price"
  | "quantity"
  | "line_total"
>;

export function QuotationDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [quotation, setQuotation] = useState<QuotationDetail | null>(null);
  const [catalog, setCatalog] = useState<Product[]>([]);
  const [catalogSearch, setCatalogSearch] = useState("");
  const [catalogTotal, setCatalogTotal] = useState(0);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [currency, setCurrency] = useState("USD");
  const [paymentTerm, setPaymentTerm] = useState("");
  const [deliveryTime, setDeliveryTime] = useState("");
  const [validityDays, setValidityDays] = useState(30);
  const [shippingCost, setShippingCost] = useState("0");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const applyQuotation = useCallback((item: QuotationDetail) => {
    const version = item.selected_version;
    setQuotation(item);
    setLines(version.items);
    setCurrency(version.currency);
    setPaymentTerm(version.payment_term);
    setDeliveryTime(version.delivery_time);
    setValidityDays(version.validity_days);
    setShippingCost(version.shipping_cost);
  }, []);

  const load = useCallback(async () => {
    if (!id) {
      return;
    }
    try {
      applyQuotation(await getQuotation(id));
      setError("");
    } catch {
      setError("无法加载报价详情。");
    }
  }, [applyQuotation, id]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    let cancelled = false;
    const searchTerm = catalogSearch.trim();
    const delay = window.setTimeout(() => {
      setCatalogLoading(true);
      void getProducts({
        limit: 100,
        offset: 0,
        q: searchTerm || undefined,
        is_active: true,
      })
        .then((page) => {
          if (!cancelled) {
            setCatalog(page.items);
            setCatalogTotal(page.total);
          }
        })
        .catch(() => {
          if (!cancelled) {
            setCatalog([]);
            setCatalogTotal(0);
          }
        })
        .finally(() => {
          if (!cancelled) {
            setCatalogLoading(false);
          }
        });
    }, searchTerm ? 250 : 0);

    return () => {
      cancelled = true;
      window.clearTimeout(delay);
    };
  }, [catalogSearch]);

  const availableProducts = useMemo(
    () =>
      catalog.filter(
        (product) => !lines.some((line) => line.product_id === product.id),
      ),
    [catalog, lines],
  );

  if (!quotation) {
    return <p className="text-slate-500">{error || "加载中…"}</p>;
  }

  const selectedVersion = quotation.selected_version;
  const isCurrentVersion =
    selectedVersion.version_no === quotation.current_version;
  const editable =
    user?.role !== "Viewer" &&
    quotation.status === "Draft" &&
    isCurrentVersion;
  const quotationId = quotation.id;
  const selectedVersionNo = selectedVersion.version_no;
  const subtotal = lines.reduce(
    (sum, line) =>
      sum + Number(line.unit_price || 0) * Number(line.quantity || 0),
    0,
  );
  const amount = subtotal + Number(shippingCost || 0);

  async function selectVersion(versionNo: number) {
    if (!id) {
      return;
    }
    setSaving(true);
    try {
      applyQuotation(await getQuotation(id, versionNo));
    } catch {
      setError("无法加载历史版本。");
    } finally {
      setSaving(false);
    }
  }

  function addProduct(product: Product) {
    if (lines.some((line) => line.product_id === product.id)) {
      return;
    }
    const price = product.reference_price ?? "0";
    setLines([
      ...lines,
      {
        product_id: product.id,
        sku_snapshot: product.sku,
        product_name_snapshot: product.name,
        picture_snapshot:
          product.images.find((image) => image.is_primary)?.image_url ??
          product.images[0]?.image_url ??
          null,
        unit_price: price,
        quantity: "1",
        line_total: price,
      },
    ]);
    setCatalogSearch("");
  }

  async function saveDraft() {
    if (lines.some((line) => !line.product_id)) {
      setError("已删除的历史产品不能加入新草稿，请移除该行。");
      return;
    }
    setSaving(true);
    try {
      applyQuotation(
        await updateQuotation(quotationId, {
          currency,
          payment_term: paymentTerm,
          delivery_time: deliveryTime,
          validity_days: validityDays,
          shipping_cost: shippingCost,
          items: lines.map((line) => ({
            product_id: line.product_id!,
            unit_price: line.unit_price,
            quantity: line.quantity,
          })),
        }),
      );
      setError("");
    } catch {
      setError("保存草稿失败，请检查产品、价格和条款。");
    } finally {
      setSaving(false);
    }
  }

  async function generateAndOpen() {
    setSaving(true);
    try {
      applyQuotation(
        await generateQuotationPdf(quotationId, selectedVersionNo),
      );
      const blob = await downloadQuotationPdf(quotationId, selectedVersionNo);
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener,noreferrer");
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
      setError("");
    } catch {
      setError("PDF 生成或下载失败。");
    } finally {
      setSaving(false);
    }
  }

  async function downloadExisting() {
    setSaving(true);
    try {
      const blob = await downloadQuotationPdf(quotationId, selectedVersionNo);
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener,noreferrer");
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch {
      setError("PDF 下载失败。");
    } finally {
      setSaving(false);
    }
  }

  async function sendQuotation() {
    setSaving(true);
    try {
      applyQuotation(await markQuotationSent(quotationId));
      setError("");
    } catch {
      setError("无法锁定并标记此报价为已发送。");
    } finally {
      setSaving(false);
    }
  }

  async function reviseQuotation() {
    setSaving(true);
    try {
      applyQuotation(await createQuotationVersion(quotationId));
      setError("");
    } catch {
      setError("无法创建新版本。");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <Link to="/quotations" className="text-sm text-blue-700">
        ← 返回报价列表
      </Link>

      <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-mono text-sm text-slate-500">
            {quotation.quotation_number}
          </p>
          <h2 className="text-3xl font-bold">
            报价 V{selectedVersion.version_no}
          </h2>
          <p className="mt-1 text-slate-500">
            {quotation.customer_company} · {quotation.opportunity_name}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            value={selectedVersion.version_no}
            onChange={(event) => void selectVersion(Number(event.target.value))}
            className="rounded border px-3 py-2"
          >
            {quotation.versions.map((version) => (
              <option key={version.id} value={version.version_no}>
                V{version.version_no} · {version.currency} {version.total_amount}
              </option>
            ))}
          </select>
          {selectedVersion.pdf_url && (
            <button
              disabled={saving}
              onClick={() => void downloadExisting()}
              className="rounded border px-3 py-2 text-blue-700"
            >
              查看 PDF
            </button>
          )}
          {user?.role !== "Viewer" && (
            <button
              disabled={saving}
              onClick={() => void generateAndOpen()}
              className="rounded border border-blue-600 px-3 py-2 text-blue-700"
            >
              生成 PDF
            </button>
          )}
          {editable && (
            <button
              disabled={saving}
              onClick={() => void sendQuotation()}
              className="rounded bg-emerald-600 px-3 py-2 font-semibold text-white"
            >
              标记已发送
            </button>
          )}
          {user?.role !== "Viewer" &&
            quotation.status !== "Draft" &&
            isCurrentVersion && (
              <button
                disabled={saving}
                onClick={() => void reviseQuotation()}
                className="rounded bg-blue-600 px-3 py-2 font-semibold text-white"
              >
                创建 V{quotation.current_version + 1}
              </button>
            )}
        </div>
      </div>

      {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}

      <section className="mt-6 overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
        <header className="border-b-2 border-[#153A5B] p-6">
          <div className="flex flex-wrap justify-between gap-4">
            <div>
              <h3 className="text-xl font-bold text-[#153A5B]">
                {quotation.company_contact.name}
              </h3>
              <div className="mt-3 text-sm text-slate-600">
                <p>Website: {quotation.company_contact.website || "未配置"}</p>
                <p>Email: {quotation.company_contact.email || "未配置"}</p>
                <p>WhatsApp: {quotation.company_contact.whatsapp || "未配置"}</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-2xl font-bold text-[#153A5B]">QUOTATION</p>
              <p className="mt-2 font-mono">{quotation.quotation_number}</p>
              <p className="text-sm text-slate-500">
                Version V{selectedVersion.version_no} · {quotation.status}
              </p>
            </div>
          </div>
        </header>

        <div className="p-6">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <h3 className="font-bold">报价明细</h3>
            {editable && (
              <div className="flex flex-wrap items-end gap-2">
                <label className="grid gap-1 text-xs font-medium text-slate-600">
                  搜索产品
                  <input
                    value={catalogSearch}
                    onChange={(event) => setCatalogSearch(event.target.value)}
                    placeholder="输入 SKU、产品名称或材质"
                    className="w-64 rounded border px-3 py-2 text-sm"
                  />
                </label>
                <label className="hidden">
                  选择产品
                  <select
                    value=""
                    onChange={() => undefined}
                    className="hidden"
                    disabled
                  >
                    <option value="">
                      {catalogLoading
                        ? "正在搜索产品…"
                        : availableProducts.length
                          ? "从搜索结果中选择"
                          : "没有匹配的可添加产品"}
                    </option>
                    {availableProducts.map((product) => (
                      <option key={product.id} value={product.id}>
                        {product.sku} · {product.name}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  disabled
                  onClick={() => undefined}
                  className="hidden"
                >
                  添加
                </button>
                <p className="basis-full text-xs text-slate-500">
                  {catalogSearch.trim()
                    ? `找到 ${catalogTotal} 个产品`
                    : "可输入 SKU、产品名称或材质缩小范围。"}
                </p>
                {catalogSearch.trim() && !catalogLoading && (
                  <div className="basis-full grid max-h-72 gap-2 overflow-y-auto rounded-lg border border-slate-200 bg-slate-50 p-2 sm:grid-cols-2">
                    {availableProducts.map((product) => {
                      const primaryImage =
                        product.images.find((image) => image.is_primary) ??
                        product.images[0];
                      return (
                        <button
                          key={product.id}
                          type="button"
                          onClick={() => addProduct(product)}
                          className="flex min-w-0 items-center gap-3 rounded-md border border-slate-200 bg-white p-2 text-left transition hover:border-blue-500 hover:bg-blue-50"
                        >
                          {primaryImage ? (
                            <img
                              src={primaryImage.image_url}
                              alt=""
                              className="h-12 w-12 shrink-0 rounded object-cover"
                            />
                          ) : (
                            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded bg-slate-100 text-xs text-slate-400">
                              No image
                            </span>
                          )}
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-xs text-slate-500">
                              {product.sku}
                            </span>
                            <span className="block truncate text-sm font-semibold text-slate-800">
                              {product.name}
                            </span>
                            <span className="block text-xs text-slate-600">
                              {product.currency_code} {product.reference_price ?? "0.00"}
                            </span>
                          </span>
                          <span className="shrink-0 text-sm font-medium text-blue-700">
                            Add
                          </span>
                        </button>
                      );
                    })}
                    {!availableProducts.length && (
                      <p className="col-span-full p-3 text-center text-sm text-slate-500">
                        {catalogTotal
                          ? "All matching products are already in this quotation."
                          : "No matching active products found."}
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-[#153A5B] text-white">
                <tr>
                  <th className="px-3 py-3">Item Name</th>
                  <th className="px-3 py-3">Picture</th>
                  <th className="px-3 py-3">Unit Price</th>
                  <th className="px-3 py-3">QTY</th>
                  <th className="px-3 py-3">Total Price</th>
                  {editable && <th className="px-3 py-3" />}
                </tr>
              </thead>
              <tbody>
                {lines.map((line, index) => {
                  const lineTotal =
                    Number(line.unit_price || 0) * Number(line.quantity || 0);
                  return (
                    <tr key={`${line.product_id}-${index}`} className="border-b">
                      <td className="px-3 py-3">
                        <strong>{line.product_name_snapshot}</strong>
                        <p className="font-mono text-xs text-slate-500">
                          {line.sku_snapshot}
                        </p>
                      </td>
                      <td className="px-3 py-3">
                        {line.picture_snapshot ? (
                          <img
                            src={line.picture_snapshot}
                            alt=""
                            className="h-16 w-16 rounded object-cover"
                          />
                        ) : (
                          <div className="flex h-16 w-16 items-center justify-center rounded bg-slate-100 text-xs text-slate-400">
                            No image
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-3">
                        {editable ? (
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            value={line.unit_price}
                            onChange={(event) =>
                              setLines(
                                lines.map((item, currentIndex) =>
                                  currentIndex === index
                                    ? { ...item, unit_price: event.target.value }
                                    : item,
                                ),
                              )
                            }
                            className="w-28 rounded border px-2 py-1"
                          />
                        ) : (
                          `${currency} ${line.unit_price}`
                        )}
                      </td>
                      <td className="px-3 py-3">
                        {editable ? (
                          <input
                            type="number"
                            min="0.01"
                            step="0.01"
                            value={line.quantity}
                            onChange={(event) =>
                              setLines(
                                lines.map((item, currentIndex) =>
                                  currentIndex === index
                                    ? { ...item, quantity: event.target.value }
                                    : item,
                                ),
                              )
                            }
                            className="w-24 rounded border px-2 py-1"
                          />
                        ) : (
                          line.quantity
                        )}
                      </td>
                      <td className="px-3 py-3 font-semibold">
                        {currency} {lineTotal.toFixed(2)}
                      </td>
                      {editable && (
                        <td className="px-3 py-3">
                          <button
                            type="button"
                            onClick={() =>
                              setLines(
                                lines.filter(
                                  (_, currentIndex) => currentIndex !== index,
                                ),
                              )
                            }
                            className="text-rose-600"
                          >
                            移除
                          </button>
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="mt-5 ml-auto max-w-md space-y-2 text-sm">
            <div className="flex justify-between border-b pb-2">
              <span>Total cost</span>
              <strong>
                {currency} {subtotal.toFixed(2)}
              </strong>
            </div>
            <div className="flex items-center justify-between border-b pb-2">
              <span>Door to door shipping cost</span>
              {editable ? (
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={shippingCost}
                  onChange={(event) => setShippingCost(event.target.value)}
                  className="w-32 rounded border px-2 py-1 text-right"
                />
              ) : (
                <strong>
                  {currency} {Number(shippingCost).toFixed(2)}
                </strong>
              )}
            </div>
            <div className="flex justify-between bg-[#153A5B] p-3 text-white">
              <strong>Amount</strong>
              <strong>
                {currency} {amount.toFixed(2)}
              </strong>
            </div>
          </div>

          <div className="mt-7">
            <h3 className="font-bold text-[#153A5B]">TERMS</h3>
            <div className="mt-3 grid gap-3">
              <label className="grid gap-1 text-sm">
                Validity (days)
                <input
                  disabled={!editable}
                  type="number"
                  min="1"
                  max="365"
                  value={validityDays}
                  onChange={(event) => setValidityDays(Number(event.target.value))}
                  className="rounded border px-3 py-2 disabled:bg-slate-50"
                />
              </label>
              <label className="grid gap-1 text-sm">
                Payment Term
                <input
                  disabled={!editable}
                  value={paymentTerm}
                  onChange={(event) => setPaymentTerm(event.target.value)}
                  className="rounded border px-3 py-2 disabled:bg-slate-50"
                />
              </label>
              <label className="grid gap-1 text-sm">
                Delivery Time
                <input
                  disabled={!editable}
                  value={deliveryTime}
                  onChange={(event) => setDeliveryTime(event.target.value)}
                  className="rounded border px-3 py-2 disabled:bg-slate-50"
                />
              </label>
              <label className="grid gap-1 text-sm">
                Currency
                <input
                  disabled={!editable}
                  value={currency}
                  maxLength={3}
                  onChange={(event) => setCurrency(event.target.value.toUpperCase())}
                  className="rounded border px-3 py-2 disabled:bg-slate-50"
                />
              </label>
            </div>
          </div>

          {editable && (
            <button
              disabled={saving || lines.length === 0}
              onClick={() => void saveDraft()}
              className="mt-5 rounded bg-slate-900 px-5 py-2 font-semibold text-white disabled:opacity-50"
            >
              保存草稿 V{quotation.current_version}
            </button>
          )}
        </div>
      </section>
    </>
  );
}
