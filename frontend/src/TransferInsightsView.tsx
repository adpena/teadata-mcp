import React, { useEffect, useMemo, useState } from 'react';
import { Card } from './components/Card';
import { DownloadButton } from './components/DownloadButton';
import { MapBox } from './components/MapBox';
import { api } from './services/api';
import { TransferInsights } from './types';
import { Button } from '@openai/apps-sdk-ui/components/Button';
import { Loader2 } from 'lucide-react';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Sankey
} from 'recharts';

const FLOW_COLORS: Record<string, string> = {
  higher: '#22c55e',
  lower: '#ef4444',
  same: '#3b82f6',
  unknown: '#9ca3af'
};

const SHARE_COLORS = ['#22c55e', '#3b82f6', '#f59e0b', '#9ca3af'];

function formatPercent(value: number) {
  if (!Number.isFinite(value)) return '0%';
  return `${value.toFixed(1)}%`;
}

function SankeyTooltip({ active, payload }: any) {
  if (!active || !payload || payload.length === 0) {
    return null;
  }
  const entry = payload[0]?.payload;
  if (!entry) {
    return null;
  }
  if (entry.source && entry.target) {
    return (
      <div className="bg-white border border-gray-200 rounded p-2 shadow text-xs">
        <div className="font-semibold">{entry.source.name} &rarr; {entry.target.name}</div>
        <div>{entry.value?.toLocaleString() || 0} transfers</div>
      </div>
    );
  }
  return (
    <div className="bg-white border border-gray-200 rounded p-2 shadow text-xs">
      <div className="font-semibold">{entry.name || 'Campus'}</div>
      {entry.total_outgoing ? <div>{entry.total_outgoing.toLocaleString()} outgoing</div> : null}
    </div>
  );
}

function SankeyNode({ x, y, width, height, payload }: any) {
  const kind = payload?.kind;
  const isCharter = payload?.is_charter;
  const color = kind === 'source' ? '#1d4ed8' : isCharter ? '#14b8a6' : '#f97316';
  const name = payload?.name || '';
  const label = name.length > 24 ? `${name.slice(0, 24)}...` : name;
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill={color} fillOpacity={0.85} rx={2} />
      {height > 14 && (
        <text x={x + width + 6} y={y + height / 2} dy={4} fontSize={11} fill="#374151">
          {label}
        </text>
      )}
    </g>
  );
}

interface FilterState {
  districtIdentifier: string;
  campusQuery: string;
  topSources: string;
  topDestinations: string;
  minTransferCount: string;
  neighborhoodRadiusMiles: string;
}

