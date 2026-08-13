import api from "./api";
import type { AlibabaInquiryResult, AlibabaIntegrationStatus, CalculatedFollowupReminderStatus, Customer, CustomerActivity, CustomerCategory, CustomerCenter, CustomerDetail, CustomerFollowupReminderPage, CustomerPage, CustomerScoreHistory, DashboardStats, FollowUp, FollowUpAttachment, Inquiry, InquiryConversion, InquiryPage, InquiryStatus, Lead, LeadConversion, LeadDetail, LeadPage, LeadStatus, OpportunityDealPipeline, OpportunityDealStage, OpportunityDetail, OpportunityListItem, OpportunityPage, OpportunityPipeline, OpportunitySalesStage, OpportunityStage, Product, ProductCategory, ProductPage, QuotationDetail, QuotationPage, QuotationStatus, Tag } from "../types";

export type CustomerCreatePayload = {
  company_name: string; contact_name?: string; country?: string; email?: string; phone?: string;
  whatsapp?: string; website?: string; customer_type?: string; source?: string;
  source_platform?: string; original_inquiry?: string;
  customer_acquired_at?: string; position?: string; notes?: string;
  interested_product?: string; level?: Customer["level"]; status?: Customer["status"];
  customer_level_value?: number; customer_size?: number; customer_total_score?: number;
  followup_stage?: string; automatic_stage_judgement?: string; latest_followup_date?: string;
  sales_stage?: Customer["sales_stage"]; category_id?: number; customer_score?: number;
};

export const getDashboardStats = async () => (await api.get<DashboardStats>("/dashboard/stats")).data;
export const getCustomerFollowupReminders = async (status?: CalculatedFollowupReminderStatus) => (
  await api.get<CustomerFollowupReminderPage>("/followup-reminders", { params: status ? { status } : undefined })
).data;
export type CustomerFilters = {
  limit: number; offset: number; q?: string; status?: string; level?: string; country?: string;
  customer_type?: string; source?: string; interested_product?: string; sales_stage?: string;
  followup_stage?: string;
  customer_level_value?: number;
  customer_name?: string; company_name?: string; position?: string; whatsapp?: string;
  email?: string; phone?: string; notes?: string;
  customer_acquired_from?: string; customer_acquired_to?: string;
  customer_size?: number; customer_total_score_min?: number; customer_total_score_max?: number;
  automatic_stage_judgement?: string; latest_followup_from?: string; latest_followup_to?: string;
  tag_id?: number; category_id?: number; score_min?: number; score_max?: number;
};
export const getCustomers = async (params: CustomerFilters) => (await api.get<CustomerPage>("/customers", { params })).data;
export const downloadCustomerArchive = async () => (await api.get<Blob>("/customers/export", { responseType: "blob" })).data;
export const getCustomer = async (id: string) => (await api.get<CustomerDetail>(`/customers/${id}`)).data;
export const getCustomerCenter = async (id: string) => (await api.get<CustomerCenter>(`/customers/${id}/center`)).data;
export const getCustomerTimeline = async (id: string) => (await api.get<CustomerActivity[]>(`/customers/${id}/timeline`)).data;
export const createCustomer = async (data: CustomerCreatePayload) => (await api.post<Customer>("/customers", data)).data;
export const updateCustomer = async (id: number, data: Partial<CustomerCreatePayload>) => (await api.put<Customer>(`/customers/${id}`, data)).data;
export const deleteCustomer = async (id: number) => { await api.delete(`/customers/${id}`); };
export type FollowUpPayload = {
  customer_id: number; user_id?: number; opportunity_id?: number | null; type: FollowUp["type"];
  followup_date?: string; content: string; next_followup_date?: string | null;
};
export type FollowUpUpdatePayload = {
  opportunity_id?: number | null; type?: FollowUp["type"]; followup_date?: string;
  content?: string; next_followup_date?: string | null;
};
export const createFollowup = async (data: FollowUpPayload) => (await api.post<FollowUp>("/followups", data)).data;
export const updateFollowup = async (id: number, data: FollowUpUpdatePayload) => (await api.put<FollowUp>(`/followups/${id}`, data)).data;
export const deleteFollowup = async (id: number) => { await api.delete(`/followups/${id}`); };
export const uploadFollowupAttachment = async (followupId: number, file: File) => {
  const form = new FormData(); form.append("file", file);
  return (await api.post<FollowUpAttachment>(`/followups/${followupId}/attachments`, form)).data;
};
export const deleteFollowupAttachment = async (followupId: number, attachmentId: number) => { await api.delete(`/followups/${followupId}/attachments/${attachmentId}`); };
export const downloadFollowupAttachment = async (followupId: number, attachmentId: number) => (await api.get<Blob>(`/followups/${followupId}/attachments/${attachmentId}`, { responseType: "blob" })).data;
export const getTags = async () => (await api.get<Tag[]>("/tags")).data;
export const createTag = async (name: string, options?: { description?: string; color?: string; is_active?: boolean }) => (await api.post<Tag>("/tags", { name, ...options })).data;
export const assignTag = async (customerId: number, tagId: number) => (await api.post<CustomerDetail>(`/customers/${customerId}/tags/${tagId}`)).data;
export const removeTag = async (customerId: number, tagId: number) => (await api.delete<CustomerDetail>(`/customers/${customerId}/tags/${tagId}`)).data;
export const updateCustomerScore = async (customerId: number, data: { score: number; reason?: string }) => (await api.put<Customer>(`/customers/${customerId}/score`, data)).data;
export const getCustomerScoreHistory = async (customerId: number) => (await api.get<CustomerScoreHistory[]>(`/customers/${customerId}/score-history`)).data;
export const getCustomerCategories = async (activeOnly = false) => (await api.get<CustomerCategory[]>("/customer-categories", { params: { active_only: activeOnly } })).data;
export const createCustomerCategory = async (data: { name: string; description?: string; color?: string; sort_order?: number; is_active?: boolean }) => (await api.post<CustomerCategory>("/customer-categories", data)).data;
export const updateCustomerCategory = async (id: number, data: Partial<{ name: string; description: string; color: string; sort_order: number; is_active: boolean }>) => (await api.put<CustomerCategory>(`/customer-categories/${id}`, data)).data;
export const updateTag = async (id: number, data: Partial<{ name: string; description: string; color: string; is_active: boolean }>) => (await api.put<Tag>(`/tags/${id}`, data)).data;

