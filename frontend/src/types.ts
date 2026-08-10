export type UserRole = "Admin" | "Sales" | "Viewer";

export type LeadStatus = "New" | "Contacted" | "Qualified" | "Converted" | "Lost";
export type InquiryStatus = "New" | "Processing" | "Converted" | "Closed";
export type OpportunityStage = "Lead" | "Qualified" | "Proposal" | "Negotiation" | "Won" | "Lost";
export type OpportunitySalesStage = "New Lead" | "Contacted" | "Requirement Confirmed" | "Quotation Sent" | "Negotiation" | "Won" | "Lost";
export type OpportunityDealStage = "New Inquiry" | "Contacted" | "Quoted" | "Negotiating" | "Won" | "Lost";
export type OpportunityReminderStatus = "None" | "Quote Follow-up Due" | "Inactive";
export type CustomerFollowUpReminderStatus = "None" | "Scheduled" | "Today" | "Overdue";
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
export interface Inquiry {
  id: number; public_id: string; customer_id: number | null; converted_opportunity_id: number | null;
  company_name: string; contact_name: string; country: string | null; email: string | null;
  phone: string | null; whatsapp: string | null; source: string; source_platform: string;
  interested_product: string | null; inquiry_content: string; status: InquiryStatus;
  created_at: string; updated_at: string;
}
export interface InquiryPage { items: Inquiry[]; total: number; limit: number; offset: number; }
export interface InquiryConversion { inquiry: Inquiry; customer: Customer; contact: Contact; opportunity: Opportunity; }
export interface Opportunity {
  id: number; public_id: string; customer_id: number; source_lead_id: number | null;
  owner_id: number | null; name: string; interested_product: string | null;
  inquiry_content: string | null; amount: string | null; currency: string;
  expected_close_date: string | null; stage: OpportunityStage;
  sales_stage: OpportunitySalesStage; probability: number; next_action: string | null;
  deal_stage: OpportunityDealStage;
  last_activity_at: string; last_followup_at: string | null;
  quotation_sent_at: string | null; quote_followup_due_date: string | null;
  reminder_status: OpportunityReminderStatus;
  created_at: string; updated_at: string;
}
export interface OpportunityListItem extends Opportunity { customer_company: string; owner_name: string | null; }
export interface OpportunityStageHistory {
  id: number; opportunity_id: number; old_stage: OpportunityStage | null;
  new_stage: OpportunityStage; changed_by_id: number | null; created_at: string;
}
export interface OpportunitySalesStageHistory {
  id: number; opportunity_id: number; old_sales_stage: OpportunitySalesStage | null;
  new_sales_stage: OpportunitySalesStage; changed_by_id: number | null; created_at: string;
}
export interface OpportunityDealStageHistory {
  id: number; opportunity_id: number; old_deal_stage: OpportunityDealStage | null;
  new_deal_stage: OpportunityDealStage; changed_by_id: number | null; created_at: string;
}
export interface OpportunityDetail extends OpportunityListItem {
  customer: Customer; stage_history: OpportunityStageHistory[]; followups: FollowUp[];
  contacts: Contact[]; sales_stage_history: OpportunitySalesStageHistory[];
  deal_stage_history: OpportunityDealStageHistory[]; products: OpportunityProduct[];
  quotations: QuotationListItem[];
}
export interface OpportunityPage { items: OpportunityListItem[]; total: number; limit: number; offset: number; }
export interface OpportunityPipelineColumn {
  sales_stage: OpportunitySalesStage; count: number; opportunities: OpportunityListItem[];
}
export interface OpportunityPipeline { columns: OpportunityPipelineColumn[]; }
export interface OpportunityDealPipelineColumn {
  deal_stage: OpportunityDealStage; count: number; opportunities: OpportunityListItem[];
}
export interface OpportunityDealPipeline { columns: OpportunityDealPipelineColumn[]; }
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
  source_platform: string | null; original_inquiry: string | null;
  category_id: number | null; category: CustomerCategory | null;
  customer_score: number; score_updated_at: string | null;
  next_followup_date: string | null; last_followup_at: string | null;
  followup_reminder_status: CustomerFollowUpReminderStatus;
  level: "A" | "B" | "C"; status: CustomerStatus; sales_stage: CustomerStatus;
  owner_id: number | null;
  created_at: string; updated_at: string;
}
export type CustomerStatus = "Lead" | "Contacted" | "Quotation" | "Negotiation" | "Won" | "Lost";
export interface CustomerCategory {
  id: number; name: string; description: string | null; color: string;
  sort_order: number; is_active: boolean; created_at: string; updated_at: string;
}
export interface CustomerScoreHistory {
  id: number; customer_id: number; old_score: number | null; new_score: number;
  reason: string | null; changed_by_id: number | null; created_at: string;
}
export interface Contact { id: number; customer_id: number; name: string; position: string | null; email: string | null; phone: string | null; whatsapp: string | null; created_at: string; }
export type FollowUpType = "Email" | "WhatsApp" | "Alibaba" | "Phone" | "Meeting";
export interface FollowUpAttachment { id: number; file_name: string; content_type: string | null; size_bytes: number; created_at: string; }
export interface FollowUp {
  id: number; customer_id: number; opportunity_id: number | null; user_id: number;
  type: FollowUpType; followup_date: string; content: string; next_followup_date: string | null;
  created_at: string; updated_at: string; attachments: FollowUpAttachment[];
}
export type CustomerActivityType = "customer_created" | "followup" | "status_changed";
export interface CustomerActivity {
  event_id: string;
  event_type: CustomerActivityType;
  occurred_at: string;
  user_id: number | null;
  content: string | null;
  followup_type: FollowUp["type"] | null;
  followup_date: string | null;
  next_followup_date: string | null;
  opportunity_id: number | null;
  old_status: CustomerStatus | null;
  new_status: CustomerStatus | null;
}
export interface CustomerDetail extends Customer { contacts: Contact[]; tags: { id: number; name: string; created_at: string }[]; followups: FollowUp[]; }
export interface CustomerCenter extends CustomerDetail {
  opportunities: OpportunityListItem[];
  quotations: QuotationListItem[];
  activities: CustomerActivity[];
  score_history: CustomerScoreHistory[];
}
export interface CustomerPage { items: Customer[]; total: number; limit: number; offset: number; }
export interface Tag {
  id: number; name: string; description: string | null; color: string;
  is_active: boolean; created_at: string;
}
export interface DashboardStats {
  customer_count: number; followup_count: number; new_customers_today: number; due_followups: number;
  today_inquiry_count: number; pending_inquiry_count: number;
  inquiry_source_stats: { source: string; count: number }[];
  today_followup_count: number; overdue_followup_count: number;
  pending_followup_customer_count: number;
  week_followup_count: number;
  today_due_customer_count: number; overdue_customer_count: number;
  week_followup_task_count: number;
  pipeline: { status: CustomerStatus; count: number }[];
  upcoming_followups: { id: number; customer_id: number; customer_name: string; type: string; content: string; next_followup_date: string }[];
  today_followups: FollowUpReminder[];
  overdue_followups: FollowUpReminder[];
  opportunity_count: number; active_opportunity_count: number;
  won_opportunity_count: number; lost_opportunity_count: number;
  opportunity_amounts: { currency: string; amount: string }[];
  opportunity_total_amounts: { currency: string; amount: string }[];
  opportunity_pipeline: { sales_stage: OpportunitySalesStage; count: number }[];
  quote_followup_overdue_count: number; inactive_opportunity_count: number;
  opportunity_reminders: OpportunityReminder[];
}
export interface FollowUpReminder {
  id: number; customer_id: number; customer_name: string; type: string; content: string;
  next_followup_date: string; reminder_status: "today" | "overdue";
}
export interface OpportunityReminder {
  id: number; name: string; customer_id: number; customer_name: string;
  reminder_status: Exclude<OpportunityReminderStatus, "None">;
  quote_followup_due_date: string | null; last_activity_at: string;
}

