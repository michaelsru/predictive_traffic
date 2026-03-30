import React from 'react';
import { useUICommand } from './contexts/UICommandContext';

export default function KpiBar({ statusData }) {
  const { kpiPulse } = useUICommand();
  const now = Date.now();

  const segments = Object.values(statusData || {});
  if (segments.length === 0) {
    return (
      <div className="flex items-center gap-6 flex-1 min-w-0">
        <span className="text-sm font-bold text-blue-400 tracking-wide whitespace-nowrap">Hwy 401 TMC — Westbound</span>
        <span className="text-xs text-gray-500">Loading…</span>
      </div>
    );
  }

  const avgSpeed = segments.reduce((s, seg) => s + (seg.avg_speed_kmh ?? 0), 0) / segments.length;
  const worst = segments.reduce((a, b) => (b.risk_score ?? 0) > (a.risk_score ?? 0) ? b : a, segments[0]);
  const alertCount = segments.filter(s => ['critical', 'warning', 'watch'].includes(s.severity)).length;

  const isPulsing = (kpi) => kpiPulse?.kpi === kpi && kpiPulse.expiresAt > now;

  const speedColor = avgSpeed >= 80 ? 'text-emerald-400' : avgSpeed >= 50 ? 'text-yellow-400' : 'text-red-400';
  const alertColor = alertCount === 0 ? 'text-emerald-400' : alertCount <= 2 ? 'text-yellow-400' : 'text-red-400';
  const severityTextColor = { critical: 'text-red-400', warning: 'text-orange-400', watch: 'text-yellow-400', normal: 'text-emerald-400' };
  const severityBg = { critical: 'bg-red-900/60', warning: 'bg-orange-900/60', watch: 'bg-yellow-900/60', normal: 'bg-emerald-900/60' };

  const card = (kpi, children) => (
    <div className={`flex flex-col px-3 py-1 rounded-lg border border-gray-700/60 bg-gray-800/60 backdrop-blur min-w-[120px]
      ${isPulsing(kpi) ? 'kpi-pulse border-blue-400/60' : ''}`}>
      {children}
    </div>
  );

  return (
    <div className="flex items-center gap-3 flex-1 min-w-0">
      <span className="text-sm font-bold text-blue-400 tracking-wide whitespace-nowrap mr-2">Hwy 401 TMC</span>

      {card('avgSpeed', <>
        <span className="text-[10px] text-gray-500 uppercase tracking-widest">Corridor Speed</span>
        <span className={`text-base font-bold ${speedColor}`}>{avgSpeed.toFixed(1)} km/h</span>
      </>)}

      {card('worstSegment', <>
        <span className="text-[10px] text-gray-500 uppercase tracking-widest">Worst Segment</span>
        <span className={`text-base font-bold flex items-center gap-1 ${severityTextColor[worst?.severity] ?? 'text-gray-300'}`}>
          {worst?.segment_id}
          <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase ${severityBg[worst?.severity]}`}>
            {worst?.severity}
          </span>
        </span>
      </>)}

      {card('activeAlerts', <>
        <span className="text-[10px] text-gray-500 uppercase tracking-widest">Active Alerts</span>
        <span className={`text-base font-bold ${alertColor}`}>
          {alertCount}
          <span className="text-xs text-gray-500 font-normal ml-1">/ {segments.length} segs</span>
        </span>
      </>)}
    </div>
  );
}
