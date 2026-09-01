import { useEffect, useState, type ChangeEvent, type FormEvent, type ReactNode } from "react";

import { updateCustomer, type CustomerCreatePayload } from "../services/crm";
import { customerArchiveOptions } from "../constants/customerArchiveOptions";
import type { CustomerCenter } from "../types";

type Props = {
  customer: CustomerCenter;
  editable: boolean;
  onSaved: () => Promise<void> | void;
  editRequest?: number;
  showEditAction?: boolean;
};

type FieldKey = keyof CustomerCreatePayload;

function emptyToUndefined(value: string) {
  const trimmed = value.trim();
  return trimmed || undefined;
}

function dateInput(value: string | null) {
  return value ? value.slice(0, 10) : "";
}

function editableFollowupStage(value: string | null): string | undefined {
  return customerArchiveOptions.followupStage.includes(value as never) ? value ?? undefined : undefined;
}

function initialForm(customer: CustomerCenter): CustomerCreatePayload {
  return {
    company_name: customer.company_name,
    contact_name: customer.contact_name ?? undefined,
    country: customer.country ?? undefined,
    email: customer.email ?? undefined,
    phone: customer.phone ?? undefined,
    whatsapp: customer.whatsapp ?? undefined,
    customer_acquired_at: dateInput(customer.customer_acquired_at),
    position: customer.position ?? undefined,
    notes: customer.notes ?? undefined,
    customer_type: customer.customer_type ?? undefined,
    source: customer.source ?? undefined,
    interested_product: customer.interested_product ?? undefined,
    customer_level_value: customer.customer_level_value ?? undefined,
    customer_size: customer.customer_size ?? undefined,
    customer_total_score: customer.customer_total_score ?? undefined,
    followup_stage: editableFollowupStage(customer.followup_stage),
    latest_followup_date: dateInput(customer.latest_followup_date),
  };
}

function Value({ value }: { value: string | number | null | undefined }) {
  return <span className="whitespace-pre-wrap text-slate-800">{value === null || value === undefined || value === "" ? "—" : value}</span>;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
    <h3 className="text-sm font-bold text-slate-900">{title}</h3>
    {children}
  </section>;
}

