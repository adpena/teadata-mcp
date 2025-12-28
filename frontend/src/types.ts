import './types/openai';

export interface CampusSummary {
  campus_number: string;
  name: string;
  district_name: string;
  charter: boolean;
  charter_label: string;
  is_private: boolean;
  enrollment: number | null;
  rating: string | null;
  grade_range: string;
  district_slug: string;
}

export interface StaffingStats {
  total_teachers_fte: number | null;
  student_teacher_ratio: number | null;
  avg_teacher_salary: number | null;
  avg_teacher_experience_years: number | null;
  teacher_turnover_rate: number | null;
}

export interface ClassSizeStats {
  elementary: Record<string, number | null>;
  secondary: Record<string, number | null>;
}

export interface DemographicsPercent {
  african_american: number | null;
  hispanic: number | null;
  white: number | null;
  asian: number | null;
  pacific_islander: number | null;
  two_or_more: number | null;
}

export interface ProgramsPercent {
  special_ed: number | null;
  econ_disadv: number | null;
  emergent_bilingual: number | null;
  immigrant: number | null;
}

export interface DemographicStats {
  ethnicity_percent: DemographicsPercent;
  programs_percent: ProgramsPercent;
}

export interface CampusDetail extends CampusSummary {
  staffing: StaffingStats;
  class_sizes: ClassSizeStats;
  demographics: DemographicStats;
  location: { lat: number | null; lon: number | null };
  transfers_out: any[];
}

export interface DistrictSummary {
  name: string;
  district_number: string;
  rating: string | null;
  enrollment: number | null;
  location?: { lat: number | null; lon: number | null };
  campuses?: CampusSummary[];
}

export interface TransferSankeyNode {
  id: string;
  name: string;
  kind: 'source' | 'destination';
  is_charter: boolean;
  rating: string | null;
  total_outgoing?: number | null;
}

export interface TransferSankeyLink {
  source: number;
  target: number;
  value: number;
  source_id: string;
  target_id: string;
}

export interface TransferFlowMapItem {
  source_id: string;
  source_name: string;
  source_lat: number;
  source_lon: number;
  source_rating: string | null;
  destination_id: string;
  destination_name: string;
  destination_lat: number;
  destination_lon: number;
  destination_rating: string | null;
  destination_charter: boolean;
  count: number;
  total_outgoing: number;
  distance_miles: number | null;
  rating_change: 'higher' | 'lower' | 'same' | 'unknown';
  within_neighborhood: boolean | null;
}

export interface TransferInsights {
  available: boolean;
  scope: {
    district_identifier?: string | null;
    district_name?: string | null;
    campus_query?: string | null;
  };
  summary: {
    total_transfers: number;
    total_sources: number;
    total_destinations: number;
    masked_records: number;
  };
  charter_breakdown: {
    charter_count: number;
    traditional_count: number;
    private_count: number;
    unknown_count: number;
    charter_percent: number;
    traditional_percent: number;
    private_percent: number;
  };
  rating_shift: {
    higher_count: number;
    lower_count: number;
    same_count: number;
    unknown_count: number;
    higher_percent: number;
    lower_percent: number;
    same_percent: number;
  };
  distance: {
    neighborhood_radius_miles: number;
    within_radius_count: number;
    within_radius_percent: number;
    distance_count: number;
    average_miles: number | null;
    bucket_counts: Array<{ label: string; count: number }>;
    missing_location_count: number;
  };
  sankey: {
    nodes: TransferSankeyNode[];
    links: TransferSankeyLink[];
    source_limit: number;
    destination_limit: number;
    min_transfer_count: number;
  };
  map: {
    flows: TransferFlowMapItem[];
    source_limit: number;
  };
  snapshot?: any;
}

export interface StaffingDashboardCampus {
  campus_number: string;
  name: string;
  district_name: string;
  charter: boolean;
  charter_label: string;
  is_private: boolean;
  enrollment: number | null;
  rating: string | null;
  staffing: {
    student_teacher_ratio: number | string | null;
    avg_teacher_experience_years: number | string | null;
    teacher_turnover_rate: number | string | null;
  };
  location: { lat: number | null; lon: number | null };
}

export interface StaffingDashboardPayload {
  total_campuses: number;
  campuses: StaffingDashboardCampus[];
  snapshot?: {
    load_snapshot?: boolean;
    snapshot_configured?: boolean;
    max_response_bytes?: number | null;
  };
}
