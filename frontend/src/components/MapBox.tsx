import React, { useEffect, useMemo, useRef, Suspense } from 'react';
import { MapContainer, TileLayer, Marker, Popup, GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster';
import {
    isLikelyWebMercator,
    unprojectWebMercator,
    normalizeGeoJSON,
    buildPointFeatureCollection,
    buildBoundaryFeatureCollection
} from './mapUtils';

// Fix for default Leaflet icons in Vite/Webpack
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

// Lazy load MapLibreView to avoid bundling maplibre-gl in the main chunk
const MapLibreView = React.lazy(() => import('./MapLibreView'));

const DefaultIcon = L.icon({
    iconUrl: icon,
    shadowUrl: iconShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

const BASE_TILE_URL =
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}';
const BASE_TILE_ATTRIBUTION =
    'Tiles &copy; Esri &mdash; Source: Esri, HERE, Garmin, FAO, NOAA, USGS';

function resolveRenderer(explicit?: 'leaflet' | 'webgl') {
    if (explicit) {
        return explicit;
    }
    const env = import.meta.env.VITE_TEADATA_MAP_RENDERER;
    if (typeof env === 'string' && env) {
        const normalized = env.toLowerCase();
        if (normalized === 'webgl') return 'webgl';
        if (normalized === 'leaflet') return 'leaflet';
    }
    try {
        const stored = window.localStorage.getItem('teadata.mapRenderer');
        if (stored) {
            const normalized = stored.toLowerCase();
            if (normalized === 'webgl' || normalized === 'leaflet') {
                return normalized as 'webgl' | 'leaflet';
            }
        }
    } catch {
        // ignore storage errors
    }
    // Default to leaflet for performance in restricted environments like ChatGPT
    return 'leaflet';
}

interface MapBoxProps {
    center: [number, number];
    zoom?: number;
    markers?: Array<{
        lat: number;
        lon: number;
        title: string;
        description?: string;
        rating?: string | number;
        color?: string; // Future: support custom colored icons
    }>;
    bounds?: [number, number, number, number]; // [minLon, minLat, maxLon, maxLat]
    boundary?: any; // GeoJSON object
    className?: string;
    scrollWheelZoom?: boolean;
    renderer?: 'leaflet' | 'webgl';
    clusterMarkers?: boolean;
}

// Component to auto-fit bounds if boundary is present
function BoundsFitter({
    bounds,
    boundary,
    markers
}: {
    bounds?: [number, number, number, number];
    boundary?: any;
    markers?: any[];
}) {
    const map = useMap();

    useEffect(() => {
        if (bounds && bounds.length === 4) {
            const [minLon, minLat, maxLon, maxLat] = bounds;
            const latLngBounds = L.latLngBounds([minLat, minLon], [maxLat, maxLon]);
            if (latLngBounds.isValid()) {
                map.fitBounds(latLngBounds, { padding: [20, 20] });
                return;
            }
        }

        if (boundary) {
            try {
                const layer = L.geoJSON(boundary);
                const bounds = layer.getBounds();
                if (bounds.isValid()) {
                    map.fitBounds(bounds, { padding: [20, 20] });
                }
            } catch (e) {
                console.warn("Failed to fit bounds to boundary", e);
            }
        } else if (markers && markers.length > 1) {
             const bounds = L.latLngBounds(markers.map(m => [m.lat, m.lon]));
             if (bounds.isValid()) {
                 map.fitBounds(bounds, { padding: [50, 50] });
             }
        }
    }, [bounds, boundary, markers, map]);

    return null;
}

function ClusteredMarkers({
    markers
}: {
    markers: Array<{ lat: number; lon: number; title: string; description?: string }>;
}) {
    const map = useMap();
    const clusterRef = useRef<L.LayerGroup | null>(null);

    useEffect(() => {
        if (!map) {
            return;
        }

        if (!clusterRef.current) {
            // @ts-ignore leaflet.markercluster augments L with markerClusterGroup
            clusterRef.current = L.markerClusterGroup({
                chunkedLoading: true,
                showCoverageOnHover: false
            });
            map.addLayer(clusterRef.current);
        }

        const group = clusterRef.current;
        if (!group) {
            return;
        }

        // @ts-ignore markerClusterGroup supports clearLayers
        group.clearLayers();
        markers.forEach((marker) => {
            const instance = L.marker([marker.lat, marker.lon]);
            if (marker.title || marker.description) {
                const popup = `
                    <div class="font-semibold">${marker.title || ''}</div>
                    ${marker.description ? `<div class="text-sm">${marker.description}</div>` : ''}
                `;
                instance.bindPopup(popup);
            }
            // @ts-ignore markerClusterGroup supports addLayer
            group.addLayer(instance);
        });
    }, [map, markers]);

    useEffect(() => {
        return () => {
            if (clusterRef.current && map) {
                map.removeLayer(clusterRef.current);
                clusterRef.current = null;
            }
        };
    }, [map]);

    return null;
}

export function MapBox({ 
    center, 
    zoom = 13, 
    markers = [], 
    bounds,
    boundary, 
    className = "h-[300px] w-full rounded-lg shadow-sm border border-gray-200",
    scrollWheelZoom = false,
    renderer,
    clusterMarkers = true
}: MapBoxProps) {
    const normalizedCenter = useMemo(() => {
        const [lat, lon] = center;
        if (isLikelyWebMercator(lon, lat)) {
            const converted = unprojectWebMercator(lon, lat);
            return [converted.lat, converted.lon] as [number, number];
        }
        return center;
    }, [center[0], center[1]]);

    const normalizedMarkers = useMemo(() => {
        return markers.map((marker) => {
            if (isLikelyWebMercator(marker.lon, marker.lat)) {
                const converted = unprojectWebMercator(marker.lon, marker.lat);
                return {
                    ...marker,
                    lat: converted.lat,
                    lon: converted.lon
                };
            }
            return marker;
        });
    }, [markers]);

    const normalizedBoundary = useMemo(() => normalizeGeoJSON(boundary), [boundary]);

    const normalizedBounds = useMemo(() => {
        if (!bounds || bounds.length !== 4) {
            return bounds;
        }
        const [minLon, minLat, maxLon, maxLat] = bounds;
        if (!isLikelyWebMercator(minLon, minLat) && !isLikelyWebMercator(maxLon, maxLat)) {
            return bounds;
        }
        const sw = unprojectWebMercator(minLon, minLat);
        const ne = unprojectWebMercator(maxLon, maxLat);
        return [sw.lon, sw.lat, ne.lon, ne.lat] as [number, number, number, number];
    }, [bounds?.[0], bounds?.[1], bounds?.[2], bounds?.[3]]);

    const resolvedRenderer = useMemo(() => resolveRenderer(renderer), [renderer]);
    const shouldCluster = clusterMarkers && normalizedMarkers.length > 50;

    // Ensure center is valid
    if (!normalizedCenter || isNaN(normalizedCenter[0]) || isNaN(normalizedCenter[1])) {
        return (
            <div className={`${className} bg-gray-100 flex items-center justify-center text-gray-500`}>
                Map unavailable (Invalid Coordinates)
            </div>
        );
    }

    if (resolvedRenderer === 'webgl') {
        return (
            <Suspense fallback={<div className={`${className} bg-gray-100 animate-pulse`} />}>
                <MapLibreView
                    center={normalizedCenter}
                    zoom={zoom}
                    markers={normalizedMarkers}
                    boundary={normalizedBoundary}
                    bounds={normalizedBounds}
                    className={className}
                    scrollWheelZoom={scrollWheelZoom}
                />
            </Suspense>
        );
    }

    return (
        <MapContainer 
            center={normalizedCenter} 
            zoom={zoom} 
            scrollWheelZoom={scrollWheelZoom} 
            preferCanvas={true}
            className={className}
        >
            <TileLayer
                attribution={BASE_TILE_ATTRIBUTION}
                url={BASE_TILE_URL}
            />
            
            {shouldCluster ? (
                <ClusteredMarkers markers={normalizedMarkers} />
            ) : (
                normalizedMarkers.map((marker, idx) => (
                    <Marker key={idx} position={[marker.lat, marker.lon]}>
                        <Popup>
                            <div className="font-semibold">{marker.title}</div>
                            {marker.description && <div className="text-sm">{marker.description}</div>}
                        </Popup>
                    </Marker>
                ))
            )}

            {normalizedBoundary && (
                <GeoJSON 
                    data={normalizedBoundary} 
                    style={{
                        color: '#3b82f6', // blue-500
                        weight: 2,
                        opacity: 0.6,
                        fillOpacity: 0.1
                    }} 
                />
            )}

            <BoundsFitter bounds={normalizedBounds} boundary={normalizedBoundary} markers={normalizedMarkers} />
        </MapContainer>
    );
}
