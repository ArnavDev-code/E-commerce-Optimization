/**
 * Core domain types for FunnelLeak AI
 */

export interface Merchant {
  id: string;
  email: string;
  name?: string | null;
  is_demo: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  merchant: Merchant;
}

export interface ConnectedStore {
  id: string;
  merchant_id: string;
  platform: string;
  shop_domain: string;
  scopes?: string | null;
  is_active: boolean;
  sync_status?: 'idle' | 'syncing' | 'success' | 'failed' | string;
  last_sync_at?: string | null;
  last_sync_error?: string | null;
  data_source?: string;
  installed_at: string;
  recent_sync_logs?: SyncLogItem[];
}

export interface SyncLogItem {
  id: string;
  sync_type: string;
  status: 'started' | 'completed' | 'failed' | string;
  records_synced: number;
  error_message?: string | null;
  started_at: string;
  completed_at?: string | null;
}

export interface ProductVariant {
  id: string;
  product_id: string;
  shopify_variant_id?: string | null;
  sku?: string | null;
  title?: string | null;
  price?: number | null;
  unit_cost?: number | null;
  inventory_quantity: number;
  available: boolean;
}

export interface Product {
  id: string;
  store_id: string;
  shopify_product_id?: string | null;
  title: string;
  handle?: string | null;
  product_type?: string | null;
  vendor?: string | null;
  status: string;
  price?: number | null;
  compare_at_price?: number | null;
  unit_cost?: number | null;
  cost_source?: string | null;
  image_url?: string | null;
  variants?: ProductVariant[];
  views?: number;
  atc_rate?: number;
  checkout_rate?: number;
  purchase_rate?: number;
  purchases?: number;
  revenue?: number;
  gross_margin_pct?: number | null;
}

export interface DetectedLeak {
  id: string;
  store_id: string;
  product_id?: string | null;
  product_title?: string;
  leak_type: string;
  metric_affected: string;
  observed_value: number;
  baseline_value: number;
  sample_size: number;
  period_start: string;
  period_end: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  confidence_score?: number | null;
  evidence_quality: 'strong' | 'moderate' | 'weak';
  reason: string;
  status: 'new' | 'reviewed' | 'resolved' | 'dismissed';
  detected_at: string;
}

export interface AIDiagnosis {
  id: string;
  leak_id: string;
  provider: string;
  issue_summary: string;
  evidence: Array<{
    metric?: string;
    observed_value?: string;
    baseline_value?: string;
    sample_size?: number;
    context?: string;
    fact?: string;
    verified_by?: string;
  }>;
  possible_explanations: Array<{
    hypothesis: string;
    supporting_signals?: string[];
    likelihood: 'high' | 'medium' | 'low';
  }>;
  missing_information?: string[];
  recommended_investigation?: string[];
  further_checks?: string[];
  recommended_actions: string[] | Array<{ action: string; expected_impact: string }>;
  confidence_level: 'high' | 'medium' | 'low';
  is_fallback: boolean;
  created_at: string;
}

export interface Recommendation {
  id: string;
  store_id: string;
  leak_id?: string | null;
  product_id?: string | null;
  product_title?: string | null;
  product_price?: number | null;
  product_cost?: number | null;
  title: string;
  target_stage: string;
  expected_direction: string;
  detected_problem: string;
  supporting_evidence: Record<string, any>;
  suggested_action: string;
  business_reason: string;
  potential_impact_estimate?: number | null;
  implementation_effort: 'low' | 'medium' | 'high';
  confidence_level: 'high' | 'medium' | 'low';
  priority_score?: number | null;
  priority_breakdown?: {
    composite_score: number;
    priority_tier: string;
    impact_score: number;
    confidence_score: number;
    margin_stock_score: number;
    feasibility_score: number;
    weights: {
      impact: number;
      confidence: number;
      margin_stock: number;
      feasibility: number;
    };
    cogs_provided: boolean;
    inventory_units: number;
  };
  risks_or_prerequisites?: string[];
  priority: 'high' | 'medium' | 'low';
  metric_to_monitor: string;
  status: 'new' | 'accepted' | 'rejected' | 'in_progress' | 'completed' | 'pending' | 'approved';
  merchant_notes?: string | null;
  created_at: string;
}

export interface Experiment {
  id: string;
  store_id: string;
  recommendation_id?: string | null;
  product_id?: string | null;
  name: string;
  experiment_type: 'before_after' | 'ab_test';
  hypothesis?: string | null;
  control_description?: string | null;
  treatment_description?: string | null;
  change_made?: string | null;
  status: 'draft' | 'running' | 'completed' | 'cancelled';
  start_date?: string | null;
  end_date?: string | null;
  metric_to_track?: string | null;
  created_at: string;
  result?: ExperimentResult | null;
}

export interface ExperimentResult {
  id: string;
  experiment_id: string;
  metric_name: string;
  control_value: number;
  treatment_value: number;
  absolute_change: number;
  relative_change_pct: number;
  control_sample_size: number;
  treatment_sample_size: number;
  is_statistically_significant?: boolean | null;
  p_value?: number | null;
  merchant_conclusion?: string | null;
  recorded_at: string;
}

export interface AnalyticsOverview {
  total_sessions: number;
  total_orders: number;
  revenue: number;
  aov: number;
  conversion_rate: number;
  gross_profit?: number | null;
  detected_leaks_count: number;
  pending_recommendations_count: number;
  active_experiments_count: number;
}

export interface GA4PropertySummary {
  property_id: string;
  display_name: string;
  account_id?: string | null;
  account_name?: string | null;
}

export interface GA4AccountSummary {
  account_id: string;
  display_name: string;
  properties: GA4PropertySummary[];
}

export interface GA4PropertiesResponse {
  accounts: GA4AccountSummary[];
  total_properties: number;
}

export interface GA4ConnectionStatus {
  is_connected: boolean;
  connection_status: 'connected' | 'disconnected' | 'error' | 'expired' | string;
  provider_property_id?: string | null;
  provider_property_name?: string | null;
  last_validated_at?: string | null;
  last_sync_at?: string | null;
  last_sync_error?: string | null;
  token_expired: boolean;
}

export interface GA4SyncResponse {
  success: boolean;
  records_synced: number;
  message: string;
  error?: string | null;
}
