export type Issue = { field: string; message: string; severity: 'error' | 'warning' }
export type Box = { id: string; text: string; score: number; rect: number[] }
export type Invoice = {
  id: string; filename: string; page: number; revision: number; created_at: string; updated_at: string;
  invoice_number: string; invoice_code: string; invoice_date: string; invoice_type: string;
  buyer_name: string; buyer_tax_id: string; seller_name: string; seller_tax_id: string;
  subtotal: string | null; tax_amount: string | null; total: string | null; tax_rates: string;
  category: string; remark: string; status: 'needs_review' | 'approved' | 'rejected'; source: string;
  engine: string; confidence: number; duplicate: boolean; issues: Issue[]; completeness: number;
  preview_url: string; original_url: string; boxes?: Box[]; evidence?: Record<string,string>;
  raw_text?: string; items?: { name: string; amount: string | null; tax_amount: string | null; tax_rate: string }[];
}
export type Settings = { workspace_name: string; confidence_threshold: number; amount_tolerance: string }
export type Meta = { settings: Settings; categories: string[]; ocr_available: boolean; provided_count: number; demo_count: number }
export type Dashboard = {
  total_count: number; approved_count: number; pending_count: number; rejected_count: number;
  anomaly_count: number; duplicate_count: number; total_amount: string; tax_amount: string;
  pdf_count: number; ocr_count: number;
  trend: { month: string; amount: number; count: number }[];
  categories: { name: string; amount: number; count: number }[];
  suppliers: { name: string; amount: number; count: number }[]; recent: Invoice[];
}
export type Job = { id: string; source: string; status: string; total: number; processed: number; succeeded: number; failed: number; skipped: number; current_file: string; created_at: string; error?: string; results: { filename: string; status: string; message: string; invoice_ids: string[] }[]; errors: { filename: string; message: string }[] }
export type Audit = { id: number; action: string; invoice_id: string | null; summary: string; changes: Record<string,unknown>; created_at: string }
export type Filters = { q: string; status: string; category: string; source: string; start: string; end: string; sort: string }
export type Page = 'dashboard' | 'upload' | 'invoices' | 'analytics' | 'audit' | 'settings'
