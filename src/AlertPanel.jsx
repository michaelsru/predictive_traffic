import React from 'react';
import { useUICommand, useUICommandDispatch } from './contexts/UICommandContext';

const severityBorder  = { critical: 'border-red-500',    warning: 'border-orange-500', watch: 'border-yellow-500', normal: 'border-emerald-500' };
const severityBg      = { critical: 'bg-red-950/70',     warning: 'bg-orange-950/70',  watch: 'bg-yellow-950/70',  normal: 'bg-emerald-950/70'  };
const severityText    = { critical: 'text-red-400',      warning: 'text-orange-400',   watch: 'text-yellow-400',   normal: 'text-emerald-400'   };
const severityBadgeBg = { critical: 'bg-red-800',        warning: 'bg-orange-800',     watch: 'bg-yellow-800',     normal: 'bg-emerald-800'     };

function speedLabel(speed, baseline) {
  const ratio = baseline > 0 ? speed / baseline : 1;
  if (ratio < 0.35) return 'Severely congested';
  if (ratio < 0.55) return 'Heavy congestion';
  if (ratio < 0.75) return 'Moderate slowdown';
  if (ratio < 0.90) return 'Minor slowdown';
  return 'Near normal';
}

function deltaLabel(pct) {
  if (pct >= 0) return `+${pct.toFixed(0)}% above baseline`;
  const abs = Math.abs(pct);
  if (abs >= 60) return `${abs.toFixed(0)}% below baseline`;
  if (abs >= 30) return `${abs.toFixed(0)}% below baseline`;
  return `${abs.toFixed(0)}% below baseline`;
}

function cusumLabel(cusum) {
  if (cusum >= 0.9) return 'Sustained drop detected';
  if (cusum >= 0.6) return 'Drift building up';
  if (cusum >= 0.3) return 'Early drift signal';
  return 'No sustained drift';
}

function varianceLabel(ratio) {
  if (ratio >= 3.5) return 'Highly erratic flow';
  if (ratio >= 2.5) return 'Unstable flow';
  if (ratio >= 1.5) return 'Slightly variable';
  return 'Smooth flow';
}

function propagationLabel(prop) {
  switch (prop) {
    case 'spreading_upstream':   return '⬅ Congestion spreading back';
    case 'spreading_downstream': return '➡ Congestion moving forward';
    case 'clearing':             return '✓ Neighbour congestion clearing';
    default:                     return 'Contained to this segment';
  }
}

function summaryLine(seg) {
  const speed = seg.avg_speed_kmh?.toFixed(0);
  const baseline = seg.baseline_avg_speed ?? 100;
  const condition = speedLabel(seg.avg_speed_kmh, baseline);
  const prop = seg.propagation ?? 'none';
  const propSuffix = prop === 'spreading_upstream' ? ', spreading back' : prop === 'spreading_downstream' ? ', spreading forward' : '';
  return `${speed} km/h — ${condition}${propSuffix}`;
}

export default function AlertPanel({ statusData }) {
  const { expandedAlertId } = useUICommand();
  const dispatch = useUICommandDispatch();

  const SEGMENT_ORDER = Object.keys(statusData || {}).sort(
    (a, b) => parseInt(a.slice(1)) - parseInt(b.slice(1))
  );
  const alerts = SEGMENT_ORDER
    .map(id => statusData?.[id])
    .filter(seg => seg && ['critical', 'warning', 'watch'].includes(seg.severity))
    .sort((a, b) => (b.risk_score ?? 0) - (a.risk_score ?? 0));

  return (
    <div className="w-60 shrink-0 flex flex-col bg-gray-900 border-l border-gray-800 overflow-hidden">
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
          const baseline = seg.baseline_avg_speed ?? 100;

          return (
            <div
              key={seg.segment_id}
              className={`rounded-lg border cursor-pointer transition-all duration-200
                ${severityBorder[sev]} ${severityBg[sev]}`}
              onClick={() => dispatch({ type: 'expandAlert', segmentId: seg.segment_id })}
            >
              {/* Collapsed row */}
              <div className="flex items-start gap-2 px-2.5 py-2">
                <div className="flex flex-col flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className={`text-sm font-black ${severityText[sev]}`}>{seg.segment_id}</span>
                    <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase ${severityBadgeBg[sev]} text-white`}>
                      {sev}
                    </span>
                  </div>
                  <span className="text-[10px] text-gray-300 mt-0.5 leading-tight">
                    {summaryLine(seg)}
                  </span>
                </div>
                <span className="text-gray-500 text-[10px] mt-0.5 shrink-0">{isExpanded ? '▲' : '▼'}</span>
              </div>

              {/* Expanded details */}
              {isExpanded && (
                <div className="px-2.5 pb-2.5 border-t border-white/5 pt-2 flex flex-col gap-1.5">

                  {/* Speed */}
                  <div className="flex flex-col">
                    <span className="text-[9px] text-gray-500 uppercase">Speed</span>
                    <span className={`text-[11px] font-semibold ${severityText[sev]}`}>
                      {seg.avg_speed_kmh?.toFixed(1)} km/h — {speedLabel(seg.avg_speed_kmh, baseline)}
                    </span>
                  </div>

                  {/* Baseline delta */}
                  <div className="flex flex-col">
                    <span className="text-[9px] text-gray-500 uppercase">vs Baseline</span>
                    <span className="text-[11px] text-gray-200">
                      {deltaLabel(seg.baseline_delta_pct ?? 0)}
                    </span>
                  </div>

                  {/* Trend */}
                  <div className="flex flex-col">
                    <span className="text-[9px] text-gray-500 uppercase">Trend</span>
                    <span className="text-[11px] text-gray-200">
                      {seg.trend === 'deteriorating' ? '↘ Worsening over last 6 readings'
                        : seg.trend === 'improving'  ? '↗ Recovering over last 6 readings'
                        : '→ Holding steady'}
                    </span>
                  </div>

                  {/* Sustained drift */}
                  <div className="flex flex-col">
                    <span className="text-[9px] text-gray-500 uppercase">Drift (CUSUM)</span>
                    <span className="text-[11px] text-gray-200">
                      {cusumLabel(seg.cusum_upper ?? 0)}
                    </span>
                  </div>

                  {/* Flow variance */}
                  <div className="flex flex-col">
                    <span className="text-[9px] text-gray-500 uppercase">Flow Variance</span>
                    <span className="text-[11px] text-gray-200">
                      {varianceLabel(seg.variance_ratio ?? 1)} ({seg.variance_ratio?.toFixed(2)}× normal)
                    </span>
                  </div>

                  {/* Propagation */}
                  <div className="flex flex-col">
                    <span className="text-[9px] text-gray-500 uppercase">Propagation</span>
                    <span className="text-[11px] text-gray-200">
                      {propagationLabel(seg.propagation ?? 'none')}
                    </span>
                  </div>

                  {/* Risk score bar */}
                  <div className="flex flex-col gap-0.5 mt-1">
                    <div className="flex justify-between">
                      <span className="text-[9px] text-gray-500 uppercase">Risk Score</span>
                      <span className={`text-[9px] font-bold ${severityText[sev]}`}>
                        {((seg.risk_score ?? 0) * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="h-1 rounded-full bg-gray-700 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          sev === 'critical' ? 'bg-red-500' :
                          sev === 'warning'  ? 'bg-orange-500' : 'bg-yellow-500'
                        }`}
                        style={{ width: `${Math.min((seg.risk_score ?? 0) * 100, 100)}%` }}
                      />
                    </div>
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
