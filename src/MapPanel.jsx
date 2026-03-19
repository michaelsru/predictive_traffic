import React, { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Fix for default marker icons in react-leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

const SEGMENT_COORDS = {
  "S1": [[43.7280, -79.5120], [43.7265, -79.5280]], // Weston Rd to 400
  "S2": [[43.7265, -79.5280], [43.7255, -79.5420]], // 400 to Black Creek
  "S3": [[43.7255, -79.5420], [43.7242, -79.5580]], // Black Creek to Dufferin
  "S4": [[43.7242, -79.5580], [43.7228, -79.5740]], // Dufferin to Keele
  "S5": [[43.7228, -79.5740], [43.7210, -79.5900]], // Keele to Allen (approx)
};

const COLOR_MAP = {
  "green": "#10b981",
  "yellow": "#facc15",
  "amber": "#f59e0b",
  "red": "#ef4444"
};

function MapController({ activeAnchor }) {
  const map = useMap();
  
  useEffect(() => {
    if (activeAnchor) {
      map.flyTo([activeAnchor.lat, activeAnchor.lng], 15, {
        duration: 1.5
      });
    } else {
      // Reset to overview
      map.flyTo([43.7255, -79.5420], 13, {
        duration: 1.5
      });
    }
  }, [activeAnchor, map]);
  
  return null;
}

export default function MapPanel({ highlights, activeAnchor, talkingPoints }) {
  const getSegmentStyle = (segmentId) => {
    const highlight = highlights.find(h => h.segment_id === segmentId);
    if (!highlight) return { color: '#3b82f6', weight: 5, className: '' };
    
    return {
      color: COLOR_MAP[highlight.color] || '#3b82f6',
      weight: 8,
      className: highlight.pulse ? 'pulse-polyline' : ''
    };
  };

  const createNumberedIcon = (number) => {
    return L.divIcon({
      className: 'custom-numbered-icon',
      html: `<div>${number}</div>`,
      iconSize: [30, 30],
      iconAnchor: [15, 30]
    });
  };

  return (
    <div className="map-panel">
      <MapContainer center={[43.7255, -79.5420]} zoom={13} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        
        {Object.entries(SEGMENT_COORDS).map(([id, coords]) => {
          const style = getSegmentStyle(id);
          return (
            <Polyline 
              key={id} 
              positions={coords} 
              pathOptions={{ color: style.color, weight: style.weight, className: style.className }} 
            />
          );
        })}

        {talkingPoints && talkingPoints.map(tp => (
          tp.anchor && (
            <Marker 
              key={tp.id} 
              position={[tp.anchor.lat, tp.anchor.lng]}
              icon={createNumberedIcon(tp.id)}
            >
              <Popup>{tp.text}</Popup>
            </Marker>
          )
        ))}
        
        <MapController activeAnchor={activeAnchor} />
      </MapContainer>
    </div>
  );
}