export function TransferInsightsView() {
  const [data, setData] = useState<TransferInsights | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterState>({
    districtIdentifier: '',
    campusQuery: '',
    topSources: '20',
    topDestinations: '3',
    minTransferCount: '10',
    neighborhoodRadiusMiles: '5'
  });

  const loadInsights = async (options?: Partial<FilterState>) => {
    const toNumber = (value?: string) => {
      if (!value) return undefined;
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : undefined;
    };
    setLoading(true);
    setError(null);
    try {
      const payload = await api.getTransferInsights({
        districtIdentifier: options?.districtIdentifier?.trim() || undefined,
        campusQuery: options?.campusQuery?.trim() || undefined,
        topSources: toNumber(options?.topSources),
        topDestinations: toNumber(options?.topDestinations),
        minTransferCount: toNumber(options?.minTransferCount),
        neighborhoodRadiusMiles: toNumber(options?.neighborhoodRadiusMiles)
      });
      const normalized = payload.payload || payload;
      setData(normalized as TransferInsights);
    } catch (e: any) {
      setError(e.message || 'Failed to load transfer insights.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInsights(filters);
  }, []);

  const charterShare = useMemo(() => {
    if (!data) return [];
    return [
      { name: 'Charter', value: data.charter_breakdown.charter_count },
      { name: 'Traditional', value: data.charter_breakdown.traditional_count },
      { name: 'Private', value: data.charter_breakdown.private_count },
      { name: 'Unknown', value: data.charter_breakdown.unknown_count }
    ].filter((entry) => entry.value > 0);
  }, [data]);

  const ratingShift = useMemo(() => {
    if (!data) return [];
    return [
      { name: 'Higher', count: data.rating_shift.higher_count },
      { name: 'Same', count: data.rating_shift.same_count },
      { name: 'Lower', count: data.rating_shift.lower_count },
      { name: 'Unknown', count: data.rating_shift.unknown_count }
    ].filter((entry) => entry.count > 0);
  }, [data]);

  const distanceBuckets = useMemo(() => {
    if (!data) return [];
    return data.distance.bucket_counts.map((bucket) => ({
      label: bucket.label,
      count: bucket.count
    }));
  }, [data]);

  const flowLines = useMemo(() => {
    if (!data) return [];
    return data.map.flows.map((flow) => ({
      id: `${flow.source_id}-${flow.destination_id}`,
      from: {
        lat: flow.source_lat,
        lon: flow.source_lon,
        title: flow.source_name
      },
      to: {
        lat: flow.destination_lat,
        lon: flow.destination_lon,
        title: flow.destination_name
      },
      count: flow.count,
      color: FLOW_COLORS[flow.rating_change] || FLOW_COLORS.unknown,
      label: `${flow.source_name} -> ${flow.destination_name} (${flow.count.toLocaleString()} transfers)`
    }));
  }, [data]);

  const flowMarkers = useMemo(() => {
    if (!data) return [];
    const seen = new Set<string>();
    const markers: Array<{ lat: number; lon: number; title: string; description?: string }> = [];
    for (const flow of data.map.flows) {
      const sourceKey = `source:${flow.source_id}`;
      if (!seen.has(sourceKey)) {
        markers.push({
          lat: flow.source_lat,
          lon: flow.source_lon,
          title: flow.source_name,
          description: `Top destination: ${flow.destination_name} (${flow.count.toLocaleString()})`
        });
        seen.add(sourceKey);
      }
      const destKey = `dest:${flow.destination_id}`;
      if (!seen.has(destKey)) {
        markers.push({
          lat: flow.destination_lat,
          lon: flow.destination_lon,
          title: flow.destination_name,
          description: `Destination from ${flow.source_name}`
        });
        seen.add(destKey);
      }
    }
    return markers;
  }, [data]);

  const scopeLabel = useMemo(() => {
    if (!data) return 'Statewide';
    if (data.scope?.district_name) return data.scope.district_name;
    if (data.scope?.district_identifier) return data.scope.district_identifier;
    return 'Statewide';
  }, [data]);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    loadInsights(filters);
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-500">
        <Loader2 className="w-8 h-8 animate-spin mb-4" />
        <p>Analyzing transfer flows...</p>
      </div>
    );
  }

  if (error) {
    return <div className="text-red-500 text-center py-10">{error}</div>;
  }

  if (!data || !data.available) {
    return (
      <Card className="p-6 text-center text-gray-600">
        Transfer destination data is not available in this snapshot.
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Transfer Insights</h1>
          <p className="text-gray-600">Scope: {scopeLabel}</p>
        </div>
        <DownloadButton data={data} filename="transfer-insights" label="Export JSON" />
      </div>

      <Card className="p-4">
        <form className="grid grid-cols-1 md:grid-cols-3 gap-3" onSubmit={handleSubmit}>
          <div>
            <label className="text-xs font-semibold text-gray-600">District (optional)</label>
            <input
              type="text"
              value={filters.districtIdentifier}
              onChange={(event) => setFilters({ ...filters, districtIdentifier: event.target.value })}
              className="mt-1 w-full border rounded px-3 py-2 text-sm"
              placeholder="Austin ISD or 227901"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-600">Campus filter (optional)</label>
            <input
              type="text"
              value={filters.campusQuery}
              onChange={(event) => setFilters({ ...filters, campusQuery: event.target.value })}
              className="mt-1 w-full border rounded px-3 py-2 text-sm"
              placeholder="IDEA, KIPP, Westlake"
            />
          </div>
          <div className="flex items-end">
            <Button type="submit" variant="solid" color="primary" className="w-full">
              Run Analysis
            </Button>
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-600">Top sources</label>
            <input
              type="number"
              value={filters.topSources}
              onChange={(event) => setFilters({ ...filters, topSources: event.target.value })}
              className="mt-1 w-full border rounded px-3 py-2 text-sm"
              min={1}
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-600">Top destinations</label>
            <input
              type="number"
              value={filters.topDestinations}
              onChange={(event) => setFilters({ ...filters, topDestinations: event.target.value })}
              className="mt-1 w-full border rounded px-3 py-2 text-sm"
              min={1}
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-600">Min transfer count</label>
            <input
              type="number"
              value={filters.minTransferCount}
              onChange={(event) => setFilters({ ...filters, minTransferCount: event.target.value })}
              className="mt-1 w-full border rounded px-3 py-2 text-sm"
              min={0}
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-600">Neighborhood radius (miles)</label>
            <input
              type="number"
              value={filters.neighborhoodRadiusMiles}
              onChange={(event) =>
                setFilters({ ...filters, neighborhoodRadiusMiles: event.target.value })
              }
              className="mt-1 w-full border rounded px-3 py-2 text-sm"
              min={1}
              step={0.5}
            />
          </div>
          <div className="md:col-span-2 flex items-end text-xs text-gray-500">
            Showing top {data.sankey.source_limit} sources and {data.sankey.destination_limit} destinations per source.
          </div>
        </form>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="text-sm text-gray-500">Total transfers</div>
          <div className="text-2xl font-bold">{data.summary.total_transfers.toLocaleString()}</div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-gray-500">To charters</div>
          <div className="text-2xl font-bold">{formatPercent(data.charter_breakdown.charter_percent)}</div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-gray-500">To higher-rated</div>
          <div className="text-2xl font-bold">{formatPercent(data.rating_shift.higher_percent)}</div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-gray-500">
            Within {data.distance.neighborhood_radius_miles} miles
          </div>
          <div className="text-2xl font-bold">{formatPercent(data.distance.within_radius_percent)}</div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-bold">Transfer flows (Sankey)</h3>
            <span className="text-xs text-gray-500">
              Min {data.sankey.min_transfer_count} transfers
            </span>
          </div>
          {data.sankey.links.length === 0 ? (
            <div className="text-sm text-gray-400 text-center py-12">No flow links available.</div>
          ) : (
            <div className="h-[360px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <Sankey
                  data={data.sankey}
                  nodePadding={20}
                  nodeWidth={12}
                  linkCurvature={0.5}
                  iterations={32}
                  node={(props) => <SankeyNode {...props} />}
                >
                  <Tooltip content={<SankeyTooltip />} />
                </Sankey>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-bold">Primary destinations map</h3>
            <span className="text-xs text-gray-500">{data.map.flows.length} flows</span>
          </div>
          {data.map.flows.length === 0 ? (
            <div className="text-sm text-gray-400 text-center py-12">No map flows available.</div>
          ) : (
            <MapBox
              center={[31.9686, -99.9018]}
              zoom={6}
              markers={flowMarkers}
              lines={flowLines}
              className="h-[360px] w-full rounded-lg border border-gray-200"
              scrollWheelZoom={false}
              clusterMarkers={false}
            />
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-4">
          <h3 className="font-bold mb-3">Charter vs traditional</h3>
          {charterShare.length === 0 ? (
            <div className="text-sm text-gray-400 text-center py-12">No transfer data.</div>
          ) : (
            <div className="h-[260px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={charterShare} dataKey="value" nameKey="name" outerRadius={90}>
                    {charterShare.map((entry, index) => (
                      <Cell key={entry.name} fill={SHARE_COLORS[index % SHARE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: any) => value?.toLocaleString()} />
                  <Legend verticalAlign="bottom" height={28} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card className="p-4">
          <h3 className="font-bold mb-3">Rating shifts</h3>
          {ratingShift.length === 0 ? (
            <div className="text-sm text-gray-400 text-center py-12">No rating data.</div>
          ) : (
            <div className="h-[260px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={ratingShift} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip formatter={(value: any) => value?.toLocaleString()} />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {ratingShift.map((entry) => (
                      <Cell key={entry.name} fill={FLOW_COLORS[entry.name.toLowerCase()] || '#9ca3af'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      </div>

      <Card className="p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-bold">Distance distribution</h3>
          <span className="text-xs text-gray-500">
            Avg {data.distance.average_miles ?? 'n/a'} miles (n={data.distance.distance_count.toLocaleString()})
          </span>
        </div>
        {distanceBuckets.length === 0 ? (
          <div className="text-sm text-gray-400 text-center py-12">No distance data.</div>
        ) : (
          <div className="h-[260px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={distanceBuckets} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip formatter={(value: any) => value?.toLocaleString()} />
                <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>
    </div>
  );
}
