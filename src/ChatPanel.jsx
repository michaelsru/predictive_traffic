import React, { useState, useRef, useEffect } from 'react';
import { sendChat, logIncident } from './api';
import { useAgentState, useAgentDispatch } from './contexts/AgentContext';

// Commands that are mechanical/prep steps — hidden by default
const THINKING_COMMANDS = new Set([
  'switchChart', 'setTimeWindow', 'switchOverlay', 'clearHighlights',
]);

/**
 * Groups narrative + uiCommands into sequential blocks:
 *   { type: 'step',    index, text, cmd }
 *   { type: 'thinking', items: [{ index, text, cmd }, ...] }
 */
function groupSteps(narrative, uiCommands) {
  const groups = [];
  let thinkingAccum = null;

  narrative.forEach((text, index) => {
    const cmd = uiCommands[index] ?? {};
    const isThinking = THINKING_COMMANDS.has(cmd.type);

    if (isThinking) {
      if (!thinkingAccum) { thinkingAccum = { type: 'thinking', items: [] }; groups.push(thinkingAccum); }
      thinkingAccum.items.push({ index, text, cmd });
    } else {
      thinkingAccum = null;
      groups.push({ type: 'step', index, text, cmd });
    }
  });

  return groups;
}

const SUGGESTED_QUERIES = [
  "Give me a full corridor brief",
  "Handover brief — what happened in the last hour?",
  "What's happening near S3?",
  "Triage my active alerts",
  "Walk me through the last 30 minutes on S2",
  "Why is the risk score high?",
  "What should I watch if this pattern continues?",
];