export type LeadCreatePayload = {
  company_name: string; contact_name: string; country?: string; email?: string; phone?: string;
  whatsapp?: string; source?: string; inquiry_content?: string; interested_product?: string;
  status?: LeadStatus;
};
export type LeadFilters = { limit: number; offset: number; q?: string; status?: string; source?: string };
export const getLeads = async (params: LeadFilters) => (await api.get<LeadPage>("/leads", { params })).data;
export const getLead = async (id: string) => (await api.get<LeadDetail>(`/leads/${id}`)).data;
export const createLead = async (data: LeadCreatePayload) => (await api.post<Lead>("/leads", data)).data;
export const convertLead = async (id: number) => (await api.post<LeadConversion>(`/leads/${id}/convert`)).data;

export type InquiryPayload = {
  company_name: string; contact_name: string; country?: string; email?: string; phone?: string;
  whatsapp?: string; source?: string; source_platform?: string; interested_product?: string;
  inquiry_content: string; status?: InquiryStatus;
};
export type InquiryFilters = { limit: number; offset: number; q?: string; status?: string; source?: string; source_platform?: string };
export const getInquiries = async (params: InquiryFilters) => (await api.get<InquiryPage>("/inquiries", { params })).data;
export const getInquiry = async (id: string) => (await api.get<Inquiry>(`/inquiries/${id}`)).data;
export const createInquiry = async (data: InquiryPayload) => (await api.post<Inquiry>("/inquiries", data)).data;
export const updateInquiry = async (id: number, data: Partial<InquiryPayload>) => (await api.put<Inquiry>(`/inquiries/${id}`, data)).data;
export const convertInquiry = async (id: number) => (await api.post<InquiryConversion>(`/inquiries/${id}/convert`)).data;

export type AlibabaInquiryPayload = {
  company_name: string; contact_name: string; country?: string; email?: string; phone?: string;
  whatsapp?: string; inquiry_content?: string; interested_product?: string; source?: string;
};
export const getAlibabaIntegrationStatus = async () => (await api.get<AlibabaIntegrationStatus>("/integrations/alibaba/status")).data;
export const receiveAlibabaInquiry = async (data: AlibabaInquiryPayload) => (await api.post<AlibabaInquiryResult>("/integrations/alibaba/inquiries", data)).data;

