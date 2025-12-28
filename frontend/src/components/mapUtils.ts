import L from 'leaflet';

const LAT_LIMIT = 90;
const LON_LIMIT = 180;

export function isLikelyWebMercator(lon: number, lat: number) {
    return Math.abs(lon) > LON_LIMIT || Math.abs(lat) > LAT_LIMIT;
}

export function unprojectWebMercator(lon: number, lat: number) {
    const latLng = L.CRS.EPSG3857.unproject(L.point(lon, lat));
    return { lat: latLng.lat, lon: latLng.lng };
}

function findFirstCoord(coords: any): [number, number] | null {
    if (!coords) {
        return null;
    }
    if (typeof coords[0] === 'number' && typeof coords[1] === 'number') {
        return [coords[0], coords[1]];
    }
    if (Array.isArray(coords)) {
        for (const item of coords) {
            const found = findFirstCoord(item);
            if (found) {
                return found;
            }
        }
    }
    return null;
}

function convertCoordsToLatLng(coords: any): any {
    if (!Array.isArray(coords)) {
        return coords;
    }
    if (typeof coords[0] === 'number' && typeof coords[1] === 'number') {
        const converted = unprojectWebMercator(coords[0], coords[1]);
        return [converted.lon, converted.lat];
    }
    return coords.map((item) => convertCoordsToLatLng(item));
}

function findGeoJSONSample(geojson: any): [number, number] | null {
    if (!geojson || typeof geojson !== 'object') {
        return null;
    }
    if (geojson.type === 'FeatureCollection' && Array.isArray(geojson.features)) {
        for (const feature of geojson.features) {
            const found = findGeoJSONSample(feature);
            if (found) {
                return found;
            }
        }
        return null;
    }
    if (geojson.type === 'Feature' && geojson.geometry) {
        return findGeoJSONSample(geojson.geometry);
    }
    if (geojson.coordinates) {
        return findFirstCoord(geojson.coordinates);
    }
    return null;
}

export function normalizeGeoJSON(geojson: any): any {
    if (!geojson || typeof geojson !== 'object') {
        return geojson;
    }
    const coordsSample = findGeoJSONSample(geojson);
    const isWebMercator = coordsSample
        ? isLikelyWebMercator(coordsSample[0], coordsSample[1])
        : false;
    if (!isWebMercator) {
        return geojson;
    }

    if (geojson.type === 'FeatureCollection' && Array.isArray(geojson.features)) {
        return {
            ...geojson,
            features: geojson.features.map((feature: any) => normalizeGeoJSON(feature))
        };
    }
    if (geojson.type === 'Feature' && geojson.geometry) {
        return {
            ...geojson,
            geometry: normalizeGeoJSON(geojson.geometry)
        };
    }
    if (geojson.coordinates) {
        return {
            ...geojson,
            coordinates: convertCoordsToLatLng(geojson.coordinates)
        };
    }
    return geojson;
}

export function normalizeRating(value?: string | number) {
    if (value === null || value === undefined) return '';
    if (typeof value === 'number') return String(value);
    return value;
}

export function buildPointFeatureCollection(markers: Array<{ lat: number; lon: number; title: string; description?: string; rating?: string | number; color?: string; }>) {
    return {
        type: 'FeatureCollection',
        features: markers.map((marker) => {
            const properties: Record<string, any> = {
                title: marker.title,
                description: marker.description || '',
                rating: normalizeRating(marker.rating)
            };
            if (marker.color) {
                properties.color = marker.color;
            }
            return {
                type: 'Feature',
                geometry: {
                    type: 'Point',
                    coordinates: [marker.lon, marker.lat]
                },
                properties
            };
        })
    };
}

export function buildBoundaryFeatureCollection(boundary: any) {
    if (!boundary) {
        return { type: 'FeatureCollection', features: [] };
    }
    if (boundary.type === 'FeatureCollection' && Array.isArray(boundary.features)) {
        return boundary;
    }
    if (boundary.type === 'Feature' && boundary.geometry) {
        return { type: 'FeatureCollection', features: [boundary] };
    }
    if (boundary.type && boundary.coordinates) {
        return {
            type: 'FeatureCollection',
            features: [
                {
                    type: 'Feature',
                    geometry: boundary,
                    properties: { kind: 'district' }
                }
            ]
        };
    }
    return { type: 'FeatureCollection', features: [] };
}

export function buildLineFeatureCollection(
    lines: Array<{
        from: { lat: number; lon: number };
        to: { lat: number; lon: number };
        count?: number;
        color?: string;
        label?: string;
    }>
) {
    if (!lines || lines.length === 0) {
        return { type: 'FeatureCollection', features: [] };
    }
    return {
        type: 'FeatureCollection',
        features: lines.map((line, index) => ({
            type: 'Feature',
            geometry: {
                type: 'LineString',
                coordinates: [
                    [line.from.lon, line.from.lat],
                    [line.to.lon, line.to.lat]
                ]
            },
            properties: {
                id: index,
                count: line.count || 0,
                color: line.color || '',
                label: line.label || ''
            }
        }))
    };
}