// ─── ThinkingGroup ──────────────────────────────────────────────────────────
function ThinkingGroup({ items, currentStep, agentDispatch }) {
  const [open, setOpen] = useState(false);
  const [expandedCmd, setExpandedCmd] = useState(null); // index of item whose cmd JSON is shown
  const containsActive = items.some(it => it.index === currentStep);

  return (
    <div className={`rounded-lg border transition-all ${containsActive ? 'border-blue-500/30 bg-blue-600/10' : 'border-gray-700/40 bg-gray-800/30'}`}>
      {/* Toggle row */}
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 w-full px-2.5 py-1.5 text-left text-[10px] text-gray-500 hover:text-gray-300 transition-colors"
      >
        <span className={`transition-transform duration-150 ${open ? 'rotate-90' : ''}`}>▶</span>
        <span className="font-mono uppercase tracking-widest">
          {items.length} thinking step{items.length > 1 ? 's' : ''}
        </span>
        {containsActive && (
          <span className="ml-auto w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
        )}
      </button>

      {/* Expanded items */}
      {open && (
        <div className="px-2 pb-2 flex flex-col gap-0.5 border-t border-gray-700/40">
          {items.map(({ index, text, cmd }) => (
            <div key={index} className={`rounded-md transition-all ${index === currentStep ? 'bg-blue-600/20 border border-blue-500/30' : ''}`}>
              <button
                onClick={() => { agentDispatch({ type: 'PAUSE' }); agentDispatch({ type: 'JUMP', step: index }); }}
                className={`flex items-start gap-2 text-left px-2 py-1.5 w-full text-xs
                  ${index === currentStep ? 'text-gray-100' : index < currentStep ? 'text-gray-500 hover:text-gray-300' : 'text-gray-400 hover:text-gray-200'}`}
              >
                <span className={`shrink-0 w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold mt-0.5
                  ${index === currentStep ? 'bg-blue-500 text-white' : index < currentStep ? 'bg-gray-600 text-gray-400' : 'bg-gray-700 text-gray-500'}`}>
                  {index + 1}
                </span>
                <span className="leading-snug flex-1">{text}</span>
                <span
                  role="button"
                  tabIndex={0}
                  title="Show raw command"
                  onClick={e => { e.stopPropagation(); setExpandedCmd(p => p === index ? null : index); }}
                  onKeyDown={e => e.key === 'Enter' && (e.stopPropagation(), setExpandedCmd(p => p === index ? null : index))}
                  className="shrink-0 px-1 py-0.5 rounded text-[9px] font-mono bg-gray-700 hover:bg-gray-600 text-gray-400 hover:text-gray-200 cursor-pointer transition-colors"
                >
                  {'{ }'}
                </span>
              </button>
              {expandedCmd === index && (
                <pre className="mx-2 mb-1.5 px-2 py-1.5 rounded bg-gray-900/80 border border-gray-700/60 text-[9px] text-gray-400 font-mono overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(cmd, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── StepList ────────────────────────────────────────────────────────────────
function StepList({ narrative, uiCommands, currentStep, agentDispatch }) {
  const groups = groupSteps(narrative, uiCommands);
  return (
    <div className="px-2 pb-2 flex flex-col gap-0.5">
      {groups.map((group, gi) =>
        group.type === 'thinking' ? (
          <ThinkingGroup
            key={`tg-${gi}`}
            items={group.items}
            currentStep={currentStep}
            agentDispatch={agentDispatch}
          />
        ) : (
          <button
            key={group.index}
            onClick={() => { agentDispatch({ type: 'PAUSE' }); agentDispatch({ type: 'JUMP', step: group.index }); }}
            className={`flex items-start gap-2 text-left px-2 py-1.5 rounded-lg transition-all w-full text-xs
              ${group.index === currentStep
                ? 'bg-blue-600/25 border border-blue-500/40 text-gray-100'
                : group.index < currentStep
                  ? 'text-gray-500 hover:text-gray-300 hover:bg-gray-700/30'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-gray-700/20'}`}
          >
            <span className={`shrink-0 w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold mt-0.5
              ${group.index === currentStep ? 'bg-blue-500 text-white' : group.index < currentStep ? 'bg-gray-600 text-gray-400' : 'bg-gray-700 text-gray-500'}`}>
              {group.index + 1}
            </span>
            <span className="leading-snug">{group.text}</span>
          </button>
        )
      )}
    </div>
  );
}

// ─── ConfirmIncidentForm ────────────────────────────────────────────
const SEVERITIES = [
  { value: 'minor',    label: 'Minor',    color: 'bg-yellow-700 border-yellow-500' },
  { value: 'moderate', label: 'Moderate', color: 'bg-orange-700 border-orange-500' },
  { value: 'major',    label: 'Major',    color: 'bg-red-700    border-red-500'    },
  { value: 'critical', label: 'Critical', color: 'bg-red-900    border-red-400'    },
];
const SEGMENTS = ['S1', 'S2', 'S3', 'S4', 'S5'];

function ConfirmIncidentForm({ defaultSegment, onDone }) {
  const [segmentId, setSegmentId] = useState(defaultSegment ?? 'S1');
  const [severity, setSeverity]   = useState('moderate');
  const [notes, setNotes]         = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult]       = useState(null); // { ok: bool, message }

  const handleSubmit = async () => {
    setSubmitting(true);
    setResult(null);
    try {
      const rec = await logIncident({ segment_id: segmentId, severity, notes: notes || null });
      setResult({ ok: true, message: `Incident #${rec.id} logged — ${rec.severity} @ ${rec.segment_id}` });
      setTimeout(onDone, 2000);
    } catch (err) {
      setResult({ ok: false, message: err.message });
    } finally {
      setSubmitting(false);
    }
  };

  if (result?.ok) return (
    <div className="px-3 py-2.5 text-xs text-emerald-400 flex items-center gap-2">
      <span>✓</span><span>{result.message}</span>
    </div>
  );

  return (
    <div className="px-2 pt-1 pb-2 flex flex-col gap-2">
      {/* Segment */}
      <div className="flex items-center gap-1.5">
        <span className="text-[9px] text-gray-500 uppercase w-14 shrink-0">Segment</span>
        <div className="flex gap-1 flex-wrap">
          {SEGMENTS.map(s => (
            <button key={s} onClick={() => setSegmentId(s)}
              className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border transition-all
                ${segmentId === s ? 'bg-blue-600 border-blue-400 text-white' : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500'}`}>
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Severity */}
      <div className="flex items-center gap-1.5">
        <span className="text-[9px] text-gray-500 uppercase w-14 shrink-0">Severity</span>
        <div className="flex gap-1 flex-wrap">
          {SEVERITIES.map(({ value, label, color }) => (
            <button key={value} onClick={() => setSeverity(value)}
              className={`px-2 py-0.5 rounded text-[10px] font-semibold border transition-all
                ${severity === value ? color + ' text-white' : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500'}`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Notes */}
      <textarea
        value={notes}
        onChange={e => setNotes(e.target.value)}
        placeholder="Optional notes…"
        rows={2}
        className="w-full bg-gray-900 border border-gray-700 focus:border-orange-500 text-gray-200 text-[10px] px-2 py-1.5 rounded outline-none resize-none transition-colors placeholder:text-gray-600"
      />

      {result && !result.ok && (
        <p className="text-[10px] text-red-400">{result.message}</p>
      )}

      <div className="flex gap-2 justify-end">
        <button onClick={onDone} className="px-2.5 py-1 text-[10px] text-gray-400 hover:text-gray-200 transition-colors">Cancel</button>
        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="px-3 py-1 rounded text-[10px] font-semibold bg-orange-700 hover:bg-orange-600 disabled:opacity-50 text-white transition-all"
        >{submitting ? 'Logging…' : 'Confirm Incident'}
        </button>
      </div>
    </div>
  );
}

// ─── ChatPanel ───────────────────────────────────────────────────────────────
export default function ChatPanel({ history, onResponse, onViewFootage }) {

  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [incidentFormOpen, setIncidentFormOpen] = useState(false);
  const messagesEndRef = useRef(null);
  const { narrative, uiCommands, currentStep } = useAgentState();
  const agentDispatch = useAgentDispatch();

  // Derive worst segment: rank pulseSegment commands by color severity, fall back to first panTo
  const COLOR_RANK = { red: 4, amber: 3, yellow: 2, green: 1 };
  const defaultIncidentSegment = (() => {
    const pulses = uiCommands.filter(c => c.type === 'pulseSegment' && c.segmentId);
    if (pulses.length) {
      return pulses.reduce((worst, c) =>
        (COLOR_RANK[c.color] ?? 0) > (COLOR_RANK[worst.color] ?? 0) ? c : worst
      ).segmentId;
    }
    return uiCommands.find(c => c.type === 'panTo')?.segmentId ?? 'S1';
  })();


  const totalSteps = narrative.length;
  const hasBriefing = totalSteps > 0;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [history, currentStep]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput('');
    setLoading(true);
    setError(null);
    try {
      const apiHistory = history.slice(-10).map(h => ({ role: h.role, content: h.content }));
      const response = await sendChat(userMsg, apiHistory);
      agentDispatch({ type: 'LOAD', narrative: response.narrative, uiCommands: response.uiCommands, query: userMsg });
      onResponse(response, userMsg);
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-[420px] shrink-0 flex flex-col bg-gray-900 border-r border-gray-800">

      {/* ── Header ─────────────────────────────────── */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-gray-800 shrink-0">
        <span className="text-blue-400">◈</span>
        <span className="text-xs font-bold text-gray-300 uppercase tracking-widest">Co-pilot</span>
      </div>

      {/* ── History ────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-3 py-3 flex flex-col gap-3">
        {history.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'user' ? (
              <div className="bg-blue-600 text-white text-sm px-3 py-2 rounded-2xl rounded-tr-sm max-w-[80%]">
                {msg.content}
              </div>
            ) : (
              <div className="w-full bg-gray-800/60 rounded-xl border border-gray-700/50 overflow-hidden">
                <div className="px-3 pt-2.5 pb-1 flex items-center gap-1.5">
                  <span className="text-blue-400 text-xs">◈</span>
                  <span className="text-[10px] text-gray-500 uppercase tracking-widest font-semibold">Agent Briefing</span>
                </div>

                {/* Step list — only on last assistant message */}
                {idx === history.length - 1 && hasBriefing ? (
                  <>
                    <StepList
                      narrative={narrative}
                      uiCommands={uiCommands}
                      currentStep={currentStep}
                      agentDispatch={agentDispatch}
                    />
                    {/* ── Operator actions ── */}
                    <div className="px-2 pb-2 pt-1 flex flex-col gap-1.5 border-t border-gray-700/40 mt-0.5">
                      <span className="text-[9px] text-gray-600 uppercase tracking-widest px-1 pt-0.5">Operator actions</span>
                      <div className="flex flex-col gap-1">
                        <button
                          onClick={() => onViewFootage?.()}
                          className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs text-gray-400 hover:text-gray-100 bg-gray-800/60 hover:bg-gray-700/60 border border-gray-700/50 hover:border-gray-600 transition-all w-full text-left"
                        >
                          <span>📷</span>
                          <span>View Live Footage</span>
                        </button>
                        <button
                          onClick={() => setIncidentFormOpen(o => !o)}
                          className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs transition-all w-full text-left
                            ${incidentFormOpen
                              ? 'text-orange-100 bg-orange-900/50 border border-orange-600/60'
                              : 'text-orange-300 hover:text-orange-100 bg-orange-950/30 hover:bg-orange-900/40 border border-orange-700/30 hover:border-orange-600/50'}`}
                        >
                          <span>⚠</span>
                          <span>Confirm Incident</span>
                          <span className="ml-auto text-[9px]">{incidentFormOpen ? '▲' : '▼'}</span>
                        </button>
                        <button
                          onClick={() => {/* stub */ }}
                          className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs text-red-300 hover:text-red-100 bg-red-950/30 hover:bg-red-900/40 border border-red-700/30 hover:border-red-600/50 transition-all w-full text-left"
                        >
                          <span>🚨</span>
                          <span>Create Incident Response</span>
                        </button>
                      </div>
                      {incidentFormOpen && (
                        <div className="rounded-lg border border-orange-700/30 bg-orange-950/20 mt-0.5">
                          <ConfirmIncidentForm
                            defaultSegment={defaultIncidentSegment}
                            onDone={() => setIncidentFormOpen(false)}
                          />
                        </div>
                      )}
                    </div>
                  </>
                ) : (
                  <p className="px-3 pb-3 text-sm text-gray-300 leading-relaxed">{msg.content}</p>
                )}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2 text-gray-500 text-sm px-2">
            <span className="flex gap-1">
              {[0, 1, 2].map(i => (
                <span key={i} className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-bounce"
                  style={{ animationDelay: `${i * 0.15}s` }} />
              ))}
            </span>
            Assembling corridor context…
          </div>
        )}
        {error && (
          <div className="mx-2 px-3 py-2 rounded-lg bg-red-950/60 border border-red-700/50 text-red-400 text-xs">
            <span className="font-bold">Error: </span>{error}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* ── Step Navigator ─────────────────────────── */}
      {hasBriefing && (
        <div className="px-3 py-2 border-t border-gray-800 bg-gray-900/80 shrink-0">
          {/* Progress bar */}
          <div className="h-0.5 bg-gray-700 rounded-full mb-2 overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full step-progress-bar"
              style={{ width: `${((currentStep + 1) / totalSteps) * 100}%` }}
            />
          </div>
          <div className="flex items-center justify-between gap-2">
            <button
              onClick={() => agentDispatch({ type: 'PREV' })}
              disabled={currentStep === 0}
              className="px-4 py-1.5 rounded text-sm bg-gray-800 hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            >◀</button>

            <span className="text-xs text-gray-400 font-mono">
              Step <span className="text-white font-bold">{currentStep + 1}</span>
              <span className="text-gray-600 mx-1">of</span>
              {totalSteps}
            </span>

            <button
              onClick={() => agentDispatch({ type: 'NEXT' })}
              disabled={currentStep === totalSteps - 1}
              className="px-4 py-1.5 rounded text-sm bg-gray-800 hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            >▶</button>
          </div>

        </div>
      )}

      {/* ── Input ──────────────────────────────────── */}
      <div className="px-3 pb-3 pt-2 border-t border-gray-800 shrink-0">
        {history.length === 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {SUGGESTED_QUERIES.map(q => (
              <button
                key={q}
                onClick={() => setInput(q)}
                className="text-[10px] px-2 py-1 rounded-full bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-gray-200 border border-gray-700 hover:border-gray-500 transition-all"
              >
                {q}
              </button>
            ))}
          </div>
        )}
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask the co-pilot…"
            disabled={loading}
            autoFocus
            className="flex-1 bg-gray-800 border border-gray-700 focus:border-blue-500 text-gray-100 placeholder:text-gray-600
              text-sm px-3 py-2 rounded-lg outline-none transition-colors"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:cursor-not-allowed
              text-white text-sm font-semibold rounded-lg transition-all"
          >
            {loading ? '…' : 'Send'}
          </button>
        </form>
      </div>
    </div>
  );
}
