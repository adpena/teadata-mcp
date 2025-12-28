import { useEffect, useMemo, useState } from 'react';
import { Loader2 } from 'lucide-react';
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';
import { api } from './services/api';
import { Card } from './components/Card';
import { DownloadButton } from './components/DownloadButton';
import { MapBox } from './components/MapBox';
import { StaffingDashboardPayload, StaffingDashboardCampus } from './types';

type MetricKey =
  | 'avg_teacher_experience_years'
  | 'teacher_turnover_rate'
  | 'student_teacher_ratio';

type SummaryStats = {
  count: number;
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
  mean: number;
  variance: number;
};

type TestResult = {
  meanCharter: number | null;
  meanTraditional: number | null;
  diff: number | null;
  pValue: number | null;
  effectSize: number | null;
  countCharter: number;
  countTraditional: number;
};

const RATING_COLORS: Record<string, string> = {
  A: '#22c55e',
  B: '#84cc16',
  C: '#fbbf24',
  D: '#f97316',
  F: '#ef4444',
  NR: '#94a3b8'
};

const METRIC_CONFIG: Array<{
  key: MetricKey;
  label: string;
  unit: string;
  format: (value: number) => string;
}> = [
    {
      key: 'avg_teacher_experience_years',
      label: 'Teacher Experience',
      unit: 'Years',
      format: (value) => `${value.toFixed(1)} yrs`
    },
    {
      key: 'teacher_turnover_rate',
      label: 'Teacher Turnover',
      unit: 'Percent',
      format: (value) => `${value.toFixed(1)}%`
    },
    {
      key: 'student_teacher_ratio',
      label: 'Student-Teacher Ratio',
      unit: 'Students per Teacher',
      format: (value) => `${value.toFixed(1)}:1`
    }
  ];

function toNumber(value: number | string | null | undefined) {
  if (value === null || value === undefined) return null;
  if (value === '.') return null;
  const num = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(num) ? num : null;
}

function normalizeTurnover(value: number | string | null | undefined) {
  const num = toNumber(value);
  if (num === null) return null;
  if (num > 0 && num <= 1) {
    return num * 100;
  }
  return num;
}

function mean(values: number[]) {
  if (values.length === 0) return 0;
  return values.reduce((acc, val) => acc + val, 0) / values.length;
}

function variance(values: number[]) {
  if (values.length < 2) return 0;
  const avg = mean(values);
  return values.reduce((acc, val) => acc + (val - avg) ** 2, 0) / (values.length - 1);
}

function quantile(sorted: number[], p: number) {
  if (!sorted.length) return 0;
  const index = (sorted.length - 1) * p;
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) return sorted[lower];
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (index - lower);
}

function buildSummary(values: number[]): SummaryStats | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return {
    count: values.length,
    min: sorted[0],
    q1: quantile(sorted, 0.25),
    median: quantile(sorted, 0.5),
    q3: quantile(sorted, 0.75),
    max: sorted[sorted.length - 1],
    mean: mean(values),
    variance: variance(values)
  };
}

