import React, { useEffect, useState } from 'react';
import { fetchHistory } from './api';

function Sparkline({ data }) {
  if (!data || data.length === 0) return null;
  
  const width = 200;
  const height = 40;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  
  const points = data.map((val, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((val - min) / range) * height;
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg width={width} height={height} className="sparkline">
      <polyline points={points} fill="none" stroke="#3b82f6" strokeWidth="2" />
    </svg>
  );
}

function SegmentCard({ segmentId, data }) {
  const [history, setHistory] = useState([]);

  useEffect(() => {
    const loadHistory = async () => {
      try {
        const histData = await fetchHistory(segmentId);
        setHistory(histData.map(d => d.avg_speed_kmh));
      } catch (err) {
        console.error(err);
      }
    };
    loadHistory();
    const interval = setInterval(loadHistory, 10000);
    return () => clearInterval(interval);
  }, [segmentId]);

  if (!data) return <div className="segment-card loading">Loading {segmentId}...</div>;

  return (
    <div className="segment-card">
      <div className="segment-header">
        <h3>{segmentId}</h3>
        <span className="speed">{data.avg_speed_kmh.toFixed(1)} km/h</span>
      </div>
      <div className="segment-stats">
        <div className="stat">
          <span className="label">StdDev</span>
          <span className="value">{data.speed_stddev.toFixed(2)}</span>
        </div>
        <div className="stat">
          <span className="label">Var Ratio</span>
          <span className="value">{data.variance_ratio.toFixed(2)}x</span>
        </div>
      </div>
      <div className="sparkline-container">
        <Sparkline data={history} />
      </div>
    </div>
  );
}

export default function SegmentPanel({ statusData }) {
  const segments = ["S1", "S2", "S3", "S4", "S5"];
  
  return (
    <div className="segment-panel">
      <h2>Live Segments</h2>
      <div className="segment-list">
        {segments.map(seg => (
          <SegmentCard key={seg} segmentId={seg} data={statusData[seg]} />
        ))}
      </div>
    </div>
  );
}
