import axios from "axios";
import { useState, type ChangeEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { createCustomer, type CustomerCreatePayload } from "../services/crm";
import { customerArchiveOptions } from "../constants/customerArchiveOptions";

const initialForm: CustomerCreatePayload = { company_name: "" };
type FormKey = keyof CustomerCreatePayload;

export function NewCustomerPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState<CustomerCreatePayload>(initialForm);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const text = (key: FormKey) => ({
    value: typeof form[key] === "string" ? form[key] : "",
    onChange: (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setForm((current) => ({ ...current, [key]: event.target.value })),
  });
  const number = (key: FormKey) => ({
    value: typeof form[key] === "number" ? form[key] : "",
    onChange: (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm((current) => ({ ...current, [key]: event.target.value === "" ? undefined : Number(event.target.value) })),
  });

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true); setError("");
    try {
      const optionalText = (value: string | undefined) => value?.trim() || undefined;
      const payload: CustomerCreatePayload = {
        ...form, company_name: form.company_name.trim(),
        contact_name: optionalText(form.contact_name), country: optionalText(form.country), email: optionalText(form.email),
        phone: optionalText(form.phone), whatsapp: optionalText(form.whatsapp), customer_acquired_at: optionalText(form.customer_acquired_at),
        position: optionalText(form.position), notes: optionalText(form.notes), customer_type: optionalText(form.customer_type),
        source: optionalText(form.source), interested_product: optionalText(form.interested_product), followup_stage: optionalText(form.followup_stage),
        automatic_stage_judgement: optionalText(form.automatic_stage_judgement), latest_followup_date: optionalText(form.latest_followup_date),
        response_status: optionalText(form.response_status), followup_requirement: optionalText(form.followup_requirement),
      };
      const customer = await createCustomer(payload);
      navigate(`/customers/${customer.id}`);
    } catch (err) {
      setError(axios.isAxiosError(err) ? String(err.response?.data?.detail ?? "无法创建客户。") : "无法创建客户。");
    } finally { setSaving(false); }
  }

  return <>
    <h2 className="text-3xl font-bold">新增客户</h2>
    <p className="mt-1 text-sm text-slate-500">字段与“客户档案表”一致；未填写的字段将保持为空。</p>
    <form onSubmit={submit} className="mt-6 max-w-6xl rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <label className="text-sm font-medium">获得客户时间<input type="date" {...text("customer_acquired_at")} className="mt-1 w-full rounded border px-3 py-2" /></label>
        <label className="text-sm font-medium">来源<select {...text("source")} className="mt-1 w-full rounded border px-3 py-2"><option value="" />{customerArchiveOptions.source.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
        <label className="text-sm font-medium">客户名<input {...text("contact_name")} className="mt-1 w-full rounded border px-3 py-2" /></label>
        <label className="text-sm font-medium">公司名<input required {...text("company_name")} className="mt-1 w-full rounded border px-3 py-2" /></label>
        <label className="text-sm font-medium">职位<input {...text("position")} className="mt-1 w-full rounded border px-3 py-2" /></label>
        <label className="text-sm font-medium">国家<input {...text("country")} className="mt-1 w-full rounded border px-3 py-2" /></label>
        <label className="text-sm font-medium">客户类型<select {...text("customer_type")} className="mt-1 w-full rounded border px-3 py-2"><option value="" />{customerArchiveOptions.customerType.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
        <label className="text-sm font-medium">兴趣产品<select {...text("interested_product")} className="mt-1 w-full rounded border px-3 py-2"><option value="" />{customerArchiveOptions.interestedProduct.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
        <label className="text-sm font-medium">WhatsApp<input {...text("whatsapp")} className="mt-1 w-full rounded border px-3 py-2" /></label>
        <label className="text-sm font-medium">邮箱<input type="email" {...text("email")} className="mt-1 w-full rounded border px-3 py-2" /></label>
        <label className="text-sm font-medium">电话<input {...text("phone")} className="mt-1 w-full rounded border px-3 py-2" /></label>
        <label className="text-sm font-medium">客户等级<select {...number("customer_level_value")} className="mt-1 w-full rounded border px-3 py-2"><option value="" />{customerArchiveOptions.customerLevelValue.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
        <label className="text-sm font-medium">客户体量<select {...number("customer_size")} className="mt-1 w-full rounded border px-3 py-2"><option value="" />{customerArchiveOptions.customerSize.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
        <label className="text-sm font-medium">客户总分<input type="number" min="0" {...number("customer_total_score")} className="mt-1 w-full rounded border px-3 py-2" /></label>
        <label className="text-sm font-medium">跟进阶段<select {...text("followup_stage")} className="mt-1 w-full rounded border px-3 py-2"><option value="" />{customerArchiveOptions.followupStage.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
        <label className="text-sm font-medium">自动阶段判断<input {...text("automatic_stage_judgement")} className="mt-1 w-full rounded border px-3 py-2" /></label>
        <label className="text-sm font-medium">最近跟进日期<input type="date" {...text("latest_followup_date")} className="mt-1 w-full rounded border px-3 py-2" /></label>
        <label className="text-sm font-medium">是否回复<select {...text("response_status")} className="mt-1 w-full rounded border px-3 py-2"><option value="" />{customerArchiveOptions.responseStatus.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
        <label className="text-sm font-medium">是否需要跟进<input {...text("followup_requirement")} className="mt-1 w-full rounded border px-3 py-2" /></label>
        <label className="text-sm font-medium md:col-span-2 xl:col-span-3">备注<textarea {...text("notes")} className="mt-1 min-h-28 w-full rounded border px-3 py-2" /></label>
      </div>
      {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}
      <div className="mt-6 flex gap-3"><button disabled={saving} className="rounded bg-blue-600 px-4 py-2 font-semibold text-white disabled:opacity-60">{saving ? "保存中…" : "创建客户"}</button><button type="button" onClick={() => navigate(-1)} className="rounded border px-4 py-2">取消</button></div>
    </form>
  </>;
}
