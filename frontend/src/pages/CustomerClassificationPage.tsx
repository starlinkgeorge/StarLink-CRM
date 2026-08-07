import axios from "axios";
import { useEffect, useState, type FormEvent } from "react";

import { createCustomerCategory, createTag, getCustomerCategories, getTags, updateCustomerCategory, updateTag } from "../services/crm";
import { useAuth } from "../store/auth";
import type { CustomerCategory, Tag } from "../types";

export function CustomerClassificationPage() {
  const { user } = useAuth();
  const [categories, setCategories] = useState<CustomerCategory[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [categoryName, setCategoryName] = useState("");
  const [categoryColor, setCategoryColor] = useState("#2563eb");
  const [tagName, setTagName] = useState("");
  const [tagColor, setTagColor] = useState("#2563eb");
  const [error, setError] = useState("");
  const editable = user?.role !== "Viewer";

  async function load() {
    const [categoryData, tagData] = await Promise.all([getCustomerCategories(), getTags()]);
    setCategories(categoryData);
    setTags(tagData);
  }

  useEffect(() => { load().catch(() => setError("无法加载客户分类和标签。")); }, []);

  async function submitCategory(event: FormEvent) {
    event.preventDefault();
    try { await createCustomerCategory({ name: categoryName, color: categoryColor }); setCategoryName(""); await load(); }
    catch (err) { setError(axios.isAxiosError(err) ? err.response?.data?.detail ?? "无法创建客户分类。" : "无法创建客户分类。"); }
  }

  async function submitTag(event: FormEvent) {
    event.preventDefault();
    try { await createTag(tagName.trim(), { color: tagColor }); setTagName(""); await load(); }
    catch (err) { setError(axios.isAxiosError(err) ? err.response?.data?.detail ?? "无法创建客户标签。" : "无法创建客户标签。"); }
  }

  async function toggleCategory(category: CustomerCategory) { await updateCustomerCategory(category.id, { is_active: !category.is_active }); await load(); }
  async function toggleTag(tag: Tag) { await updateTag(tag.id, { is_active: !tag.is_active }); await load(); }

  return (
    <>
      <p className="text-sm text-slate-500">V4 客户管理</p><h2 className="mt-1 text-3xl font-bold">客户分类与标签</h2>
      {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}
      <div className="mt-6 grid gap-5 lg:grid-cols-2">
        <section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <h3 className="font-bold">客户分类</h3>
          {editable && <form onSubmit={submitCategory} className="mt-4 flex flex-wrap gap-2"><input required maxLength={80} value={categoryName} onChange={(event) => setCategoryName(event.target.value)} placeholder="例如：学校客户" className="min-w-48 flex-1 rounded border px-3 py-2" /><input type="color" value={categoryColor} onChange={(event) => setCategoryColor(event.target.value)} className="h-10 w-12 rounded border p-1" /><button className="rounded bg-blue-600 px-3 py-2 text-sm font-semibold text-white">新增分类</button></form>}
          <div className="mt-4 space-y-2">{categories.map((category) => <div key={category.id} className="flex items-center justify-between rounded-lg bg-slate-50 p-3 text-sm"><span className="flex items-center gap-2"><i className="h-3 w-3 rounded-full" style={{ backgroundColor: category.color }} />{category.name}</span><span className="flex items-center gap-2 text-slate-500">{category.is_active ? "启用" : "停用"}{editable && <button onClick={() => void toggleCategory(category)} className="text-blue-700 underline">{category.is_active ? "停用" : "启用"}</button>}</span></div>)}{!categories.length && <p className="text-sm text-slate-500">暂无客户分类。</p>}</div>
        </section>
        <section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <h3 className="font-bold">客户标签</h3>
          {editable && <form onSubmit={submitTag} className="mt-4 flex flex-wrap gap-2"><input required maxLength={80} value={tagName} onChange={(event) => setTagName(event.target.value)} placeholder="例如：高意向" className="min-w-48 flex-1 rounded border px-3 py-2" /><input type="color" value={tagColor} onChange={(event) => setTagColor(event.target.value)} className="h-10 w-12 rounded border p-1" /><button className="rounded bg-blue-600 px-3 py-2 text-sm font-semibold text-white">新增标签</button></form>}
          <div className="mt-4 flex flex-wrap gap-2">{tags.map((tag) => <span key={tag.id} className={`rounded-full px-3 py-1 text-sm ${tag.is_active ? "text-white" : "bg-slate-200 text-slate-500"}`} style={tag.is_active ? { backgroundColor: tag.color } : undefined}>{tag.name}{editable && <button onClick={() => void toggleTag(tag)} className="ml-2 underline">{tag.is_active ? "停用" : "启用"}</button>}</span>)}{!tags.length && <p className="text-sm text-slate-500">暂无客户标签。</p>}</div>
        </section>
      </div>
    </>
  );
}