export function CustomerArchiveProfile({ customer, editable, onSaved, editRequest = 0, showEditAction = true }: Props) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<CustomerCreatePayload>(() => initialForm(customer));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (editRequest > 0 && editable) setEditing(true);
  }, [editRequest, editable]);

  const updateText = (key: FieldKey) => (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    setForm((current) => ({ ...current, [key]: event.target.value }));
  };
  const updateNumber = (key: FieldKey) => (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const value = event.target.value;
    setForm((current) => ({ ...current, [key]: value === "" ? undefined : Number(value) }));
  };

  function cancel() {
    setForm(initialForm(customer));
    setError("");
    setEditing(false);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!form.company_name?.trim()) {
      setError("公司名不能为空。");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const normalized: CustomerCreatePayload = {
        ...form,
        company_name: form.company_name.trim(),
      };
      for (const key of ["contact_name", "country", "email", "phone", "whatsapp", "position", "notes", "customer_type", "source", "interested_product", "followup_stage", "customer_acquired_at", "latest_followup_date"] as FieldKey[]) {
        const value = normalized[key];
        if (typeof value === "string") normalized[key] = emptyToUndefined(value) as never;
      }
      await updateCustomer(customer.id, normalized);
      await onSaved();
      setEditing(false);
    } catch {
      setError("保存客户档案失败，请检查必填项和输入格式。");
    } finally {
      setSaving(false);
    }
  }

  if (editing) {
    return <form onSubmit={submit} className="space-y-5 rounded-xl border border-blue-200 bg-blue-50/30 p-5">
      <div className="flex items-center justify-between gap-3"><h3 className="text-lg font-bold">编辑客户档案</h3><span className="text-xs text-slate-500">字段与“客户档案表”一致</span></div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <label className="text-sm font-medium">获得客户时间<input type="date" value={form.customer_acquired_at ?? ""} onChange={updateText("customer_acquired_at")} className="mt-1 w-full rounded border px-3 py-2" /></label>
        <label className="text-sm font-medium">来源<select value={form.source ?? ""} onChange={updateText("source")} className="mt-1 w-full rounded border px-3 py-2"><option value="" />{customerArchiveOptions.source.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
        <label className="text-sm font-medium">客户名<input value={form.contact_name ?? ""} onChange={updateText("contact_name")} className="mt-1 w-full rounded border px-3 py-2" /></label>
        <label className="text-sm font-medium">公司名<input required value={form.company_name} onChange={updateText("company_name")} className="mt-1 w-full rounded border px-3 py-2" /></label>
        <label className="text-sm font-medium">职位<input value={form.position ?? ""} onChange={updateText("position")} className="mt-1 w-full rounded border px-3 py-2" /></label>
        <label className="text-sm font-medium">国家<input value={form.country ?? ""} onChange={updateText("country")} className="mt-1 w-full rounded border px-3 py-2" /></label>
        <label className="text-sm font-medium">客户类型<select value={form.customer_type ?? ""} onChange={updateText("customer_type")} className="mt-1 w-full rounded border px-3 py-2"><option value="" />{customerArchiveOptions.customerType.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
        <label className="text-sm font-medium">兴趣产品<select value={form.interested_product ?? ""} onChange={updateText("interested_product")} className="mt-1 w-full rounded border px-3 py-2"><option value="" />{customerArchiveOptions.interestedProduct.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
        <label className="text-sm font-medium">WhatsApp<input value={form.whatsapp ?? ""} onChange={updateText("whatsapp")} className="mt-1 w-full rounded border px-3 py-2" /></label>
        <label className="text-sm font-medium">邮箱<input type="email" value={form.email ?? ""} onChange={updateText("email")} className="mt-1 w-full rounded border px-3 py-2" /></label>
        <label className="text-sm font-medium">电话<input value={form.phone ?? ""} onChange={updateText("phone")} className="mt-1 w-full rounded border px-3 py-2" /></label>
        <label className="text-sm font-medium">客户等级<select value={form.customer_level_value ?? ""} onChange={updateNumber("customer_level_value")} className="mt-1 w-full rounded border px-3 py-2"><option value="" />{customerArchiveOptions.customerLevelValue.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
        <label className="text-sm font-medium">客户体量<select value={form.customer_size ?? ""} onChange={updateNumber("customer_size")} className="mt-1 w-full rounded border px-3 py-2"><option value="" />{customerArchiveOptions.customerSize.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
        <label className="text-sm font-medium">客户总分<input type="number" min="0" value={form.customer_total_score ?? ""} onChange={updateNumber("customer_total_score")} className="mt-1 w-full rounded border px-3 py-2" /></label>
        <label className="text-sm font-medium">跟进阶段<select value={form.followup_stage ?? ""} onChange={updateText("followup_stage")} className="mt-1 w-full rounded border px-3 py-2"><option value="" />{customerArchiveOptions.followupStage.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
        <label className="text-sm font-medium">最近跟进日期<input type="date" value={form.latest_followup_date ?? ""} onChange={updateText("latest_followup_date")} className="mt-1 w-full rounded border px-3 py-2" /></label>
        <label className="text-sm font-medium md:col-span-2 xl:col-span-3">备注<textarea value={form.notes ?? ""} onChange={updateText("notes")} className="mt-1 min-h-28 w-full rounded border px-3 py-2" /></label>
      </div>
      {error && <p className="text-sm text-rose-600">{error}</p>}
      <div className="flex gap-3"><button disabled={saving} className="rounded bg-blue-600 px-4 py-2 font-semibold text-white disabled:opacity-60">{saving ? "保存中…" : "保存档案"}</button><button type="button" onClick={cancel} className="rounded border px-4 py-2">取消</button></div>
    </form>;
  }

  return <div className="space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-bold">客户档案</h2><p className="text-sm text-slate-500">核心资料与联系方式</p></div>{showEditAction && editable && <button type="button" onClick={() => setEditing(true)} className="rounded border border-blue-600 px-3 py-1.5 text-sm font-semibold text-blue-700">编辑客户档案</button>}</div>
    <div className="grid gap-3 xl:grid-cols-3">
      <Section title="基础信息"><dl className="mt-3 grid gap-x-4 gap-y-2 text-sm sm:grid-cols-2"><dt>获得客户时间</dt><dd><Value value={dateInput(customer.customer_acquired_at)} /></dd><dt>来源</dt><dd><Value value={customer.source} /></dd><dt>来源平台</dt><dd><Value value={customer.source_platform} /></dd><dt>客户名</dt><dd><Value value={customer.contact_name} /></dd><dt>职位</dt><dd><Value value={customer.position} /></dd><dt>国家</dt><dd><Value value={customer.country} /></dd></dl></Section>
      <Section title="联系方式"><dl className="mt-3 grid gap-x-4 gap-y-2 text-sm sm:grid-cols-2"><dt>WhatsApp</dt><dd><Value value={customer.whatsapp} /></dd><dt>邮箱</dt><dd className="break-all"><Value value={customer.email} /></dd><dt>电话</dt><dd><Value value={customer.phone} /></dd><dt>网站</dt><dd className="break-all"><Value value={customer.website} /></dd></dl></Section>
      <Section title="业务信息"><dl className="mt-3 grid gap-x-4 gap-y-2 text-sm sm:grid-cols-2"><dt>客户分类</dt><dd><Value value={customer.category?.name} /></dd><dt>客户类型</dt><dd><Value value={customer.customer_type} /></dd><dt>兴趣产品</dt><dd><Value value={customer.interested_product} /></dd><dt>客户等级</dt><dd><Value value={customer.customer_level_value} /></dd><dt>客户体量</dt><dd><Value value={customer.customer_size} /></dd><dt>客户总分</dt><dd><Value value={customer.customer_total_score} /></dd><dt>跟进阶段</dt><dd><Value value={customer.followup_stage} /></dd><dt>最近跟进</dt><dd><Value value={dateInput(customer.latest_followup_date)} /></dd></dl></Section>
      <div className="xl:col-span-3"><Section title="备注"><p className="mt-2 whitespace-pre-wrap text-sm"><Value value={customer.notes} /></p></Section></div>
    </div>
  </div>;
}
