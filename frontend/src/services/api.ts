// Mock window.openai for local dev
if (typeof window !== 'undefined' && !window.openai) {
  window.openai = {
    callTool: async (name: string, args: any) => {
      console.log(`[Real API] Calling ${name}`, args);
      try {
        const response = await fetch(`/api/tool/${name}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(args)
        });
        const result = await response.json();
        if (result.status === 'error') {
          throw new Error(result.message);
        }
        return result.payload;
      } catch (e) {
        console.error("API Call failed", e);
        throw e;
      }
    }
  };
}

function isPerfEnabled() {
  if (typeof window === 'undefined') return false;
  const envFlag = import.meta.env.VITE_TEADATA_PERF_LOG;
  if (typeof envFlag === 'string') {
    const normalized = envFlag.toLowerCase();
    if (normalized === 'false' || normalized === '0') return false;
    if (normalized === 'true' || normalized === '1') return true;
  }
  try {
    const stored = window.localStorage.getItem('teadata.perf');
    if (stored !== null) {
      const normalized = stored.toLowerCase();
      return normalized === '1' || normalized === 'true';
    }
  } catch {
    return true;
  }
  return true;
}

function memorySnapshot() {
  const perf: any = typeof performance !== 'undefined' ? performance : null;
  if (!perf || !perf.memory) return null;
  return {
    used: perf.memory.usedJSHeapSize,
    total: perf.memory.totalJSHeapSize,
    limit: perf.memory.jsHeapSizeLimit
  };
}

function formatBytes(value: number | null) {
  if (value === null) return 'n/a';
  let size = value;
  for (const unit of ['B', 'KB', 'MB', 'GB']) {
    if (size < 1024 || unit === 'GB') {
      return `${size.toFixed(1)}${unit}`;
    }
    size /= 1024;
  }
  return `${size.toFixed(1)}GB`;
}

function summarizePayload(payload: any) {
  if (!payload || typeof payload !== 'object') return {};
  const features = Array.isArray(payload.geojson?.features)
    ? payload.geojson.features.length
    : 0;
  const campuses = Array.isArray(payload.campuses)
    ? payload.campuses.length
    : 0;
  const rows = Array.isArray(payload.table?.rows)
    ? payload.table.rows.length
    : 0;
  return { features, campuses, tableRows: rows };
}

async function callTool(name: string, args: any) {
  const perfEnabled = isPerfEnabled();
  const start = perfEnabled ? performance.now() : 0;
  const memBefore = perfEnabled ? memorySnapshot() : null;
  try {
    const result = await window.openai!.callTool(name, args);
    if (perfEnabled) {
      const memAfter = memorySnapshot();
      const durationMs = performance.now() - start;
      const summary = summarizePayload(result?.payload || result);
      console.info('[teadata] tool perf', {
        tool: name,
        durationMs: Number(durationMs.toFixed(1)),
        memoryBefore: memBefore
          ? {
              used: formatBytes(memBefore.used),
              total: formatBytes(memBefore.total),
              limit: formatBytes(memBefore.limit)
            }
          : null,
        memoryAfter: memAfter
          ? {
              used: formatBytes(memAfter.used),
              total: formatBytes(memAfter.total),
              limit: formatBytes(memAfter.limit)
            }
          : null,
        payload: summary
      });
    }
    return result;
  } catch (error) {
    if (perfEnabled) {
      const durationMs = performance.now() - start;
      console.info('[teadata] tool perf (error)', {
        tool: name,
        durationMs: Number(durationMs.toFixed(1)),
        memoryBefore: memBefore
          ? {
              used: formatBytes(memBefore.used),
              total: formatBytes(memBefore.total),
              limit: formatBytes(memBefore.limit)
            }
          : null
      });
    }
    throw error;
  }
}

export const api = {
  searchCampuses: async (query: string, status: string, rating: string = 'all', grade_level: string = 'all') => {
    return callTool('search_campuses', { query, status, rating, grade_level });
  },
  getCampusDetail: async (identifier: string) => {
    return callTool('get_campus_detail', { identifier });
  },
  getDistrictDetail: async (identifier: string) => {
    return callTool('get_district_detail', { identifier });
  },
  findCampusesInDistrict: async (districtId: string) => {
      // @ts-ignore
      return callTool('find_campuses_in_district_boundary', {
          district_identifier: districtId,
          response_profile: 'map',
          boundary_delivery: 'reference',
          include_geojson: true,
          limit: 200
      });
  },
  getNearbyCampuses: async (identifier: string) => {
      // @ts-ignore
      return callTool('get_nearby_campuses', {
          identifier,
          limit: 10,
          radius_miles: 5
      });
  },
  compareCampuses: async (ids: string[]) => {
      // @ts-ignore
      return callTool('compare_campuses', { identifiers: ids });
  }
};
