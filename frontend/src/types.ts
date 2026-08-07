export type UserRole = "Admin" | "Sales" | "Viewer";

export type LeadStatus = "New" | "Contacted" | "Qualified" | "Converted" | "Lost";
export interface Lead {
  id: number; public_id: string; company_name: string; contact_name: string;
  country: string | null; email: string | null; phone: string | null; whatsapp: string | null;
  source: string | null; inquiry_content: string | null; interested_product: string | null;
  status: LeadStatus; created_at: string; updated_at: string;
}
export interface LeadDetail extends Lead {
  converted_customer_id: number | null;
  converted_opportunity_id: number | null;
}
export interface LeadPage { items: Lead[]; total: number; limit: number; offset: number; }
export interface Opportunity {
  id: number; public_id: string; customer_id: number; source_lead_id: number | null;
  owner_id: number | null; name: string; interested_product: string | null;
  stage: CustomerStatus; created_at: string; updated_at: string;
}
export interface LeadConversion {
  lead: Lead; customer: Customer; contact: Contact; opportunity: Opportunity;
}
export interface AlibabaIntegrationStatus {
  provider: "Alibaba"; connected: boolean; mode: "simulation";
}
export interface AlibabaInquiryResult {
  lead_id: number; lead_public_id: string; created: boolean; lead: Lead;
}

export interface User { id: number; name: string; email: string; role: UserRole; created_at: string; updated_at: string; }
export interface Customer {
  id: number; company_name: string; contact_name: string | null; country: string | null;
  email: string | null; phone: string | null; whatsapp: string | null; website: string | null;
  customer_type: string | null; source: string | null; interested_product: string | null;
  level: "A" | "B" | "C"; status: CustomerStatus; sales_stage: CustomerStatus;
  owner_id: number | null;
  created_at: string; updated_at: string;
}
export type CustomerStatus = "Lead" | "Contacted" | "Quotation" | "Negotiation" | "Won" | "Lost";
export interface Contact { id: number; customer_id: number; name: string; position: string | null; email: string | null; phone: string | null; whatsapp: string | null; created_at: string; }
export interface FollowUp { id: number; customer_id: number; user_id: number; type: "Email" | "WhatsApp" | "Phone" | "Meeting"; content: string; next_followup_date: string | null; created_at: string; }
export type CustomerActivityType = "customer_created" | "followup" | "status_changed";
export interface CustomerActivity {
  event_id: string;
  event_type: CustomerActivityType;
  occurred_at: string;
  user_id: number | null;
  content: string | null;
  followup_type: FollowUp["type"] | null;
  next_followup_date: string | null;
  old_status: CustomerStatus | null;
  new_status: CustomerStatus | null;
}
export interface CustomerDetail extends Customer { contacts: Contact[]; tags: { id: number; name: string; created_at: string }[]; followups: FollowUp[]; }
export interface CustomerPage { items: Customer[]; total: number; limit: number; offset: number; }
export interface Tag { id: number; name: string; created_at: string; }
export interface DashboardStats {
  customer_count: number; followup_count: number; new_customers_today: number; due_followups: number;
  today_followup_count: number; overdue_followup_count: number;
  pipeline: { status: CustomerStatus; count: number }[];
  upcoming_followups: { id: number; customer_id: number; customer_name: string; type: string; content: string; next_followup_date: string }[];
  today_followups: FollowUpReminder[];
  overdue_followups: FollowUpReminder[];
}
export interface FollowUpReminder {
  id: number; customer_id: number; customer_name: string; type: string; content: string;
  next_followup_date: string; reminder_status: "today" | "overdue";
}