export interface ProductCategory {
  id: number; name: string; parent_id: number | null; sort_order: number;
}
export interface ProductImage {
  id: number; product_id: number; image_url: string; is_primary: boolean;
  sort_order: number; created_at: string;
}
export interface Product {
  id: number; sku: string; name: string; category_id: number | null; category_name: string | null;
  material: string | null; dimension_text: string | null; length_mm: string | null;
  width_mm: string | null; height_mm: string | null; weight_kg: string | null;
  unit: string; moq: number | null; reference_price: string | null; currency_code: string;
  description: string | null; is_active: boolean; images: ProductImage[];
  created_at: string; updated_at: string;
}
export interface ProductPage { items: Product[]; total: number; limit: number; offset: number; }
export interface OpportunityProduct {
  product_id: number; sku: string; name: string; quantity: string;
  target_price: string | null; reference_price: string | null;
  currency_code: string; image_url: string | null;
}

export type QuotationStatus = "Draft" | "Sent" | "Accepted" | "Rejected" | "Expired";
export interface QuotationItem {
  id: number; product_id: number | null; sku_snapshot: string; product_name_snapshot: string;
  picture_snapshot: string | null; unit_price: string; quantity: string; line_total: string;
}
export interface QuotationVersionSummary {
  id: number; version_no: number; currency: string; total_amount: string;
  pdf_url: string | null; created_at: string;
}
export interface QuotationVersion extends QuotationVersionSummary {
  payment_term: string; delivery_time: string; validity_days: number;
  shipping_cost: string; subtotal: string; items: QuotationItem[];
}
export interface QuotationListItem {
  id: number; quotation_number: string; customer_id: number; customer_company: string;
  opportunity_id: number | null; opportunity_name: string | null; status: QuotationStatus;
  current_version: number; currency: string; total_amount: string;
  created_at: string; updated_at: string;
}
export interface QuotationDetail extends QuotationListItem {
  versions: QuotationVersionSummary[]; selected_version: QuotationVersion;
  company_contact: { name: string; website: string; email: string; whatsapp: string };
}
export interface QuotationPage { items: QuotationListItem[]; total: number; limit: number; offset: number; }
