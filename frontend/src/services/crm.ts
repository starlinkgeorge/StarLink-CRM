import api from "./api";
import type { Customer, CustomerDetail, CustomerPage, FollowUp } from "../types";

export type CustomerCreatePayload = {
  company_name: string; contact_name?: string; country?: string; email?: string; phone?: string;
  whatsapp?: string; website?: string; source?: string; level?: Customer["level"]; status?: Customer["status"];
};

export const getDashboardStats = async () => (await api.get<{ customer_count: number; followup_count: number }>("/dashboard/stats")).data;
export const getCustomers = async (params: { limit: number; offset: number; q?: string }) => (await api.get<CustomerPage>("/customers", { params })).data;
export const getCustomer = async (id: string) => (await api.get<CustomerDetail>(`/customers/${id}`)).data;
export const createCustomer = async (data: CustomerCreatePayload) => (await api.post<Customer>("/customers", data)).data;
export const createFollowup = async (data: { customer_id: number; user_id: number; type: string; content: string; next_followup_date?: string }) => (await api.post<FollowUp>("/followups", data)).data;
