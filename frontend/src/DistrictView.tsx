import { useState, useEffect } from 'react';
import { Card } from './components/Card';
import { DistrictSummary } from './types';
import { MapBox } from './components/MapBox';
import { Loader2 } from 'lucide-react';
import { CompareButton } from './components/CompareButton';
import { api } from './services/api';
import { VirtualizedList } from './components/VirtualizedList';

interface DistrictViewProps {
  district: DistrictSummary;
  onCampusClick: (id: string) => void;
}

export function DistrictView({ district, onCampusClick }: DistrictViewProps) {
  const [mapData, setMapData] = useState<{
    boundary: any;
    markers: any[];
    bounds?: [number, number, number, number];
  } | null>(null);
  const [loadingMap, setLoadingMap] = useState(false);

  useEffect(() => {
    let active = true;
    async function fetchMapData() {
      if (!district.district_number) return;

      setLoadingMap(true);
      try {
        const result = await api.findCampusesInDistrict(district.district_number);

        const payload = result.payload || result; // Handle raw payload or wrapper

        let boundary = null;
        if (payload.district && payload.district.geometry) {
          boundary = payload.district.geometry;
        }

        const bounds =
          payload.district &&
            Array.isArray(payload.district.geometry_bounds) &&
            payload.district.geometry_bounds.length === 4
            ? payload.district.geometry_bounds
            : undefined;

        const markers = [];
        if (payload.geojson && payload.geojson.features) {
          for (const feature of payload.geojson.features) {
            if (feature.geometry && feature.geometry.type === 'Point') {
              const [lon, lat] = feature.geometry.coordinates;
              markers.push({
                lat,
                lon,
                title: feature.properties.name,
                description: `Rating: ${feature.properties.overall_rating_2025 || feature.properties.rating || 'N/A'}`,
                rating: feature.properties.overall_rating_2025 || feature.properties.rating || null,
                // We could pass campus_number to link clicks later
              });
            }
          }
        }

        if (active) {
          setMapData({ boundary, markers, bounds });
        }

      } catch (e) {
        console.error("Failed to load map data", e);
      } finally {
        if (active) {
          setLoadingMap(false);
        }
      }
    }

    fetchMapData();
    return () => {
      active = false;
    };
  }, [district.district_number]);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold">{district.name}</h1>
          <p className="text-gray-600">District #{district.district_number}</p>
        </div>
      </div>

      <div className="h-[300px] w-full bg-gray-50 rounded-lg border border-gray-200 overflow-hidden relative">
        {loadingMap && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/50 z-10">
            <Loader2 className="h-6 w-6 animate-spin text-gray-500" />
          </div>
        )}

        {mapData ? (
          <MapBox
            center={district.location ? [district.location.lat!, district.location.lon!] : [31.9686, -99.9018]} // Fallback to Texas center
            zoom={district.location ? 10 : 6}
            boundary={mapData.boundary}
            bounds={mapData.bounds}
            markers={mapData.markers}
            className="h-full w-full"
          />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400">
            {district.location ? 'Loading map...' : 'No location data available'}
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Card className="p-4">
          <h3 className="font-semibold text-gray-500 mb-1">Rating</h3>
          <p className="text-2xl font-bold">{district.rating || 'N/A'}</p>
        </Card>
        <Card className="p-4">
          <h3 className="font-semibold text-gray-500 mb-1">Total Enrollment</h3>
          <p className="text-2xl font-bold">{district.enrollment?.toLocaleString() || 'N/A'}</p>
        </Card>
      </div>

      {district.campuses && (
        <div className="space-y-2">
          <h3 className="font-bold text-lg">Campuses ({district.campuses.length})</h3>
          <VirtualizedList
            items={district.campuses}
            itemHeight={76}
            maxHeight={520}
            className="w-full"
            itemKey={(campus) => campus.campus_number || campus.name}
            renderItem={(campus) => (
              <Card
                key={campus.campus_number}
                className="p-3 hover:bg-gray-50 cursor-pointer transition-colors group"
                onClick={() => onCampusClick(campus.campus_number)}
              >
                <div className="flex justify-between items-center">
                  <div>
                    <div className="font-medium">{campus.name}</div>
                    <div className="text-sm text-gray-500">
                      {campus.grade_range} • {campus.rating || 'NR'}
                    </div>
                  </div>
                  <div className="ml-2">
                    <CompareButton id={campus.campus_number} name={campus.name} />
                  </div>
                </div>
              </Card>
            )}
          />
        </div>
      )}
    </div>
  );
}
