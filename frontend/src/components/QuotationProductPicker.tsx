import { useMemo, useState, type FormEvent } from "react";

import { searchQuotationProducts } from "../services/crm";
import type { Product } from "../types";

type QuotationProductPickerProps = {
  disabled?: boolean;
  selectedProductIds: number[];
  onAddProducts: (products: Product[]) => void;
};

function primaryImage(product: Product) {
  return product.images.find((image) => image.is_primary) ?? product.images[0];
}

/**
 * Catalogue picker for customer-created quotations. It only queries the
 * existing Products API and never owns quote lines, keeping price/quantity
 * editing in the parent quotation form.
 */
export function QuotationProductPicker({
  disabled = false,
  selectedProductIds,
  onAddProducts,
}: QuotationProductPickerProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [checkedIds, setCheckedIds] = useState<number[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");
  const selectedIds = useMemo(() => new Set(selectedProductIds), [selectedProductIds]);
  const selectableResults = useMemo(
    () => results.filter((product) => !selectedIds.has(product.id)),
    [results, selectedIds],
  );
  const checkedSelectable = useMemo(
    () => checkedIds.filter((id) => !selectedIds.has(id)),
    [checkedIds, selectedIds],
  );

  async function search(event?: FormEvent) {
    event?.preventDefault();
    const value = query.trim();
    if (!value) {
      setResults([]);
      setTotal(0);
      setCheckedIds([]);
      setSearched(false);
      return;
    }
    setLoading(true);
    setError("");
    setSearched(true);
    try {
      const page = await searchQuotationProducts(value);
      setResults(page.items);
      setTotal(page.total);
      setCheckedIds((current) => current.filter((id) => page.items.some((product) => product.id === id)));
    } catch {
      setResults([]);
      setTotal(0);
      setCheckedIds([]);
      setError("无法搜索产品库，请稍后重试。");
    } finally {
      setLoading(false);
    }
  }

  function toggle(productId: number) {
    setCheckedIds((current) => (
      current.includes(productId)
        ? current.filter((id) => id !== productId)
        : [...current, productId]
    ));
  }

  function add(products: Product[]) {
    const additions = products.filter((product) => !selectedIds.has(product.id));
    if (!additions.length) return;
    onAddProducts(additions);
    setCheckedIds((current) => current.filter((id) => !additions.some((product) => product.id === id)));
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-900">搜索产品</h3>
          <p className="mt-1 text-sm text-slate-500">
            可输入 SKU 或产品名称。多个 SKU 用空格分隔；产品名称会按完整短语匹配。
          </p>
        </div>
        {searched && !loading && <span className="text-sm text-slate-500">找到 {total} 个匹配产品</span>}
      </div>

      <form onSubmit={(event) => void search(event)} className="mt-4 flex gap-2">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          disabled={disabled || loading}
          placeholder="例如：SL-P-001 SL-P-026 或 Pink Tower Brown Stair"
          className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none ring-blue-500 focus:ring-2 disabled:bg-slate-100"
        />
        <button
          type="submit"
          disabled={disabled || loading || !query.trim()}
          className="rounded-lg bg-blue-700 px-4 py-2 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "搜索中…" : "搜索"}
        </button>
      </form>

      <div className="mt-4 rounded-lg border border-slate-200 bg-white">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-3 py-2">
          <strong className="text-sm">搜索结果</strong>
          <div className="flex flex-wrap gap-2 text-sm">
            <button type="button" disabled={disabled || !selectableResults.length} onClick={() => setCheckedIds(selectableResults.map((product) => product.id))} className="text-blue-700 disabled:opacity-40">全选</button>
            <button type="button" disabled={disabled || !checkedSelectable.length} onClick={() => setCheckedIds([])} className="text-slate-600 disabled:opacity-40">取消全选</button>
            <button type="button" disabled={disabled || !checkedSelectable.length} onClick={() => add(results.filter((product) => checkedSelectable.includes(product.id)))} className="rounded border border-blue-600 px-2 py-1 font-semibold text-blue-700 disabled:cursor-not-allowed disabled:opacity-40">添加已选产品</button>
          </div>
        </div>

        {loading && <p className="p-6 text-center text-sm text-slate-500">正在搜索产品…</p>}
        {!loading && !searched && <p className="p-6 text-center text-sm text-slate-500">输入关键词后点击搜索，结果会显示在这里。</p>}
        {!loading && searched && error && <p className="p-6 text-center text-sm text-rose-600">{error}</p>}
        {!loading && searched && !error && !results.length && <p className="p-6 text-center text-sm text-slate-500">未找到匹配产品</p>}
        {!loading && searched && !error && !!results.length && (
          <div className="max-h-96 overflow-y-auto">
            {results.map((product) => {
              const image = primaryImage(product);
              const alreadyAdded = selectedIds.has(product.id);
              const isChecked = checkedIds.includes(product.id);
              return (
                <div key={product.id} className="flex min-w-[680px] items-center gap-3 border-b border-slate-100 px-3 py-2 last:border-b-0">
                  <input type="checkbox" checked={isChecked} disabled={disabled || alreadyAdded} onChange={() => toggle(product.id)} aria-label={`选择 ${product.sku}`} />
                  {image ? <img src={image.image_url} alt="" className="h-12 w-12 rounded object-cover" /> : <span className="flex h-12 w-12 items-center justify-center rounded bg-slate-100 text-xs text-slate-400">No image</span>}
                  <div className="min-w-0 flex-1"><p className="font-mono text-xs text-slate-500">{product.sku}</p><p className="truncate font-medium">{product.name}</p></div>
                  <span className="w-36 text-sm text-slate-600">{product.category_name ?? "未分类"}</span>
                  <span className="w-28 text-right text-sm">{product.reference_price === null ? "—" : `${product.currency_code} ${product.reference_price}`}</span>
                  <button type="button" disabled={disabled || alreadyAdded} onClick={() => add([product])} className="w-16 text-right text-sm font-semibold text-blue-700 disabled:cursor-default disabled:text-slate-400">{alreadyAdded ? "已添加" : "添加"}</button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
