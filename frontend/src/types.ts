export type UserRole = "Admin" | "Sales" | "Viewer";

export interface User { id: number; name: string; email: string; role: UserRole; created_at: string; updated_at: string; }
export interface Customer {
  id: number; company_name: string; contact_name: string | null; country: string | null;
  email: string | null; phone: string | null; whatsapp: string | null; website: string | null;
  source: string | null; level: "A" | "B" | "C"; status: CustomerStatus; owner_id: number | null;
  created_at: string; updated_at: string;
}
export type CustomerStatus = "Lead" | "Contacted" | "Quotation" | "Negotiation" | "Won" | "Lost";
export interface Contact { id: number; customer_id: number; name: string; position: string | null; email: string | null; phone: string | null; whatsapp: string | null; created_at: string; }
export interface FollowUp { id: number; customer_id: number; user_id: number; type: "Email" | "WhatsApp" | "Phone" | "Meeting"; content: string; next_followup_date: string | null; created_at: string; }
export interface CustomerDetail extends Customer { contacts: Contact[]; tags: { id: number; name: string; created_at: string }[]; followups: FollowUp[]; }
export interface CustomerPage { items: Customer[]; total: number; limit: number; offset: number; }
