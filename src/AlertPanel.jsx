import React from 'react';
import { useUICommand, useUICommandDispatch } from './contexts/UICommandContext';

const severityBorder  = { critical: 'border-red-500',    warning: 'border-orange-500', watch: 'border-yellow-500', normal: 'border-emerald-500' };
const severityBg      = { critical: 'bg-red-950/70',     warning: 'bg-orange-950/70',  watch: 'bg-yellow-950/70',  normal: 'bg-emerald-950/70'  };
const severityText    = { critical: 'text-red-400',      warning: 'text-orange-400',   watch: 'text-yellow-400',   normal: 'text-emerald-400'   };
const severityBadgeBg = { critical: 'bg-red-800',        warning: 'bg-orange-800',     watch: 'bg-yellow-800',     normal: 'bg-emerald-800'     };

export default function AlertPanel({ statusData }) {
  const { expandedAlertId } = useUICommand();
  const dispatch = useUICommandDispatch();

  // Derive and sort segments numerically from live status data
  const SEGMENT_ORDER = Object.keys(statusData || {}).sort(
    (a, b) => parseInt(a.slice(1)) - parseInt(b.slice(1))
  );
  const alerts = SEGMENT_ORDER
    .map(id => statusData?.[id])
    .filter(seg => seg && ['critical', 'warning', 'watch'].includes(seg.severity));

  return (
    <div className="w-56 shrink-0 flex flex-col bg-gray-900 border-l border-gray-800 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2.5 border-b border-gray-800 shrink-0">
        <span className="text-yellow-400 text-sm">⚠</span>
        <span className="text-xs font-bold text-gray-300 uppercase tracking-widest">Alerts</span>
        {alerts.length > 0 && (
          <span className="ml-auto bg-red-700 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
            {alerts.length}
          </span>
        )}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-2">
        {alerts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-center">
            <span className="text-2xl">✓</span>
            <span className="text-xs text-gray-500">All segments nominal</span>
          </div>
        ) : alerts.map(seg => {
          const isExpanded = expandedAlertId === seg.segment_id;
          const sev = seg.severity || 'normal';
          return (
            <div
              key={seg.segment_id}
              className={`rounded-lg border cursor-pointer transition-all duration-200
                ${severityBorder[sev]} ${severityBg[sev]}`}
              onClick={() => dispatch({ type: 'expandAlert', segmentId: seg.segment_id })}
            >
              {/* Alert row */}
              <div className="flex items-center gap-2 px-2.5 py-2">
                <span className={`text-sm font-black ${severityText[sev]}`}>{seg.segment_id}</span>
                <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase ${severityBadgeBg[sev]} text-white`}>
                  {sev}
                </span>
                <span className="ml-auto text-[10px] text-gray-400 font-mono">
                  {((seg.risk_score ?? 0) * 100).toFixed(0)}%
                </span>
                <span className="text-gray-500 text-[10px]">{isExpanded ? '▲' : '▼'}</span>
              </div>

              {/* Expanded details */}
              {isExpanded && (
                <div className="px-2.5 pb-2.5 border-t border-white/5">
                  <div className="grid grid-cols-3 gap-1 mt-2">
                    {[
                      ['Speed',   `${seg.avg_speed_kmh?.toFixed(1)} km/h`],
                      ['Δ Base',  `${seg.baseline_delta_pct > 0 ? '+' : ''}${seg.baseline_delta_pct?.toFixed(1)}%`],
                      ['Trend',   seg.trend === 'deteriorating' ? '↘ Worse' : seg.trend === 'improving' ? '↗ Better' : '→ Stable'],
                      ['CUSUM',   `${((seg.cusum_upper ?? 0) * 100).toFixed(0)}%`],
                      ['VarRatio',`${seg.variance_ratio?.toFixed(2)}x`],
                      ['Spread',  (seg.propagation ?? 'none').replace(/_/g, ' ')],
                    ].map(([label, val]) => (
                      <div key={label} className="flex flex-col">
                        <span className="text-[9px] text-gray-500 uppercase">{label}</span>
                        <span className="text-[10px] text-gray-200 font-mono leading-tight">{val}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
