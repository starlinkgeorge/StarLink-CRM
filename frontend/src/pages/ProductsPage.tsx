import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import {
  createProduct,
  createProductCategory,
  deleteProduct,
  getProductCategories,
  getProducts,
  updateProduct,
  type ProductPayload,
} from "../services/crm";
import { useAuth } from "../store/auth";
import type { ProductCategory, ProductPage } from "../types";

const PAGE_SIZE = 20;
const emptyProduct: ProductPayload = { sku: "", name: "", unit: "piece", currency_code: "USD", is_active: true };

export function ProductsPage() {
  const { user } = useAuth();
  const editable = user?.role !== "Viewer";
  const canDelete = user?.role === "Admin";
  const [data, setData] = useState<ProductPage | null>(null);
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [offset, setOffset] = useState(0);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [activeStatus, setActiveStatus] = useState("");
  const [filters, setFilters] = useState({ q: "", category_id: "", is_active: "" });
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<ProductPayload>(emptyProduct);
  const [imageUrl, setImageUrl] = useState("");
  const [categoryName, setCategoryName] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [deletingProductId, setDeletingProductId] = useState<number | null>(null);

  const loadCategories = useCallback(async () => setCategories(await getProductCategories()), []);
  const load = useCallback(async (currentOffset = offset, currentFilters = filters) => {
    try {
      setData(await getProducts({
        limit: PAGE_SIZE,
        offset: currentOffset,
        q: currentFilters.q || undefined,
        category_id: currentFilters.category_id ? Number(currentFilters.category_id) : undefined,
        is_active: currentFilters.is_active === "" ? undefined : currentFilters.is_active === "true",
      }));
      setError("");
    } catch { setError("无法加载产品列表。"); }
  }, [offset, filters]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { void loadCategories().catch(() => setError("无法加载产品分类。")); }, [loadCategories]);

  function search(event: FormEvent) {
    event.preventDefault();
    setOffset(0);
    setFilters({ q: query, category_id: category, is_active: activeStatus });
  }

  async function submitProduct(event: FormEvent) {
    event.preventDefault(); setSaving(true);
    try {
      await createProduct({ ...form, images: imageUrl.trim() ? [{ image_url: imageUrl.trim(), is_primary: true }] : [] });
      setForm(emptyProduct); setImageUrl(""); setShowCreate(false); setOffset(0); await load(0);
    } catch { setError("产品创建失败，请检查 SKU 是否重复及字段格式。"); }
    finally { setSaving(false); }
  }

  async function submitCategory(event: FormEvent) {
    event.preventDefault();
    if (!categoryName.trim()) return;
    try { await createProductCategory({ name: categoryName.trim() }); setCategoryName(""); await loadCategories(); }
    catch { setError("产品分类创建失败。"); }
  }

  async function toggleActive(productId: number, isActive: boolean) {
    try { await updateProduct(productId, { is_active: !isActive }); await load(); }
    catch { setError("无法更新产品状态。"); }
  }

  async function removeProduct(productId: number, productName: string) {
    if (!window.confirm(`确定要删除产品“${productName}”吗？此操作不可恢复。`)) return;
    setDeletingProductId(productId);
    try {
      await deleteProduct(productId);
      setError("");
      const nextOffset = data?.items.length === 1 && offset > 0 ? offset - PAGE_SIZE : offset;
      if (nextOffset !== offset) setOffset(nextOffset);
      else await load(nextOffset);
    } catch {
      setError("无法删除产品。如果它已关联商机，请先从商机中移除该产品。");
    } finally {
      setDeletingProductId(null);
    }
  }

  return <>
    <div className="flex flex-wrap items-center justify-between gap-4"><div><p className="text-sm text-slate-500">SKU、规格、价格与图片管理</p><h2 className="text-3xl font-bold">产品库</h2></div>{editable && <button onClick={() => setShowCreate(!showCreate)} className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white">{showCreate ? "取消新增" : "新增产品"}</button>}</div>
    {showCreate && <section className="mt-6 grid gap-5 xl:grid-cols-[3fr_1fr]"><form onSubmit={submitProduct} className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><h3 className="font-bold">新增产品</h3><div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3"><input required value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value })} placeholder="SKU *" className="rounded-lg border px-3 py-2" /><input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="产品名称 *" className="rounded-lg border px-3 py-2" /><select value={form.category_id ?? ""} onChange={(e) => setForm({ ...form, category_id: e.target.value ? Number(e.target.value) : undefined })} className="rounded-lg border px-3 py-2"><option value="">未分类</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select><input value={form.material ?? ""} onChange={(e) => setForm({ ...form, material: e.target.value })} placeholder="材质" className="rounded-lg border px-3 py-2" /><input value={form.dimension_text ?? ""} onChange={(e) => setForm({ ...form, dimension_text: e.target.value })} placeholder="尺寸说明" className="rounded-lg border px-3 py-2" /><input type="number" min="1" value={form.moq ?? ""} onChange={(e) => setForm({ ...form, moq: e.target.value ? Number(e.target.value) : undefined })} placeholder="MOQ" className="rounded-lg border px-3 py-2" /><input type="number" min="0" step="0.01" value={form.reference_price ?? ""} onChange={(e) => setForm({ ...form, reference_price: e.target.value })} placeholder="参考价格" className="rounded-lg border px-3 py-2" /><input value={form.currency_code ?? "USD"} maxLength={3} onChange={(e) => setForm({ ...form, currency_code: e.target.value.toUpperCase() })} placeholder="币种" className="rounded-lg border px-3 py-2" /><input value={imageUrl} onChange={(e) => setImageUrl(e.target.value)} placeholder="主图 URL（http/https）" className="rounded-lg border px-3 py-2" /><textarea value={form.description ?? ""} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="产品描述" className="min-h-24 rounded-lg border px-3 py-2 md:col-span-2 xl:col-span-3" /></div><button disabled={saving} className="mt-4 rounded-lg bg-slate-900 px-4 py-2 font-semibold text-white disabled:opacity-60">{saving ? "保存中…" : "保存产品"}</button></form><form onSubmit={submitCategory} className="h-fit rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><h3 className="font-bold">快速新增分类</h3><input value={categoryName} onChange={(e) => setCategoryName(e.target.value)} placeholder="分类名称" className="mt-4 w-full rounded-lg border px-3 py-2" /><button className="mt-3 rounded-lg border border-blue-600 px-3 py-2 text-sm font-semibold text-blue-700">新增分类</button></form></section>}
    <form onSubmit={search} className="mt-6 flex flex-wrap gap-3 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200"><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索 SKU、名称或材质" className="min-w-64 flex-1 rounded-lg border px-3 py-2" /><select value={category} onChange={(e) => setCategory(e.target.value)} className="rounded-lg border px-3 py-2"><option value="">全部分类</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select><select value={activeStatus} onChange={(e) => setActiveStatus(e.target.value)} className="rounded-lg border px-3 py-2"><option value="">全部状态</option><option value="true">已启用</option><option value="false">已停用</option></select><button className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white">筛选</button></form>
    {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}
    <div className="mt-6 overflow-x-auto rounded-xl bg-white shadow-sm ring-1 ring-slate-200"><table className="min-w-full text-left text-sm"><thead className="bg-slate-50 text-slate-500"><tr><th className="px-4 py-3">产品</th><th className="px-4 py-3">SKU</th><th className="px-4 py-3">分类</th><th className="px-4 py-3">材质 / 尺寸</th><th className="px-4 py-3">MOQ</th><th className="px-4 py-3">参考价格</th><th className="px-4 py-3">状态</th><th className="px-4 py-3">操作</th></tr></thead><tbody>{data?.items.map((item) => <tr key={item.id} className="border-t"><td className="px-4 py-3"><div className="flex items-center gap-3">{item.images[0] ? <img src={item.images[0].image_url} alt="" className="h-10 w-10 rounded object-cover" /> : <div className="h-10 w-10 rounded bg-slate-100" />}<Link to={`/products/${item.id}`} className="font-medium text-blue-700">{item.name}</Link></div></td><td className="px-4 py-3 font-mono">{item.sku}</td><td className="px-4 py-3">{item.category_name ?? "—"}</td><td className="px-4 py-3">{[item.material, item.dimension_text].filter(Boolean).join(" / ") || "—"}</td><td className="px-4 py-3">{item.moq ?? "—"} {item.unit}</td><td className="px-4 py-3">{item.reference_price ? `${item.currency_code} ${item.reference_price}` : "—"}</td><td className="px-4 py-3"><span className={`rounded-full px-2 py-1 text-xs ${item.is_active ? "bg-emerald-100 text-emerald-700" : "bg-slate-200 text-slate-600"}`}>{item.is_active ? "已启用" : "已停用"}</span></td><td className="px-4 py-3"><div className="flex items-center gap-3">{editable && <button type="button" onClick={() => void toggleActive(item.id, item.is_active)} className="text-blue-700">{item.is_active ? "停用" : "启用"}</button>}{canDelete && <button type="button" disabled={deletingProductId === item.id} onClick={() => void removeProduct(item.id, item.name)} className="text-rose-600 disabled:opacity-50">{deletingProductId === item.id ? "删除中..." : "删除"}</button>}</div></td></tr>)}{data?.items.length === 0 && <tr><td colSpan={8} className="px-4 py-10 text-center text-slate-500">暂无产品。</td></tr>}</tbody></table></div>
    <div className="mt-4 flex justify-between text-sm"><span className="text-slate-500">共 {data?.total ?? 0} 个产品</span><div className="flex gap-2"><button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} className="rounded border px-3 py-1 disabled:opacity-40">上一页</button><button disabled={!data || offset + PAGE_SIZE >= data.total} onClick={() => setOffset(offset + PAGE_SIZE)} className="rounded border px-3 py-1 disabled:opacity-40">下一页</button></div></div>
  </>;
}
