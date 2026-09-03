import api from "./api";
import type { AlibabaInquiryResult, AlibabaIntegrationStatus, AnalyticsPeriod, BusinessAnalyticsOverview, CalculatedFollowupReminderStatus, Customer, CustomerActivity, CustomerCategory, CustomerCenter, CustomerDetail, CustomerFollowupReminderPage, CustomerPage, CustomerScoreHistory, DashboardStats, DashboardTask, FollowUp, FollowUpAttachment, MailFolder, MailFolderCounts, MailMessage, MailMessagePage, OpportunityDealStage, OpportunityDetail, OpportunityListItem, OpportunityPage, OpportunitySalesStage, OpportunityStage, Order, OrderPage, OrderProfitAnalytics, OrderProfitPeriod, OtherSalesAmount, Product, ProductCategory, ProductPage, QuotationDetail, QuotationPage, QuotationStatus, SalesTargetProgress, SystemSettings, Tag, TaskPriority, WonOrderBackfillPreview, WonOrderBackfillResult } from "../types";

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
export const getMailMessages = async (params: { folder?: "inbox" | "sent" | "unread" | "drafts" | "starred" | "all"; customer_id?: number; mail_folder_id?: number; query?: string; date_from?: string; date_to?: string; has_attachments?: boolean; is_read?: boolean; is_starred?: boolean; limit?: number; offset?: number } = {}) => (await api.get<MailMessagePage>("/mail/messages", { params })).data;
export const getMailMessage = async (id: number) => (await api.get<MailMessage>(`/mail/messages/${id}`)).data;
export const getMailFolderCounts = async () => (await api.get<MailFolderCounts>("/mail/counts")).data;
export const syncMail = async () => (await api.post<{ imported: number; skipped: number; folders: string[] }>("/mail/sync")).data;
export const getMailFolders = async () => (await api.get<MailFolder[]>("/mail/folders")).data;
export const createMailFolder = async (data: { name: string; customer_id?: number; bound_addresses?: string[] }) => (await api.post<MailFolder>("/mail/folders", data)).data;
export const updateMailFolder = async (id: number, data: { name: string; customer_id?: number; bound_addresses?: string[] }) => (await api.put<MailFolder>(`/mail/folders/${id}`, data)).data;
export const deleteMailFolder = async (id: number) => { await api.delete(`/mail/folders/${id}`); };
export const sendMail = async (data: { to_emails: string; cc_emails?: string; bcc_emails?: string; subject: string; body: string; html_body?: string; customer_id?: number; reply_to_id?: number; forward_of_id?: number; draft_id?: number; tracking_enabled?: boolean; files?: File[] }) => {
  const form = new FormData(); form.append("to_emails", data.to_emails); form.append("subject", data.subject); form.append("body", data.body);
  form.append("cc_emails", data.cc_emails ?? ""); form.append("bcc_emails", data.bcc_emails ?? ""); form.append("html_body", data.html_body ?? "");
  form.append("tracking_enabled", String(data.tracking_enabled ?? true));
  if (data.customer_id) form.append("customer_id", String(data.customer_id)); if (data.reply_to_id) form.append("reply_to_id", String(data.reply_to_id));
  if (data.forward_of_id) form.append("forward_of_id", String(data.forward_of_id));
  if (data.draft_id) form.append("draft_id", String(data.draft_id));
  data.files?.forEach((file) => form.append("files", file));
  return (await api.post<MailMessage>("/mail/send", form)).data;
};
export const sendMailIndividually = async (data: { to_emails: string; cc_emails?: string; bcc_emails?: string; subject: string; body: string; html_body?: string; customer_id?: number; reply_to_id?: number; forward_of_id?: number; tracking_enabled?: boolean; files?: File[] }) => {
  const form = new FormData(); form.append("to_emails", data.to_emails); form.append("subject", data.subject); form.append("body", data.body); form.append("cc_emails", data.cc_emails ?? ""); form.append("bcc_emails", data.bcc_emails ?? ""); form.append("html_body", data.html_body ?? ""); form.append("tracking_enabled", String(data.tracking_enabled ?? true));
  if (data.customer_id) form.append("customer_id", String(data.customer_id)); if (data.reply_to_id) form.append("reply_to_id", String(data.reply_to_id)); if (data.forward_of_id) form.append("forward_of_id", String(data.forward_of_id)); data.files?.forEach((file) => form.append("files", file));
  return (await api.post<{ sent: MailMessage[]; failed_addresses: string[] }>("/mail/send-individually", form)).data;
};
export const saveMailDraft = async (data: { to_emails?: string; cc_emails?: string; bcc_emails?: string; subject?: string; body?: string; html_body?: string; customer_id?: number; draft_id?: number; files?: File[] }) => {
  const form = new FormData(); form.append("to_emails", data.to_emails ?? ""); form.append("cc_emails", data.cc_emails ?? ""); form.append("bcc_emails", data.bcc_emails ?? ""); form.append("subject", data.subject ?? ""); form.append("body", data.body ?? ""); form.append("html_body", data.html_body ?? "");
  if (data.customer_id) form.append("customer_id", String(data.customer_id)); if (data.draft_id) form.append("draft_id", String(data.draft_id)); data.files?.forEach((file) => form.append("files", file));
  return (await api.post<MailMessage>("/mail/drafts", form)).data;
};
export const downloadMailAttachment = async (messageId: number, attachmentId: number) => (await api.get<Blob>(`/mail/messages/${messageId}/attachments/${attachmentId}`, { responseType: "blob" })).data;
export const markMailRead = async (id: number) => (await api.post<MailMessage>(`/mail/messages/${id}/read`)).data;
export const markMailUnread = async (id: number) => (await api.post<MailMessage>(`/mail/messages/${id}/unread`)).data;
export const bulkUpdateMail = async (messageIds: number[], data: { is_read?: boolean; is_starred?: boolean; mail_folder_id?: number; clear_mail_folder?: boolean; deleted?: boolean }) => (await api.post<MailMessage[]>("/mail/messages/bulk", messageIds, { params: data })).data;
export const getSystemSettings = async () => (await api.get<SystemSettings>("/settings")).data;
export const updateSystemSettings = async (data: SystemSettings) => (await api.put<SystemSettings>("/settings", data)).data;
export const getDashboardTasks = async () => (await api.get<DashboardTask[]>("/dashboard/tasks/today")).data;
export const createDashboardTask = async (data: { title: string; due_date: string; priority: TaskPriority; customer_id?: number }) => (await api.post<DashboardTask>("/dashboard/tasks", data)).data;
export const completeDashboardTask = async (id: number) => (await api.post<DashboardTask>(`/dashboard/tasks/${id}/complete`)).data;
export const deleteDashboardTask = async (id: number) => { await api.delete(`/dashboard/tasks/${id}`); };
export const getSalesTargetProgress = async () => (await api.get<SalesTargetProgress>("/dashboard/sales-target-progress")).data;
export const updateSalesTarget = async (year: number, target_amount: string) => (await api.put(`/dashboard/sales-targets/${year}`, { target_amount })).data;
export const getOtherSales = async (year: number) => (await api.get<OtherSalesAmount[]>("/dashboard/other-sales", { params: { year } })).data;
export const createOtherSale = async (data: { sale_date: string; amount: string; currency: string; note: string }) => (await api.post<OtherSalesAmount>("/dashboard/other-sales", data)).data;
export const updateOtherSale = async (id: number, data: { sale_date: string; amount: string; currency: string; note: string }) => (await api.put<OtherSalesAmount>(`/dashboard/other-sales/${id}`, data)).data;
export const deleteOtherSale = async (id: number) => { await api.delete(`/dashboard/other-sales/${id}`); };
export const getBusinessAnalytics = async (params: { period: AnalyticsPeriod; start_date?: string; end_date?: string }) => (
  await api.get<BusinessAnalyticsOverview>("/analytics/overview", { params })
).data;
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
  cold_customer?: boolean;
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
export const createOpportunity = async (data: OpportunityPayload) => (await api.post<OpportunityListItem>("/opportunities", data)).data;
export const updateOpportunity = async (id: number, data: Partial<Omit<OpportunityPayload, "customer_id">>) => (await api.put<OpportunityDetail>(`/opportunities/${id}`, data)).data;
export const deleteOpportunity = async (id: number) => { await api.delete(`/opportunities/${id}`); };
export type OrderPayload = { order_no:string; customer_id:number; opportunity_id?:number; quotation_id?:number; order_date:string; currency:string; order_amount:string; payment_status?:Order["payment_status"]; production_status?:Order["production_status"]; shipping_status?:Order["shipping_status"]; expected_delivery_date?:string; shipped_at?:string; notes?:string; rmb_received_amount?:string | null; purchase_cost?:string | null; freight_cost?:string | null; };
export const getOrders = async (params:{limit:number;offset:number;q?:string;customer_id?:number;start_date?:string;end_date?:string;payment_status?:Order["payment_status"];production_status?:Order["production_status"];shipping_status?:Order["shipping_status"]}) => (await api.get<OrderPage>("/orders",{params})).data;
export const getOrder = async (id:string|number) => (await api.get<Order>(`/orders/${id}`)).data;
export const createOrder = async (payload:OrderPayload) => (await api.post<Order>("/orders",payload)).data;
export const updateOrder = async (id:number,payload:Partial<OrderPayload>) => (await api.put<Order>(`/orders/${id}`,payload)).data;
export const deleteOrder = async (id:number) => { await api.delete(`/orders/${id}`); };
export const getOrderByQuotation = async (id:number) => (await api.get<Order|null>(`/orders/by-quotation/${id}`)).data;
export const getOrderProfitAnalytics = async (params: { period: OrderProfitPeriod; start_date?: string; end_date?: string }) => (await api.get<OrderProfitAnalytics>("/orders/analytics/profit", { params })).data;
export const previewWonOrderBackfill = async () => (await api.get<WonOrderBackfillPreview>("/orders/won-backfill/preview")).data;
export const backfillWonOrders = async (fallback_order_date?: string) => (await api.post<WonOrderBackfillResult>("/orders/won-backfill", { fallback_order_date: fallback_order_date || null })).data;

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
