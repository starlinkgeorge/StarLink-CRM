import axios from "axios";
import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { createCustomer, getCustomerCategories, type CustomerCreatePayload } from "../services/crm";
import type { CustomerCategory } from "../types";

const customerTypes = [
  "Kindergarten",
  "School",
  "Distributor",
  "Wholesaler",
  "Retailer",
  "Project Contractor",
  "Other",
];

const sources = ["Alibaba", "Website", "Facebook", "LinkedIn", "Other"];

const salesStages = [
  ["Lead", "新线索"],
  ["Contacted", "已联系"],
  ["Quotation", "报价中"],
  ["Negotiation", "谈判中"],
  ["Won", "已成交"],
  ["Lost", "已流失"],
] as const;

const initialForm: CustomerCreatePayload = {
  company_name: "",
  contact_name: "",
  country: "",
  email: "",
  phone: "",
  whatsapp: "",
  website: "",
  customer_type: "",
  source: "",
  interested_product: "",
  level: "C",
  sales_stage: "Lead",
};

export function NewCustomerPage() {
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<CustomerCreatePayload>(initialForm);
  const [categories, setCategories] = useState<CustomerCategory[]>([]);

  useEffect(() => {
    getCustomerCategories(true).then(setCategories).catch(() => undefined);
  }, []);

  const field = (key: keyof CustomerCreatePayload) => ({
    value: form[key] ?? "",
    onChange: (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm({ ...form, [key]: event.target.value } as CustomerCreatePayload),
  });

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const customer = await createCustomer(form);
      navigate(`/customers/${customer.id}`);
    } catch (err) {
      setError(
        axios.isAxiosError(err)
          ? (err.response?.data?.detail ?? "无法创建客户。")
          : "无法创建客户。",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <h2 className="text-3xl font-bold">新增客户</h2>
      <p className="mt-1 text-sm text-slate-500">
        建立客户档案并记录客户类型、来源、感兴趣产品和当前销售阶段。
      </p>
      <form
        onSubmit={submit}
        className="mt-6 max-w-3xl rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-200"
      >
        <div className="grid gap-4 md:grid-cols-2">
          <label className="text-sm font-medium">
            公司名称
            <input required {...field("company_name")} className="mt-1 w-full rounded border px-3 py-2" />
          </label>
          <label className="text-sm font-medium">
            客户类型
            <select {...field("customer_type")} className="mt-1 w-full rounded border px-3 py-2">
              <option value="">请选择</option>
              {customerTypes.map((type) => <option key={type} value={type}>{type}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium">
            客户分类
            <select value={form.category_id ?? ""} onChange={(event) => setForm({ ...form, category_id: event.target.value ? Number(event.target.value) : undefined })} className="mt-1 w-full rounded border px-3 py-2">
              <option value="">请选择分类</option>
              {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium">
            主联系人
            <input {...field("contact_name")} className="mt-1 w-full rounded border px-3 py-2" />
          </label>
          <label className="text-sm font-medium">
            国家/地区
            <input {...field("country")} className="mt-1 w-full rounded border px-3 py-2" />
          </label>
          <label className="text-sm font-medium">
            邮箱
            <input type="email" {...field("email")} className="mt-1 w-full rounded border px-3 py-2" />
          </label>
          <label className="text-sm font-medium">
            电话
            <input {...field("phone")} className="mt-1 w-full rounded border px-3 py-2" />
          </label>
          <label className="text-sm font-medium">
            WhatsApp
            <input {...field("whatsapp")} className="mt-1 w-full rounded border px-3 py-2" />
          </label>
          <label className="text-sm font-medium">
            网站
            <input {...field("website")} className="mt-1 w-full rounded border px-3 py-2" />
          </label>
          <label className="text-sm font-medium">
            客户来源
            <select {...field("source")} className="mt-1 w-full rounded border px-3 py-2">
              <option value="">请选择</option>
              {sources.map((source) => <option key={source} value={source}>{source}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium">
            感兴趣产品
            <input
              {...field("interested_product")}
              placeholder="例如：Montessori shelves"
              className="mt-1 w-full rounded border px-3 py-2"
            />
          </label>
          <label className="text-sm font-medium">
            客户等级
            <select {...field("level")} className="mt-1 w-full rounded border px-3 py-2">
              <option>A</option><option>B</option><option>C</option>
            </select>
          </label>
          <label className="text-sm font-medium">
            客户评分（0-100）
            <input type="number" min="0" max="100" value={form.customer_score ?? ""} onChange={(event) => setForm({ ...form, customer_score: event.target.value === "" ? undefined : Number(event.target.value) })} className="mt-1 w-full rounded border px-3 py-2" />
          </label>
          <label className="text-sm font-medium">
            销售阶段
            <select {...field("sales_stage")} className="mt-1 w-full rounded border px-3 py-2">
              {salesStages.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
        </div>
        {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}
        <div className="mt-6 flex gap-3">
          <button disabled={saving} className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white disabled:opacity-60">
            {saving ? "保存中…" : "创建客户"}
          </button>
          <button type="button" onClick={() => navigate(-1)} className="rounded-lg border px-4 py-2">取消</button>
        </div>
      </form>
    </>
  );
}
