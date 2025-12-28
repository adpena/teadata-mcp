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