export type OpportunityPayload = {
  customer_id: number; name: string; interested_product?: string; inquiry_content?: string;
  amount?: string; currency?: string; expected_close_date?: string; stage?: OpportunityStage;
  sales_stage?: OpportunitySalesStage; deal_stage?: OpportunityDealStage;
  probability?: number; next_action?: string | null;
  owner_id?: number;
};
export type OpportunityFilters = {
  limit: number; offset: number; q?: string; stage?: string; sales_stage?: string;
  deal_stage?: string; customer_id?: number;
};
export const getOpportunities = async (params: OpportunityFilters) => (await api.get<OpportunityPage>("/opportunities", { params })).data;
export const getOpportunity = async (id: string) => (await api.get<OpportunityDetail>(`/opportunities/${id}`)).data;
export const getOpportunityPipeline = async () => (await api.get<OpportunityPipeline>("/opportunities/pipeline")).data;
export const getOpportunityDealPipeline = async () => (await api.get<OpportunityDealPipeline>("/opportunities/deal-pipeline")).data;
export const createOpportunity = async (data: OpportunityPayload) => (await api.post<OpportunityListItem>("/opportunities", data)).data;
export const updateOpportunity = async (id: number, data: Partial<Omit<OpportunityPayload, "customer_id">>) => (await api.put<OpportunityDetail>(`/opportunities/${id}`, data)).data;
export const deleteOpportunity = async (id: number) => { await api.delete(`/opportunities/${id}`); };

export type ProductImagePayload = { image_url: string; is_primary?: boolean; sort_order?: number };
export type ProductPayload = {
  sku: string; name: string; category_id?: number; material?: string; dimension_text?: string;
  length_mm?: string; width_mm?: string; height_mm?: string; weight_kg?: string;
  unit?: string; moq?: number; reference_price?: string; currency_code?: string;
  description?: string; is_active?: boolean; images?: ProductImagePayload[];
};
export type ProductFilters = { limit: number; offset: number; q?: string; category_id?: number; is_active?: boolean };
export const getProductCategories = async () => (await api.get<ProductCategory[]>("/product-categories")).data;
export const createProductCategory = async (data: { name: string; parent_id?: number; sort_order?: number }) => (await api.post<ProductCategory>("/product-categories", data)).data;
export const getProducts = async (params: ProductFilters) => (await api.get<ProductPage>("/products", { params })).data;
export const searchQuotationProducts = async (q: string) => (
  await api.get<ProductPage>("/products/quotation-search", { params: { q, limit: 50 } })
).data;
export const getProduct = async (id: string) => (await api.get<Product>(`/products/${id}`)).data;
export const createProduct = async (data: ProductPayload) => (await api.post<Product>("/products", data)).data;
export const updateProduct = async (id: number, data: Partial<ProductPayload>) => (await api.put<Product>(`/products/${id}`, data)).data;
export const deleteProduct = async (id: number) => { await api.delete(`/products/${id}`); };
export const replaceOpportunityProducts = async (id: number, items: { product_id: number; quantity: string; target_price?: string }[]) => (await api.put<OpportunityDetail>(`/opportunities/${id}/products`, { items })).data;

export type QuotationItemPayload = { product_id: number; unit_price: string; quantity: string };
export type QuotationCreatePayload = {
  opportunity_id?: number; customer_id?: number; currency?: string; payment_term?: string; delivery_time?: string;
  validity_days?: number; shipping_cost?: string; items?: QuotationItemPayload[];
};
export type QuotationUpdatePayload = Omit<QuotationCreatePayload, "opportunity_id" | "customer_id">;
export const getQuotations = async (params: { limit: number; offset: number; q?: string; status?: QuotationStatus | ""; customer_id?: number }) => (await api.get<QuotationPage>("/quotations", { params })).data;
export const createQuotation = async (data: QuotationCreatePayload) => (await api.post<QuotationDetail>("/quotations", data)).data;
export const getQuotation = async (id: string | number, version_no?: number) => (await api.get<QuotationDetail>(`/quotations/${id}`, { params: { version_no } })).data;
export const deleteQuotation = async (id: number) => { await api.delete(`/quotations/${id}`); };
export const updateQuotation = async (id: number, data: QuotationUpdatePayload) => (await api.put<QuotationDetail>(`/quotations/${id}`, data)).data;
export const createQuotationVersion = async (id: number) => (await api.post<QuotationDetail>(`/quotations/${id}/versions`)).data;
export const generateQuotationPdf = async (id: number, version_no?: number) => (await api.post<QuotationDetail>(`/quotations/${id}/pdf`, undefined, { params: { version_no } })).data;
export const markQuotationSent = async (id: number) => (await api.post<QuotationDetail>(`/quotations/${id}/send`)).data;
export const downloadQuotationPdf = async (id: number, version_no?: number) => (await api.get<Blob>(`/quotations/${id}/pdf`, { params: { version_no }, responseType: "blob" })).data;
export const downloadQuotationExcel = async (id: number, version_no?: number) => (await api.get<Blob>(`/quotations/${id}/excel`, { params: { version_no }, responseType: "blob" })).data;
