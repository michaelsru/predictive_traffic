import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchIncidents, fetchReadings } from './api';

// ── shared style maps ────────────────────────────────────────────────────────
const SEV_BADGE = {
  critical: 'bg-red-800 text-red-100',
  major:    'bg-orange-800 text-orange-100',
  moderate: 'bg-yellow-800 text-yellow-100',
  warning:  'bg-orange-800 text-orange-100',
  watch:    'bg-yellow-800 text-yellow-100',
  minor:    'bg-blue-900 text-blue-200',
  normal:   'bg-gray-700 text-gray-400',
};
const SEV_DOT = {
  critical: 'bg-red-500',
  major:    'bg-orange-400',
  moderate: 'bg-yellow-400',
  warning:  'bg-orange-400',
  watch:    'bg-yellow-400',
  minor:    'bg-blue-400',
  normal:   'bg-gray-500',
};

const SEGMENTS   = ['', ...Array.from({length: 20}, (_, i) => `S${i + 1}`)];
const PAGE_SIZE  = 25;

function SevBadge({ sev }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase
        ${SEV_BADGE[sev] ?? 'bg-gray-700 text-gray-400'}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${SEV_DOT[sev] ?? 'bg-gray-500'}`} />
      {sev}
    </span>
  );
}

function fmt(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-CA', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  });
}

function Th({ children, right }) {
  return (
    <th className={`px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-gray-500 ${right ? 'text-right' : 'text-left'}`}>
      {children}
    </th>
  );
}

function Td({ children, right, mono, dim, className = '' }) {
  return (
    <td className={`px-3 py-2 ${right ? 'text-right' : ''} ${mono ? 'font-mono tabular-nums' : ''}
        ${dim ? 'text-gray-500' : 'text-gray-300'} ${className}`}>
      {children}
    </td>
  );
}

// ── Traffic tab ──────────────────────────────────────────────────────────────
function TrafficTab({ segFilter }) {
  const [page, setPage] = useState(0);

  const params = { limit: PAGE_SIZE, offset: page * PAGE_SIZE, ...(segFilter ? { segment_id: segFilter } : {}) };
  const { data, isLoading, isError, error } = useQuery({
    queryKey:         ['readings', params],
    queryFn:          () => fetchReadings(params),
    keepPreviousData: true,
    refetchInterval:  5_000,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <TabShell isLoading={isLoading} isError={isError} error={error}
              empty={items.length === 0} emptyMsg="No readings found."
              page={page} pages={pages} total={total} onPage={setPage}>
      <table className="w-full text-xs border-separate border-spacing-y-0.5">
        <thead>
          <tr>
            <Th>Time</Th><Th>Seg</Th><Th right>Speed</Th><Th right>Baseline</Th>
            <Th right>Δ%</Th><Th right>Var ×</Th><Th right>Samples</Th>
            <Th right>Risk</Th><Th>Status</Th>
          </tr>
        </thead>
        <tbody>
          {items.map(r => (
            <tr key={r.id} className="bg-gray-900 hover:bg-gray-800 transition-colors">
              <Td mono dim className="rounded-l-lg whitespace-nowrap">{fmt(r.timestamp)}</Td>
              <Td className="font-bold text-blue-300">{r.segment_id}</Td>
              <Td right mono>{r.avg_speed_kmh} km/h</Td>
              <Td right mono dim>{r.baseline_avg_speed} km/h</Td>
              <Td right mono className={r.baseline_delta_pct < -5 ? 'text-orange-400' : ''}>
                {r.baseline_delta_pct > 0 ? '+' : ''}{r.baseline_delta_pct}%
              </Td>
              <Td right mono className={r.variance_ratio > 2.5 ? 'text-yellow-400' : ''}>{r.variance_ratio}×</Td>
              <Td right mono dim>{r.sample_count}</Td>
              <Td right mono className={r.risk_score > 0.5 ? 'text-red-400' : ''}>
                {(r.risk_score * 100).toFixed(0)}%
              </Td>
              <Td className="rounded-r-lg"><SevBadge sev={r.severity} /></Td>
            </tr>
          ))}
        </tbody>
      </table>
    </TabShell>
  );
}

// ── Alerts tab ───────────────────────────────────────────────────────────────
function AlertsTab({ segFilter }) {
  const [page, setPage] = useState(0);

  const params = {
    limit: PAGE_SIZE, offset: page * PAGE_SIZE,
    min_severity: 'watch',
    ...(segFilter ? { segment_id: segFilter } : {}),
  };
  const { data, isLoading, isError, error } = useQuery({
    queryKey:         ['readings-alerts', params],
    queryFn:          () => fetchReadings(params),
    keepPreviousData: true,
    refetchInterval:  5_000,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <TabShell isLoading={isLoading} isError={isError} error={error}
              empty={items.length === 0} emptyMsg="No alert-level readings recorded."
              page={page} pages={pages} total={total} onPage={setPage}>
      <table className="w-full text-xs border-separate border-spacing-y-0.5">
        <thead>
          <tr>
            <Th>Time</Th><Th>Seg</Th><Th>Status</Th>
            <Th right>Speed</Th><Th right>Δ%</Th>
            <Th right>Var ×</Th><Th right>Risk</Th>
          </tr>
        </thead>
        <tbody>
          {items.map(r => (
            <tr key={r.id} className="bg-gray-900 hover:bg-gray-800 transition-colors">
              <Td mono dim className="rounded-l-lg whitespace-nowrap">{fmt(r.timestamp)}</Td>
              <Td className="font-bold text-blue-300">{r.segment_id}</Td>
              <Td><SevBadge sev={r.severity} /></Td>
              <Td right mono>{r.avg_speed_kmh} km/h</Td>
              <Td right mono className={r.baseline_delta_pct < -5 ? 'text-orange-400' : ''}>
                {r.baseline_delta_pct > 0 ? '+' : ''}{r.baseline_delta_pct}%
              </Td>
              <Td right mono className={r.variance_ratio > 2.5 ? 'text-yellow-400' : ''}>{r.variance_ratio}×</Td>
              <Td right mono className="rounded-r-lg text-red-400">
                {(r.risk_score * 100).toFixed(0)}%
              </Td>
            </tr>
          ))}
        </tbody>
      </table>
    </TabShell>
  );
}

// ── Incidents tab ────────────────────────────────────────────────────────────
function IncidentsTab({ segFilter }) {
  const [page, setPage] = useState(0);

  const params = { limit: PAGE_SIZE, offset: page * PAGE_SIZE, ...(segFilter ? { segment_id: segFilter } : {}) };
  const { data, isLoading, isError, error } = useQuery({
    queryKey:         ['incidents', params],
    queryFn:          () => fetchIncidents(params),
    keepPreviousData: true,
    refetchInterval:  10_000,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <TabShell isLoading={isLoading} isError={isError} error={error}
              empty={items.length === 0} emptyMsg="No incidents logged yet."
              page={page} pages={pages} total={total} onPage={setPage}>
      <table className="w-full text-xs border-separate border-spacing-y-0.5">
        <thead>
          <tr>
            <Th>Time</Th><Th>Seg</Th><Th>Severity</Th>
            <Th right>Risk</Th><Th right>Speed</Th>
            <Th>Notes</Th><Th>By</Th>
          </tr>
        </thead>
        <tbody>
          {items.map(r => (
            <tr key={r.id} className="bg-gray-900 hover:bg-gray-800 transition-colors">
              <Td mono dim className="rounded-l-lg whitespace-nowrap">{fmt(r.created_at)}</Td>
              <Td className="font-bold text-blue-300">{r.segment_id}</Td>
              <Td><SevBadge sev={r.severity} /></Td>
              <Td right mono>{r.risk_score != null ? (r.risk_score * 100).toFixed(0) + '%' : '—'}</Td>
              <Td right mono>{r.avg_speed_kmh != null ? r.avg_speed_kmh.toFixed(1) + ' km/h' : '—'}</Td>
              <Td className="max-w-xs truncate" title={r.notes ?? ''}>{r.notes || <span className="italic text-gray-600">—</span>}</Td>
              <Td dim className="rounded-r-lg">{r.confirmed_by ?? '—'}</Td>
            </tr>
          ))}
        </tbody>
      </table>
    </TabShell>
  );
}

// ── Shared table shell ───────────────────────────────────────────────────────
function TabShell({ isLoading, isError, error, empty, emptyMsg, page, pages, total, onPage, children }) {
  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="flex-1 overflow-auto px-2 py-2">
        {isLoading && (
          <div className="flex items-center justify-center h-32 text-sm text-gray-500 animate-pulse">Loading…</div>
        )}
        {isError && (
          <div className="flex items-center justify-center h-32 text-sm text-red-400">Error: {error?.message}</div>
        )}
        {!isLoading && !isError && empty && (
          <div className="flex items-center justify-center h-32 text-sm text-gray-500">{emptyMsg}</div>
        )}
        {!isLoading && !isError && !empty && children}
      </div>

      {pages > 1 && (
        <div className="flex items-center justify-center gap-3 px-5 py-2 border-t border-gray-800 shrink-0">
          <button disabled={page === 0} onClick={() => onPage(p => p - 1)}
            className="px-3 py-1 text-xs rounded bg-gray-800 border border-gray-700 disabled:opacity-40 hover:bg-gray-700 transition-colors">
            ← Prev
          </button>
          <span className="text-xs text-gray-500">Page {page + 1} / {pages} &nbsp;·&nbsp; {total} rows</span>
          <button disabled={page >= pages - 1} onClick={() => onPage(p => p + 1)}
            className="px-3 py-1 text-xs rounded bg-gray-800 border border-gray-700 disabled:opacity-40 hover:bg-gray-700 transition-colors">
            Next →
          </button>
        </div>
      )}
    </div>
  );
}

// ── Root component ────────────────────────────────────────────────────────────
const TABS = [
  { id: 'traffic',   label: '📡 Traffic Data',   desc: 'All segment readings' },
  { id: 'alerts',    label: '⚠️ Alerts',          desc: 'Watch / Warning / Critical readings' },
  { id: 'incidents', label: '🚨 Incidents',       desc: 'Operator-logged incidents' },
];

export default function LogsPage({ onClose }) {
  const [activeTab, setActiveTab] = useState('traffic');
  const [segFilter, setSegFilter] = useState('');

  const handleSegChange = (val) => setSegFilter(val);

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-gray-950 text-gray-100 font-sans">
      {/* ── Header ────────────────────────────────── */}
      <header className="flex items-center gap-4 px-5 py-3 bg-gray-900 border-b border-gray-800 shrink-0">
        <span className="text-xs font-bold uppercase tracking-widest text-gray-400">Logs</span>

        {/* Tabs */}
        <div className="flex items-center gap-1">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              title={tab.desc}
              className={`px-3 py-1.5 rounded text-xs font-semibold transition-all
                ${activeTab === tab.id
                  ? 'bg-blue-700 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200'}`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Segment filter */}
        <select
          value={segFilter}
          onChange={e => handleSegChange(e.target.value)}
          className="ml-auto text-xs bg-gray-800 border border-gray-700 rounded px-2 py-1
                     text-gray-300 focus:outline-none focus:border-blue-500"
        >
          {SEGMENTS.map(s => <option key={s} value={s}>{s || 'All segments'}</option>)}
        </select>

        <button onClick={onClose}
          className="ml-2 text-gray-500 hover:text-gray-200 transition-colors text-lg leading-none"
          title="Close">
          ✕
        </button>
      </header>

      {/* ── Tab content ────────────────────────────── */}
      {activeTab === 'traffic'   && <TrafficTab   segFilter={segFilter} />}
      {activeTab === 'alerts'    && <AlertsTab    segFilter={segFilter} />}
      {activeTab === 'incidents' && <IncidentsTab segFilter={segFilter} />}
    </div>
  );
}
