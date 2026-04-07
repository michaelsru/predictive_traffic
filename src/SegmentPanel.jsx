import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchHistory } from './api';
import { useUICommand } from './contexts/UICommandContext';

const METRIC_COLORS = { speed: '#3b82f6', volume: '#8b5cf6', risk: '#f59e0b' };
const METRIC_LABEL  = { speed: 'km/h', volume: 'proxy veh', risk: 'risk 0–1' };

const SEV_TEXT   = { critical: 'text-red-400', warning: 'text-orange-400', watch: 'text-yellow-400', normal: 'text-emerald-400' };
const SEV_BORDER = { critical: 'border-red-600', warning: 'border-orange-500', watch: 'border-yellow-500', normal: 'border-gray-700' };

function Sparkline({ data, color }) {
  if (!data || data.length < 2) return <div className="text-[10px] text-gray-600 italic">No data</div>;
  const W = 160, H = 40;
  const max = Math.max(...data), min = Math.min(...data), range = max - min || 1;
  const pts = data.map((v, i) => [
    (i / (data.length - 1)) * W,
    H - ((v - min) / range) * (H - 6) - 3,
  ]);
  const ptStr = pts.map(([x, y]) => `${x},${y}`).join(' ');
  const area  = `${pts[0][0]},${H} ${ptStr} ${pts[pts.length - 1][0]},${H}`;
  const [lx, ly] = pts[pts.length - 1];
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="overflow-visible">
      <polygon points={area} fill={color} fillOpacity="0.12" />
      <polyline points={ptStr} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" />
      <circle cx={lx} cy={ly} r="3" fill={color} />
    </svg>
  );
}

function SegmentCard({ segmentId, data, isActive, activeMetric, timeWindowMins }) {
  const limit = Math.min(Math.ceil(timeWindowMins * 15), 30);
  const { data: history = [] } = useQuery({
    queryKey: ['history', segmentId, limit],
    queryFn: () => fetchHistory(segmentId, limit),
    refetchInterval: 4000,
  });

  if (!data) return (
    <div className="rounded-xl bg-gray-800/40 border border-gray-700/50 p-3 text-xs text-gray-500 italic">
      Loading {segmentId}…
    </div>
  );

  const speedData  = history.map(h => h.avg_speed_kmh);
  const volumeData = history.map(h => Math.max(0, 120 - h.avg_speed_kmh));
  const riskData   = history.map(h => Math.min(1, (h.speed_stddev ?? 5) / 20));
  const chartData  = activeMetric === 'speed' ? speedData : activeMetric === 'volume' ? volumeData : riskData;
  const color      = METRIC_COLORS[activeMetric] ?? '#3b82f6';

  const currentDisplay = activeMetric === 'risk'
    ? `${((data.risk_score ?? 0) * 100).toFixed(0)}%`
    : `${data.avg_speed_kmh?.toFixed(1)} km/h`;

  const trendIcon = data.trend === 'deteriorating' ? '↘' : data.trend === 'improving' ? '↗' : '→';

  return (
    <div className={`rounded-xl border p-3 transition-all duration-200
      ${isActive ? 'bg-blue-950/40 border-blue-500/60 shadow-lg shadow-blue-900/20' : `bg-gray-800/40 ${SEV_BORDER[data.severity] ?? 'border-gray-700/50'}`}`}>

      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <span className={`text-sm font-black ${SEV_TEXT[data.severity] ?? 'text-blue-400'}`}>{segmentId}</span>
        <span className="text-sm font-bold text-gray-200">{currentDisplay}</span>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-1 mb-2">
        {[
          ['Risk',  `${((data.risk_score ?? 0) * 100).toFixed(0)}%`],
          ['Trend', `${trendIcon} ${data.trend ?? 'stable'}`],
          ['CUSUM', `${((data.cusum_upper ?? 0) * 100).toFixed(0)}%`],
        ].map(([label, val]) => (
          <div key={label} className="flex flex-col">
            <span className="text-[9px] text-gray-500 uppercase">{label}</span>
            <span className="text-[10px] text-gray-300 font-mono leading-tight">{val}</span>
          </div>
        ))}
      </div>

      {/* Sparkline */}
      <div className="h-10">
        <Sparkline data={chartData} color={color} />
      </div>
      <div className="text-[9px] text-gray-600 mt-0.5">{activeMetric} · {METRIC_LABEL[activeMetric]}</div>
    </div>
  );
}

export default function SegmentPanel({ statusData }) {
  const { activeSegment, activeMetric, timeWindowMins } = useUICommand();
  // Derive segment list dynamically from live data, sorted numerically (S1, S2, ... S20)
  const SEGMENTS = Object.keys(statusData || {}).sort(
    (a, b) => parseInt(a.slice(1)) - parseInt(b.slice(1))
  );

  const sorted = [...SEGMENTS].sort((a, b) => {
    if (a === activeSegment) return -1;
    if (b === activeSegment) return 1;
    return (statusData?.[b]?.risk_score ?? 0) - (statusData?.[a]?.risk_score ?? 0);
  });

  return (
    <div className="w-52 shrink-0 flex flex-col bg-gray-900 border-l border-gray-800 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-gray-800 shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-blue-400 text-xs">📊</span>
          <span className="text-xs font-bold text-gray-300 uppercase tracking-widest">Segments</span>
        </div>
        <span className="text-[9px] text-gray-500 font-mono">{activeMetric} · {timeWindowMins}m</span>
      </div>

      <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-2">
        {sorted.map(seg => (
          <SegmentCard
            key={seg}
            segmentId={seg}
            data={statusData?.[seg]}
            isActive={activeSegment === seg}
            activeMetric={activeMetric}
            timeWindowMins={timeWindowMins}
          />
        ))}
      </div>
    </div>
  );
}