function erf(x: number) {
  const sign = Math.sign(x);
  const a1 = 0.254829592;
  const a2 = -0.284496736;
  const a3 = 1.421413741;
  const a4 = -1.453152027;
  const a5 = 1.061405429;
  const p = 0.3275911;
  const absX = Math.abs(x);
  const t = 1 / (1 + p * absX);
  const y =
    1 -
    (((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t) *
    Math.exp(-absX * absX);
  return sign * y;
}

function normalCdf(x: number) {
  return 0.5 * (1 + erf(x / Math.SQRT2));
}

function welchTTest(a: number[], b: number[]): TestResult {
  const countA = a.length;
  const countB = b.length;
  if (countA < 2 || countB < 2) {
    return {
      meanCharter: countA ? mean(a) : null,
      meanTraditional: countB ? mean(b) : null,
      diff: null,
      pValue: null,
      effectSize: null,
      countCharter: countA,
      countTraditional: countB
    };
  }
  const meanA = mean(a);
  const meanB = mean(b);
  const varA = variance(a);
  const varB = variance(b);
  const diff = meanA - meanB;
  const denom = Math.sqrt(varA / countA + varB / countB);
  const tStat = denom > 0 ? diff / denom : null;
  const pValue =
    tStat !== null && Number.isFinite(tStat) ? 2 * (1 - normalCdf(Math.abs(tStat))) : null;
  const pooled =
    (countA + countB - 2) > 0
      ? Math.sqrt(((countA - 1) * varA + (countB - 1) * varB) / (countA + countB - 2))
      : null;
  const effectSize = pooled && pooled > 0 ? diff / pooled : null;
  return {
    meanCharter: meanA,
    meanTraditional: meanB,
    diff,
    pValue,
    effectSize,
    countCharter: countA,
    countTraditional: countB
  };
}

function formatPValue(value: number | null) {
  if (value === null) return 'n/a';
  if (value < 0.001) return '<0.001';
  return value.toFixed(3);
}

function ratingColor(rating?: string | null) {
  if (!rating) return RATING_COLORS.NR;
  const normalized = String(rating).toUpperCase().trim();
  if (normalized.startsWith('A')) return RATING_COLORS.A;
  if (normalized.startsWith('B')) return RATING_COLORS.B;
  if (normalized.startsWith('C')) return RATING_COLORS.C;
  if (normalized.startsWith('D')) return RATING_COLORS.D;
  if (normalized.startsWith('F')) return RATING_COLORS.F;
  return RATING_COLORS.NR;
}

function formatNumber(value: number | null, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return 'n/a';
  return value.toFixed(digits);
}

function BoxPlotSvg({
  stats,
  domain,
  color
}: {
  stats: SummaryStats;
  domain: { min: number; max: number };
  color: string;
}) {
  const width = 220;
  const height = 36;
  const padding = 10;
  const range = domain.max - domain.min || 1;
  const scale = (value: number) =>
    padding + ((value - domain.min) / range) * (width - padding * 2);
  const yCenter = height / 2;
  const boxHeight = 12;
  const boxY = yCenter - boxHeight / 2;
  const minX = scale(stats.min);
  const maxX = scale(stats.max);
  const q1X = scale(stats.q1);
  const q3X = scale(stats.q3);
  const medianX = scale(stats.median);
  return (
    <svg width={width} height={height} className="overflow-visible">
      <line x1={minX} y1={yCenter} x2={maxX} y2={yCenter} stroke={color} strokeWidth={2} />
      <rect
        x={q1X}
        y={boxY}
        width={Math.max(q3X - q1X, 2)}
        height={boxHeight}
        fill={color}
        fillOpacity={0.2}
        stroke={color}
        strokeWidth={2}
      />
      <line x1={medianX} y1={boxY} x2={medianX} y2={boxY + boxHeight} stroke={color} strokeWidth={2} />
      <line x1={minX} y1={yCenter - 6} x2={minX} y2={yCenter + 6} stroke={color} strokeWidth={2} />
      <line x1={maxX} y1={yCenter - 6} x2={maxX} y2={yCenter + 6} stroke={color} strokeWidth={2} />
    </svg>
  );
}

function BoxPlotRow({
  label,
  stats,
  domain,
  color,
  format
}: {
  label: string;
  stats: SummaryStats | null;
  domain: { min: number; max: number };
  color: string;
  format: (value: number) => string;
}) {
  return (
    <div className="grid grid-cols-[88px_1fr] items-center gap-3">
      <div>
        <div className="text-sm font-medium text-gray-700">{label}</div>
        <div className="text-xs text-gray-400">{stats ? `n=${stats.count}` : 'n=0'}</div>
      </div>
      {stats ? (
        <div>
          <BoxPlotSvg stats={stats} domain={domain} color={color} />
          <div className="flex justify-between text-xs text-gray-400">
            <span>{format(stats.min)}</span>
            <span>{format(stats.max)}</span>
          </div>
        </div>
      ) : (
        <div className="text-xs text-gray-400">Insufficient data</div>
      )}
    </div>
  );
}

function ScatterTooltip({
  active,
  payload
}: {
  active?: boolean;
  payload?: Array<{ payload: any }>;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0].payload;
  return (
    <div className="bg-white border border-gray-200 rounded-md shadow-sm p-2 text-xs">
      <div className="font-semibold text-gray-900">{point.name}</div>
      <div className="text-gray-500">{point.district}</div>
      <div className="mt-1">
        Enrollment: {point.enrollment?.toLocaleString() || 'n/a'}
      </div>
      <div>Experience: {formatNumber(point.experience, 1)} yrs</div>
      <div>Rating: {point.rating || 'NR'}</div>
    </div>
  );
}

export function StaffingDashboard() {
  const [data, setData] = useState<StaffingDashboardPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        const result = await api.getStaffingDashboard();
        const payload = (result.payload || result) as StaffingDashboardPayload;
        if (active) {
          setData(payload);
        }
      } catch (e: any) {
        if (active) {
          setError(e.message || 'Failed to load staffing data.');
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }
    fetchData();
    return () => {
      active = false;
    };
  }, []);

  const campuses = useMemo(() => {
    if (!data?.campuses) return [];
    return data.campuses.filter((campus) => !campus.is_private);
  }, [data]);

  const charterCampuses = useMemo(
    () => campuses.filter((campus) => campus.charter),
    [campuses]
  );
  const traditionalCampuses = useMemo(
    () => campuses.filter((campus) => !campus.charter),
    [campuses]
  );

  const metricValues = useMemo(() => {
    const getValue = (campus: StaffingDashboardCampus, key: MetricKey) => {
      if (key === 'teacher_turnover_rate') {
        return normalizeTurnover(campus.staffing.teacher_turnover_rate);
      }
      if (key === 'avg_teacher_experience_years') {
        return toNumber(campus.staffing.avg_teacher_experience_years);
      }
      return toNumber(campus.staffing.student_teacher_ratio);
    };
    const values: Record<MetricKey, { charter: number[]; traditional: number[] }> =
    {
      avg_teacher_experience_years: { charter: [], traditional: [] },
      teacher_turnover_rate: { charter: [], traditional: [] },
      student_teacher_ratio: { charter: [], traditional: [] }
    };
    METRIC_CONFIG.forEach((metric) => {
      values[metric.key].charter = charterCampuses
        .map((campus) => getValue(campus, metric.key))
        .filter((value): value is number => value !== null);
      values[metric.key].traditional = traditionalCampuses
        .map((campus) => getValue(campus, metric.key))
        .filter((value): value is number => value !== null);
    });
    return values;
  }, [charterCampuses, traditionalCampuses]);

  const metricSummaries = useMemo(() => {
    const summaries: Record<
      MetricKey,
      { charter: SummaryStats | null; traditional: SummaryStats | null; domain: { min: number; max: number } }
    > = {
      avg_teacher_experience_years: { charter: null, traditional: null, domain: { min: 0, max: 1 } },
      teacher_turnover_rate: { charter: null, traditional: null, domain: { min: 0, max: 1 } },
      student_teacher_ratio: { charter: null, traditional: null, domain: { min: 0, max: 1 } }
    };
    METRIC_CONFIG.forEach((metric) => {
      const charter = buildSummary(metricValues[metric.key].charter);
      const traditional = buildSummary(metricValues[metric.key].traditional);
      const combined = [
        ...(metricValues[metric.key].charter || []),
        ...(metricValues[metric.key].traditional || [])
      ];
      const domain =
        combined.length > 0
          ? {
            min: Math.min(...combined),
            max: Math.max(...combined)
          }
          : { min: 0, max: 1 };
      summaries[metric.key] = { charter, traditional, domain };
    });
    return summaries;
  }, [metricValues]);

  const testResults = useMemo(() => {
    const results: Record<MetricKey, TestResult> = {
      avg_teacher_experience_years: welchTTest(
        metricValues.avg_teacher_experience_years.charter,
        metricValues.avg_teacher_experience_years.traditional
      ),
      teacher_turnover_rate: welchTTest(
        metricValues.teacher_turnover_rate.charter,
        metricValues.teacher_turnover_rate.traditional
      ),
      student_teacher_ratio: welchTTest(
        metricValues.student_teacher_ratio.charter,
        metricValues.student_teacher_ratio.traditional
      )
    };
    return results;
  }, [metricValues]);

  const scatterData = useMemo(() => {
    return campuses
      .map((campus) => {
        const experience = toNumber(campus.staffing.avg_teacher_experience_years);
        const enrollment = toNumber(campus.enrollment);
        if (experience === null || enrollment === null) return null;
        return {
          name: campus.name,
          district: campus.district_name,
          enrollment,
          experience,
          rating: campus.rating || 'NR'
        };
      })
      .filter((point): point is NonNullable<typeof point> => point !== null);
  }, [campuses]);

  const shortageData = useMemo(() => {
    const ratioValues = campuses
      .map((campus) => toNumber(campus.staffing.student_teacher_ratio))
      .filter((value): value is number => value !== null);
    const turnoverValues = campuses
      .map((campus) => normalizeTurnover(campus.staffing.teacher_turnover_rate))
      .filter((value): value is number => value !== null);
    const experienceValues = campuses
      .map((campus) => toNumber(campus.staffing.avg_teacher_experience_years))
      .filter((value): value is number => value !== null);

    if (!ratioValues.length && !turnoverValues.length && !experienceValues.length) {
      return {
        critical: [],
        thresholds: null
      };
    }

    const ratioSorted = [...ratioValues].sort((a, b) => a - b);
    const turnoverSorted = [...turnoverValues].sort((a, b) => a - b);
    const experienceSorted = [...experienceValues].sort((a, b) => a - b);

    const thresholds = {
      ratioHigh: ratioSorted.length ? quantile(ratioSorted, 0.9) : null,
      turnoverHigh: turnoverSorted.length ? quantile(turnoverSorted, 0.9) : null,
      experienceLow: experienceSorted.length ? quantile(experienceSorted, 0.1) : null
    };

    const critical = campuses
      .map((campus) => {
        const ratio = toNumber(campus.staffing.student_teacher_ratio);
        const turnover = normalizeTurnover(campus.staffing.teacher_turnover_rate);
        const experience = toNumber(campus.staffing.avg_teacher_experience_years);
        const signals: string[] = [];
        let score = 0;
        if (ratio !== null && thresholds.ratioHigh !== null && ratio >= thresholds.ratioHigh) {
          signals.push(`High ratio ${ratio.toFixed(1)}:1`);
          score += 1;
        }
        if (turnover !== null && thresholds.turnoverHigh !== null && turnover >= thresholds.turnoverHigh) {
          signals.push(`High turnover ${turnover.toFixed(1)}%`);
          score += 1;
        }
        if (experience !== null && thresholds.experienceLow !== null && experience <= thresholds.experienceLow) {
          signals.push(`Low experience ${experience.toFixed(1)} yrs`);
          score += 1;
        }
        if (score < 2) return null;
        return {
          campus,
          score,
          signals
        };
      })
      .filter((item): item is NonNullable<typeof item> => item !== null)
      .sort((a, b) => b.score - a.score);

    return { critical, thresholds };
  }, [campuses]);

  const criticalMarkers = useMemo(() => {
    return shortageData.critical
      .map((item) => {
        const { campus, score, signals } = item;
        const lat = campus.location?.lat;
        const lon = campus.location?.lon;
        if (lat === null || lon === null || lat === undefined || lon === undefined) {
          return null;
        }
        const color = score >= 3 ? '#ef4444' : '#f97316';
        return {
          lat,
          lon,
          title: campus.name,
          rating: campus.rating || 'NR',
          description: `${campus.district_name} • ${signals.join(' • ')}`,
          color
        };
      })
      .filter((marker): marker is NonNullable<typeof marker> => marker !== null);
  }, [shortageData]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-500">
        <Loader2 className="w-8 h-8 animate-spin mb-4" />
        <p>Loading staffing dashboard...</p>
      </div>
    );
  }

  if (error) {
    return <div className="text-red-500 text-center py-10">{error}</div>;
  }

  if (!data) {
    return <div className="text-center py-10">No staffing data found.</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Staffing Analysis Dashboard</h1>
          <p className="text-gray-600">
            Charter vs traditional staffing patterns, outcomes, and shortage hotspots.
          </p>
        </div>
        <DownloadButton data={data} filename="staffing-dashboard" label="Download data" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4">
          <h3 className="text-sm font-semibold text-gray-500">Total Campuses</h3>
          <p className="text-2xl font-bold">{campuses.length.toLocaleString()}</p>
        </Card>
        <Card className="p-4">
          <h3 className="text-sm font-semibold text-gray-500">Charter Campuses</h3>
          <p className="text-2xl font-bold">{charterCampuses.length.toLocaleString()}</p>
        </Card>
        <Card className="p-4">
          <h3 className="text-sm font-semibold text-gray-500">Traditional Campuses</h3>
          <p className="text-2xl font-bold">{traditionalCampuses.length.toLocaleString()}</p>
        </Card>
      </div>

      <Card className="p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold">Staffing Distribution</h2>
            <p className="text-sm text-gray-500">
              Box plots compare charter vs traditional staffing metrics statewide.
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-amber-400" /> Charter
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-blue-500" /> Traditional
            </span>
          </div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {METRIC_CONFIG.map((metric) => (
            <Card key={metric.key} className="p-4 space-y-3">
              <div>
                <h3 className="font-semibold">{metric.label}</h3>
                <p className="text-xs text-gray-500">{metric.unit}</p>
              </div>
              <BoxPlotRow
                label="Charter"
                stats={metricSummaries[metric.key].charter}
                domain={metricSummaries[metric.key].domain}
                color="#f59e0b"
                format={metric.format}
              />
              <BoxPlotRow
                label="Traditional"
                stats={metricSummaries[metric.key].traditional}
                domain={metricSummaries[metric.key].domain}
                color="#3b82f6"
                format={metric.format}
              />
            </Card>
          ))}
        </div>
      </Card>

      <Card className="p-4 space-y-4">
        <div>
          <h2 className="text-lg font-bold">Significance Tests</h2>
          <p className="text-sm text-gray-500">
            Welch&apos;s t-test (normal approximation) compares charter vs traditional staffing.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="text-xs text-gray-500">
                <th className="p-2 border-b">Metric</th>
                <th className="p-2 border-b">Charter Mean (n)</th>
                <th className="p-2 border-b">Traditional Mean (n)</th>
                <th className="p-2 border-b">Diff</th>
                <th className="p-2 border-b">p-value</th>
                <th className="p-2 border-b">Effect (d)</th>
              </tr>
            </thead>
            <tbody>
              {METRIC_CONFIG.map((metric) => {
                const result = testResults[metric.key];
                return (
                  <tr key={metric.key} className="border-b last:border-b-0">
                    <td className="p-2 font-medium text-gray-700">{metric.label}</td>
                    <td className="p-2">
                      {result.meanCharter !== null
                        ? `${metric.format(result.meanCharter)} (${result.countCharter})`
                        : 'n/a'}
                    </td>
                    <td className="p-2">
                      {result.meanTraditional !== null
                        ? `${metric.format(result.meanTraditional)} (${result.countTraditional})`
                        : 'n/a'}
                    </td>
                    <td className="p-2">
                      {result.diff !== null ? metric.format(result.diff) : 'n/a'}
                    </td>
                    <td className="p-2">
                      {result.pValue !== null ? (
                        <span
                          className={
                            result.pValue < 0.05 ? 'text-emerald-600 font-semibold' : 'text-gray-600'
                          }
                        >
                          {formatPValue(result.pValue)}
                        </span>
                      ) : (
                        'n/a'
                      )}
                    </td>
                    <td className="p-2">
                      {result.effectSize !== null ? result.effectSize.toFixed(2) : 'n/a'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <Card className="p-4 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold">Enrollment vs Experience</h2>
            <p className="text-sm text-gray-500">
              Each dot is a campus. Color represents accountability rating.
            </p>
          </div>
          <div className="flex flex-wrap gap-3 text-xs text-gray-500">
            {Object.entries(RATING_COLORS).map(([label, color]) => (
              <span key={label} className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
                {label}
              </span>
            ))}
          </div>
        </div>
        <div className="h-[360px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                type="number"
                dataKey="enrollment"
                tickFormatter={(value) => value.toLocaleString()}
                name="Enrollment"
              />
              <YAxis type="number" dataKey="experience" name="Experience" />
              <Tooltip content={<ScatterTooltip />} />
              <Scatter
                data={scatterData}
                shape={(props: any) => {
                  if (props.cx === undefined || props.cy === undefined) return <g />;
                  return (
                    <circle
                      cx={props.cx}
                      cy={props.cy}
                      r={4}
                      fill={ratingColor(props.payload?.rating)}
                      fillOpacity={0.75}
                    />
                  );
                }}
                isAnimationActive={false}
              />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card className="p-4 space-y-4">
        <div>
          <h2 className="text-lg font-bold">Critical Staffing Shortages</h2>
          <p className="text-sm text-gray-500">
            Campuses flagged when at least two staffing stress signals fall in the worst decile.
          </p>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 h-[320px]">
            {criticalMarkers.length ? (
              <MapBox
                center={[31.9686, -99.9018]}
                zoom={5}
                markers={criticalMarkers}
                className="h-full w-full rounded-lg border border-gray-200"
                clusterMarkers={false}
              />
            ) : (
              <div className="h-full w-full rounded-lg border border-dashed border-gray-200 flex items-center justify-center text-gray-400 text-sm">
                No critical campuses with mappable coordinates.
              </div>
            )}
          </div>
          <div className="space-y-3">
            <div className="text-sm text-gray-500">
              {shortageData.critical.length} campuses flagged statewide
            </div>
            <div className="space-y-2 max-h-[280px] overflow-y-auto pr-2">
              {shortageData.critical.slice(0, 10).map((item) => (
                <div key={item.campus.campus_number} className="border rounded-lg p-2">
                  <div className="text-sm font-semibold">{item.campus.name}</div>
                  <div className="text-xs text-gray-500">{item.campus.district_name}</div>
                  <div className="text-xs text-gray-600 mt-1">{item.signals.join(' • ')}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
