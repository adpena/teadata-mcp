import { useEffect, useMemo, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { buildPointFeatureCollection, buildBoundaryFeatureCollection, buildLineFeatureCollection } from './mapUtils';

const BASE_TILE_URL =
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}';
const BASE_TILE_ATTRIBUTION =
    'Tiles &copy; Esri &mdash; Source: Esri, HERE, Garmin, FAO, NOAA, USGS';

const MAPLIBRE_STYLE = {
    version: 8,
    sources: {
        'raster-tiles': {
            type: 'raster',
            tiles: [BASE_TILE_URL],
            tileSize: 256,
            attribution: BASE_TILE_ATTRIBUTION
        }
    },
    layers: [
        {
            id: 'raster-tiles',
            type: 'raster',
            source: 'raster-tiles'
        }
    ]
} as const;

export default function MapLibreView({
    center,
    zoom,
    markers,
    boundary,
    bounds,
    className,
    scrollWheelZoom,
    lines
}: {
    center: [number, number];
    zoom: number;
    markers: Array<{
        lat: number;
        lon: number;
        title: string;
        description?: string;
        rating?: string | number;
        color?: string;
    }>;
    boundary?: any;
    bounds?: [number, number, number, number];
    className: string;
    scrollWheelZoom: boolean;
    lines?: Array<{
        id?: string;
        from: { lat: number; lon: number; title?: string };
        to: { lat: number; lon: number; title?: string };
        count?: number;
        color?: string;
        label?: string;
    }>;
}) {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const mapRef = useRef<maplibregl.Map | null>(null);
    const popupRef = useRef<maplibregl.Popup | null>(null);
    const [loaded, setLoaded] = useState(false);
    const fitKeyRef = useRef<string | null>(null);
    const eventsBoundRef = useRef(false);
    const centerKeyRef = useRef<string | null>(null);
    const zoomRef = useRef<number | null>(null);

    const pointData = useMemo(() => buildPointFeatureCollection(markers), [markers]);
    const boundaryData = useMemo(() => buildBoundaryFeatureCollection(boundary), [boundary]);
    const lineData = useMemo(() => buildLineFeatureCollection(lines || []), [lines]);

    useEffect(() => {
        if (!containerRef.current || mapRef.current) {
            return;
        }
        const map = new maplibregl.Map({
            container: containerRef.current,
            style: MAPLIBRE_STYLE as any,
            center: [center[1], center[0]],
            zoom,
            attributionControl: false
        });
        map.addControl(new maplibregl.AttributionControl({ compact: true }));
        mapRef.current = map;

        map.on('load', () => {
            setLoaded(true);
        });

        return () => {
            popupRef.current?.remove();
            map.remove();
            mapRef.current = null;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        const map = mapRef.current;
        if (!map) return;
        const nextCenterKey = `${center[0]}|${center[1]}`;
        if (centerKeyRef.current !== nextCenterKey) {
            map.setCenter([center[1], center[0]]);
            centerKeyRef.current = nextCenterKey;
        }
        if (zoomRef.current !== zoom) {
            map.setZoom(zoom);
            zoomRef.current = zoom;
        }
    }, [center, zoom]);

    useEffect(() => {
        const map = mapRef.current;
        if (!map || !loaded) return;

        const ratingColorExpression: any = [
            'match',
            ['upcase', ['to-string', ['coalesce', ['get', 'rating'], '']]],
            'A',
            '#22c55e',
            'B',
            '#84cc16',
            'C',
            '#fbbf24',
            'D',
            '#f97316',
            'F',
            '#ef4444',
            '#94a3b8'
        ];
        const colorExpression: any = [
            'case',
            ['has', 'color'],
            ['get', 'color'],
            ratingColorExpression
        ];

        const boundarySource = map.getSource('boundary') as maplibregl.GeoJSONSource | undefined;
        if (!boundarySource) {
            map.addSource('boundary', {
                type: 'geojson',
                data: boundaryData as any
            });
            map.addLayer({
                id: 'boundary-fill',
                type: 'fill',
                source: 'boundary',
                paint: {
                    'fill-color': '#3b82f6',
                    'fill-opacity': 0.1
                }
            });
            map.addLayer({
                id: 'boundary-line',
                type: 'line',
                source: 'boundary',
                paint: {
                    'line-color': '#3b82f6',
                    'line-width': 2,
                    'line-opacity': 0.6
                }
            });
        } else {
            boundarySource.setData(boundaryData as any);
        }

        const lineSource = map.getSource('transfer-lines') as maplibregl.GeoJSONSource | undefined;
        if (!lineSource) {
            map.addSource('transfer-lines', {
                type: 'geojson',
                data: lineData as any
            });
            map.addLayer({
                id: 'transfer-lines',
                type: 'line',
                source: 'transfer-lines',
                paint: {
                    'line-color': ['coalesce', ['get', 'color'], '#2563eb'],
                    'line-width': [
                        'interpolate',
                        ['linear'],
                        ['coalesce', ['get', 'count'], 0],
                        5,
                        1.5,
                        50,
                        3,
                        150,
                        5
                    ],
                    'line-opacity': 0.7
                }
            });
        } else {
            lineSource.setData(lineData as any);
        }

        const pointSource = map.getSource('campus-points') as maplibregl.GeoJSONSource | undefined;
        if (!pointSource) {
            map.addSource('campus-points', {
                type: 'geojson',
                data: pointData as any
            });
            map.addLayer({
                id: 'campus-points',
                type: 'circle',
                source: 'campus-points',
                paint: {
                    'circle-radius': 5,
                    'circle-color': colorExpression,
                    'circle-stroke-color': '#ffffff',
                    'circle-stroke-width': 1
                }
            });
            if (!eventsBoundRef.current) {
                map.on('click', 'campus-points', (event) => {
                    const features = event.features || [];
                    const feature = features[0] as any;
                    if (!feature) return;
                    const props = feature.properties || {};
                    const title = props.title || 'Campus';
                    const rating = props.rating || 'NR';
                    const description = props.description || '';
                    popupRef.current?.remove();
                    popupRef.current = new maplibregl.Popup({
                        closeButton: true,
                        closeOnClick: true
                    })
                        .setLngLat(event.lngLat)
                        .setHTML(
                            `<div class="font-semibold">${title}</div>${description
                                ? `<div class="text-sm">${description}</div>`
                                : ''
                            }<div class="text-xs mt-1">Rating: ${rating}</div>`
                        )
                        .addTo(map);
                });

                map.on('mouseenter', 'campus-points', () => {
                    map.getCanvas().style.cursor = 'pointer';
                });
                map.on('mouseleave', 'campus-points', () => {
                    map.getCanvas().style.cursor = '';
                });
                eventsBoundRef.current = true;
            }
        } else {
            pointSource.setData(pointData as any);
        }
    }, [boundaryData, pointData, lineData, loaded]);

    useEffect(() => {
        const map = mapRef.current;
        if (!map) return;
        if (scrollWheelZoom) {
            map.scrollZoom.enable();
        } else {
            map.scrollZoom.disable();
        }
    }, [scrollWheelZoom]);

    useEffect(() => {
        const map = mapRef.current;
        if (!map || !loaded) return;

        let fitBounds: [number, number, number, number] | null = null;
        if (bounds && bounds.length === 4) {
            fitBounds = bounds;
        } else if (markers.length > 1) {
            const lats = markers.map((m) => m.lat);
            const lons = markers.map((m) => m.lon);
            fitBounds = [
                Math.min(...lons),
                Math.min(...lats),
                Math.max(...lons),
                Math.max(...lats)
            ];
        }

        if (!fitBounds) return;
        const nextKey = fitBounds.join('|');
        if (fitKeyRef.current === nextKey) return;
        fitKeyRef.current = nextKey;

        map.fitBounds(
            [
                [fitBounds[0], fitBounds[1]],
                [fitBounds[2], fitBounds[3]]
            ],
            { padding: 32, maxZoom: 14, duration: 0 }
        );
    }, [bounds, markers, loaded]);

    return <div ref={containerRef} className={className} />;
}
