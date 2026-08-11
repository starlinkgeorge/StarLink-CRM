import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { deleteProduct, getProduct, getProductCategories, updateProduct, type ProductImagePayload, type ProductPayload } from "../services/crm";
import { useAuth } from "../store/auth";
import type { Product, ProductCategory } from "../types";

type ProductForm = ProductPayload & { images: ProductImagePayload[] };

function toForm(product: Product): ProductForm {
  return {
    sku: product.sku, name: product.name, category_id: product.category_id ?? undefined,
    material: product.material ?? "", dimension_text: product.dimension_text ?? "",
    length_mm: product.length_mm ?? "", width_mm: product.width_mm ?? "", height_mm: product.height_mm ?? "",
    weight_kg: product.weight_kg ?? "", unit: product.unit, moq: product.moq ?? undefined,
    reference_price: product.reference_price ?? "", currency_code: product.currency_code,
    description: product.description ?? "", is_active: product.is_active,
    images: product.images.map(({ image_url, is_primary, sort_order }) => ({ image_url, is_primary, sort_order })),
  };
}

export function ProductDetailPage() {
  const { id } = useParams(); const { user } = useAuth();
  const editable = user?.role !== "Viewer";
  const canDelete = user?.role === "Admin";
  const navigate = useNavigate();
  const [product, setProduct] = useState<Product | null>(null);
  const [form, setForm] = useState<ProductForm | null>(null);
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [error, setError] = useState(""); const [saving, setSaving] = useState(false); const [deleting, setDeleting] = useState(false);
  const load = useCallback(async () => { if (!id) return; try { const item = await getProduct(id); setProduct(item); setForm(toForm(item)); setError(""); } catch { setError("无法加载产品详情。"); } }, [id]);
  useEffect(() => { void load(); void getProductCategories().then(setCategories).catch(() => undefined); }, [load]);
  function updateImage(index: number, changes: Partial<ProductImagePayload>) { if (!form) return; setForm({ ...form, images: form.images.map((image, current) => current === index ? { ...image, ...changes } : changes.is_primary ? { ...image, is_primary: false } : image) }); }
  async function save(event: FormEvent) { event.preventDefault(); if (!product || !form) return; setSaving(true); try { const updated = await updateProduct(product.id, form); setProduct(updated); setForm(toForm(updated)); setError(""); } catch { setError("保存失败，请检查 SKU、分类、图片地址和数值格式。"); } finally { setSaving(false); } }
  async function removeProduct() { if (!product || !window.confirm(`确定要删除产品“${product.name}”吗？此操作不可恢复。`)) return; setDeleting(true); try { await deleteProduct(product.id); navigate("/products"); } catch { setError("无法删除产品。如果它已关联商机，请先从商机中移除该产品。"); } finally { setDeleting(false); } }
  if (!product || !form) return <p className="text-slate-500">{error || "加载中…"}</p>;
  const inputClass = "rounded-lg border px-3 py-2 disabled:bg-slate-50";
  return <><Link to="/products" className="text-sm text-blue-700">← 返回产品库</Link><div className="mt-4 flex flex-wrap items-start justify-between gap-3"><div><p className="font-mono text-sm text-slate-500">{product.sku}</p><h2 className="text-3xl font-bold">{product.name}</h2></div><span className={`rounded-full px-3 py-1 text-sm ${product.is_active ? "bg-emerald-100 text-emerald-700" : "bg-slate-200 text-slate-600"}`}>{product.is_active ? "已启用" : "已停用"}</span></div>{error && <p className="mt-4 text-sm text-rose-600">{error}</p>}
    {canDelete && <div className="flex justify-end"><button type="button" disabled={deleting} onClick={() => void removeProduct()} className="rounded-lg border border-rose-300 px-4 py-2 text-sm font-semibold text-rose-700 disabled:opacity-50">{deleting ? "删除中..." : "删除产品"}</button></div>}
    <form onSubmit={save} className="mt-6 space-y-5"><section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><h3 className="font-bold">产品资料</h3><div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4"><label className="grid gap-1 text-sm">SKU<input disabled={!editable} required value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value })} className={inputClass} /></label><label className="grid gap-1 text-sm">产品名称<input disabled={!editable} required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={inputClass} /></label><label className="grid gap-1 text-sm">分类<select disabled={!editable} value={form.category_id ?? ""} onChange={(e) => setForm({ ...form, category_id: e.target.value ? Number(e.target.value) : undefined })} className={inputClass}><option value="">未分类</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="grid gap-1 text-sm">材质<input disabled={!editable} value={form.material} onChange={(e) => setForm({ ...form, material: e.target.value })} className={inputClass} /></label><label className="grid gap-1 text-sm">尺寸说明<input disabled={!editable} value={form.dimension_text} onChange={(e) => setForm({ ...form, dimension_text: e.target.value })} className={inputClass} /></label>{(["length_mm", "width_mm", "height_mm", "weight_kg"] as const).map((field) => <label key={field} className="grid gap-1 text-sm">{{ length_mm: "长度 mm", width_mm: "宽度 mm", height_mm: "高度 mm", weight_kg: "重量 kg" }[field]}<input disabled={!editable} type="number" min="0" step="0.001" value={form[field]} onChange={(e) => setForm({ ...form, [field]: e.target.value })} className={inputClass} /></label>)}<label className="grid gap-1 text-sm">单位<input disabled={!editable} value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} className={inputClass} /></label><label className="grid gap-1 text-sm">MOQ<input disabled={!editable} type="number" min="1" value={form.moq ?? ""} onChange={(e) => setForm({ ...form, moq: e.target.value ? Number(e.target.value) : undefined })} className={inputClass} /></label><label className="grid gap-1 text-sm">参考价格<input disabled={!editable} type="number" min="0" step="0.01" value={form.reference_price} onChange={(e) => setForm({ ...form, reference_price: e.target.value })} className={inputClass} /></label><label className="grid gap-1 text-sm">币种<input disabled={!editable} maxLength={3} value={form.currency_code} onChange={(e) => setForm({ ...form, currency_code: e.target.value.toUpperCase() })} className={inputClass} /></label><label className="flex items-center gap-2 text-sm"><input disabled={!editable} type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />启用产品</label><label className="grid gap-1 text-sm md:col-span-2 xl:col-span-4">描述<textarea disabled={!editable} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className={`${inputClass} min-h-28`} /></label></div></section>
      <section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><div className="flex items-center justify-between"><h3 className="font-bold">产品图片</h3>{editable && <button type="button" onClick={() => setForm({ ...form, images: [...form.images, { image_url: "", is_primary: form.images.length === 0, sort_order: form.images.length }] })} className="text-sm font-semibold text-blue-700">+ 添加图片地址</button>}</div><div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">{form.images.map((image, index) => <div key={index} className="rounded-lg border p-3">{image.image_url && <img src={image.image_url} alt="产品" className="mb-3 h-40 w-full rounded object-cover" />}<input disabled={!editable} value={image.image_url} onChange={(e) => updateImage(index, { image_url: e.target.value })} placeholder="https://..." className="w-full rounded border px-3 py-2 text-sm" /><div className="mt-2 flex items-center justify-between"><label className="flex items-center gap-2 text-sm"><input disabled={!editable} type="radio" name="primary" checked={Boolean(image.is_primary)} onChange={() => updateImage(index, { is_primary: true })} />主图</label>{editable && <button type="button" onClick={() => setForm({ ...form, images: form.images.filter((_, current) => current !== index) })} className="text-sm text-rose-600">删除</button>}</div></div>)}{form.images.length === 0 && <p className="text-sm text-slate-500">暂无图片地址。</p>}</div></section>
      {editable && <button disabled={saving} className="rounded-lg bg-blue-600 px-5 py-2 font-semibold text-white disabled:opacity-60">{saving ? "保存中…" : "保存修改"}</button>}
    </form></>;
}
