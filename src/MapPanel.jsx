import React, { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { useUICommand } from './contexts/UICommandContext';
import SEGMENT_COORDS from './segment_data.json';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

const SEGMENT_MIDPOINTS = Object.fromEntries(
  Object.entries(SEGMENT_COORDS).map(([id, coords]) => {
    const mid = coords[Math.floor(coords.length / 2)];
    return [id, { lat: mid[0], lng: mid[1] }];
  })
);

const PULSE_COLORS = { green: '#22c55e', yellow: '#facc15', amber: '#f59e0b', red: '#ef4444' };

function MapController({ mapFlyTo }) {
  const map = useMap();
  const lastTs = useRef(null);
  useEffect(() => {
    if (!mapFlyTo || mapFlyTo.ts === lastTs.current) return;
    lastTs.current = mapFlyTo.ts;
    const pt = SEGMENT_MIDPOINTS[mapFlyTo.segmentId];
    if (pt) map.flyTo([pt.lat, pt.lng], 15, { duration: 1.2 });
  }, [mapFlyTo, map]);
  return null;
}

function AnnotationMarker({ annotation }) {
  const icon = L.divIcon({
    className: 'annotation-icon border-10 border-yellow-700',
    html: `<div class="annotation-bubble">${annotation.text}</div>`,
    iconAnchor: [0, 0],
  });
  return <Marker position={[annotation.lat, annotation.lng]} icon={icon} interactive={false} />;
}

export default function MapPanel({ statusData }) {
  const { pulseSegments, mapFlyTo, overlayMode, annotations, activeSegment } = useUICommand();
  const now = Date.now();

  const getStyle = (id) => {
    const pulse = pulseSegments[id];
    if (pulse?.expiresAt > now) return { color: PULSE_COLORS[pulse.color] ?? '#f59e0b', weight: 9, opacity: 1 };
    if (activeSegment === id) return { color: '#60a5fa', weight: 8, opacity: 1 };

    const seg = statusData?.[id];
    if (seg) {
      if (overlayMode === 'risk') {
        const r = seg.risk_score ?? 0;
        return { color: r > 0.6 ? '#ef4444' : r > 0.35 ? '#f59e0b' : r > 0.15 ? '#facc15' : '#22c55e', weight: 6, opacity: 0.9 };
      }
      if (overlayMode === 'speed') {
        const s = seg.avg_speed_kmh ?? 100;
        return { color: s < 40 ? '#ef4444' : s < 70 ? '#f59e0b' : s < 90 ? '#facc15' : '#22c55e', weight: 6, opacity: 0.9 };
      }
    }
    return { color: '#3b82f6', weight: 5, opacity: 0.85 };
  };

  const createLabel = (id) => L.divIcon({
    className: 'segment-label-icon',
    html: `<div class="seg-label${activeSegment === id ? ' active' : ''}">${id}</div>`,
    iconSize: [30, 20],
    iconAnchor: [15, 10],
  });

  return (
    <div className="flex-1 relative" style={{ isolation: 'isolate' }}>
      <MapContainer center={[43.722, -79.49]} zoom={13} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />

        {Object.entries(SEGMENT_COORDS).map(([id, coords]) => {
          const s = getStyle(id);
          const isPulsing = pulseSegments[id]?.expiresAt > now;
          return (
            <Polyline key={id} positions={coords}
              pathOptions={{ color: s.color, weight: s.weight, opacity: s.opacity, className: isPulsing ? 'pulse-polyline' : '' }} />
          );
        })}

        {Object.entries(SEGMENT_COORDS).map(([id, coords]) => {
          const mid = coords[Math.floor(coords.length / 2)];
          return mid ? <Marker key={`lbl-${id}`} position={mid} icon={createLabel(id)} interactive={false} /> : null;
        })}

        {annotations.filter(a => a.expiresAt > now).map(a => <AnnotationMarker key={a.id} annotation={a} />)}
        <MapController mapFlyTo={mapFlyTo} />
      </MapContainer>

      {/* Overlay badge */}
      <div className="absolute bottom-4 right-4 z-[1000] bg-gray-900/80 backdrop-blur border border-gray-700 rounded-lg px-2.5 py-1 text-[10px] font-bold text-gray-400 uppercase tracking-widest pointer-events-none">
        {overlayMode} overlay
      </div>
    </div>
  );
}
