import api from "./api";
import type { Customer, CustomerActivity, CustomerDetail, CustomerPage, DashboardStats, FollowUp, Tag } from "../types";

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
