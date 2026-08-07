import api from "./api";
import type { AlibabaInquiryResult, AlibabaIntegrationStatus, Customer, CustomerActivity, CustomerDetail, CustomerPage, DashboardStats, FollowUp, Lead, LeadConversion, LeadDetail, LeadPage, LeadStatus, OpportunityDetail, OpportunityListItem, OpportunityPage, OpportunityStage, Product, ProductCategory, ProductPage, Tag } from "../types";

export type CustomerCreatePayload = {
  company_name: string; contact_name?: string; country?: string; email?: string; phone?: string;
  whatsapp?: string; website?: string; customer_type?: string; source?: string;
  interested_product?: string; level?: Customer["level"]; status?: Customer["status"];
  sales_stage?: Customer["sales_stage"];
};

export const getDashboardStats = async () => (await api.get<DashboardStats>("/dashboard/stats")).data;
export type CustomerFilters = {
  limit: number; offset: number; q?: string; status?: string; level?: string; country?: string;
  customer_type?: string; source?: string; interested_product?: string; sales_stage?: string;
  tag_id?: number;
};
export const getCustomers = async (params: CustomerFilters) => (await api.get<CustomerPage>("/customers", { params })).data;
export const getCustomer = async (id: string) => (await api.get<CustomerDetail>(`/customers/${id}`)).data;
export const getCustomerTimeline = async (id: string) => (await api.get<CustomerActivity[]>(`/customers/${id}/timeline`)).data;
export const createCustomer = async (data: CustomerCreatePayload) => (await api.post<Customer>("/customers", data)).data;
export const updateCustomer = async (id: number, data: Partial<CustomerCreatePayload>) => (await api.put<Customer>(`/customers/${id}`, data)).data;
export const createFollowup = async (data: { customer_id: number; user_id: number; type: string; content: string; next_followup_date?: string }) => (await api.post<FollowUp>("/followups", data)).data;
export const getTags = async () => (await api.get<Tag[]>("/tags")).data;
export const createTag = async (name: string) => (await api.post<Tag>("/tags", { name })).data;
export const assignTag = async (customerId: number, tagId: number) => (await api.post<CustomerDetail>(`/customers/${customerId}/tags/${tagId}`)).data;
export const removeTag = async (customerId: number, tagId: number) => (await api.delete<CustomerDetail>(`/customers/${customerId}/tags/${tagId}`)).data;

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

export type AlibabaInquiryPayload = {
  company_name: string; contact_name: string; country?: string; email?: string; phone?: string;
  whatsapp?: string; inquiry_content?: string; interested_product?: string; source?: string;
};
export const getAlibabaIntegrationStatus = async () => (await api.get<AlibabaIntegrationStatus>("/integrations/alibaba/status")).data;
export const receiveAlibabaInquiry = async (data: AlibabaInquiryPayload) => (await api.post<AlibabaInquiryResult>("/integrations/alibaba/inquiries", data)).data;

export type OpportunityPayload = {
  customer_id: number; name: string; interested_product?: string; inquiry_content?: string;
  amount?: string; currency?: string; expected_close_date?: string; stage?: OpportunityStage;
  owner_id?: number;
};
export type OpportunityFilters = {
  limit: number; offset: number; q?: string; stage?: string; customer_id?: number;
};
export const getOpportunities = async (params: OpportunityFilters) => (await api.get<OpportunityPage>("/opportunities", { params })).data;
export const getOpportunity = async (id: string) => (await api.get<OpportunityDetail>(`/opportunities/${id}`)).data;
export const createOpportunity = async (data: OpportunityPayload) => (await api.post<OpportunityListItem>("/opportunities", data)).data;
export const updateOpportunity = async (id: number, data: Partial<Omit<OpportunityPayload, "customer_id">>) => (await api.put<OpportunityDetail>(`/opportunities/${id}`, data)).data;

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
export const getProduct = async (id: string) => (await api.get<Product>(`/products/${id}`)).data;
export const createProduct = async (data: ProductPayload) => (await api.post<Product>("/products", data)).data;
export const updateProduct = async (id: number, data: Partial<ProductPayload>) => (await api.put<Product>(`/products/${id}`, data)).data;
export const replaceOpportunityProducts = async (id: number, items: { product_id: number; quantity: string; target_price?: string }[]) => (await api.put<OpportunityDetail>(`/opportunities/${id}/products`, { items })).data;
