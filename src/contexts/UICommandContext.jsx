import React, { createContext, useContext, useReducer, useRef } from 'react';

// ---------------------------------------------------------------------------
// State shape — what the UI command layer tracks
// ---------------------------------------------------------------------------
const initialState = {
  activeSegment: null,       // segment ID highlighted in the chart/map
  activeMetric: 'speed',     // 'speed' | 'volume' | 'risk'
  timeWindowMins: 15,        // 5 | 15 | 30 | 60
  expandedAlertId: null,     // segment ID whose alert is expanded
  overlayMode: 'risk',       // 'risk' | 'speed' | 'volume'
  pulseSegments: {},         // { segmentId: { color, expiresAt } }
  kpiPulse: null,            // 'avgSpeed' | 'worstSegment' | 'activeAlerts'
  annotations: [],           // [{ id, lat, lng, text, expiresAt }]
  mapFlyTo: null,            // { segmentId, lat, lng } — changes trigger MapPanel flyTo
};

// ---------------------------------------------------------------------------
// Reducer — applies each of the 11 command types
// ---------------------------------------------------------------------------
let annotationCounter = 0;

function uiCommandReducer(state, action) {
  const now = Date.now();

  switch (action.type) {
    case 'focusSegment': {
      // Compound: panTo + expandAlert + optional annotate — fires atomically.
      // action: { segmentId, lat?, lng?, label?, durationMs? }
      const focusPulse = action.lat != null && action.lng != null && action.label
        ? (() => {
            const id = ++annotationCounter;
            return {
              annotations: [...state.annotations, {
                id,
                lat: action.lat,
                lng: action.lng,
                text: action.label,
                expiresAt: now + (action.durationMs ?? 4000),
              }],
            };
          })()
        : { annotations: state.annotations };
      return {
        ...state,
        mapFlyTo: { segmentId: action.segmentId, ts: now },
        activeSegment: action.segmentId,
        expandedAlertId: action.segmentId,
        ...focusPulse,
      };
    }

    case 'panTo':
      return {
        ...state,
        mapFlyTo: { segmentId: action.segmentId, ts: now },
        activeSegment: action.segmentId,
      };

    case 'pulseSegment':
      return {
        ...state,
        pulseSegments: {
          ...state.pulseSegments,
          [action.segmentId]: {
            color: action.color ?? 'amber',
            expiresAt: now + (action.durationMs ?? 2000),
          },
        },
      };

    case 'clearHighlights':
      return { ...state, pulseSegments: {}, annotations: [] };

    case 'switchChart':
      return { ...state, activeSegment: action.segmentId };

    case 'switchMetric':
      return { ...state, activeMetric: action.metric };

    case 'setTimeWindow':
      return { ...state, timeWindowMins: action.minutes };

    case 'expandAlert':
      return {
        ...state,
        expandedAlertId: state.expandedAlertId === action.segmentId ? null : action.segmentId,
      };

    case 'pulseKpi':
      return { ...state, kpiPulse: { kpi: action.kpi, expiresAt: now + (action.durationMs ?? 1500) } };

    case 'switchOverlay':
      return { ...state, overlayMode: action.overlay };

    case 'annotate': {
      const id = ++annotationCounter;
      const annotation = {
        id,
        lat: action.lat,
        lng: action.lng,
        text: action.text,
        expiresAt: now + (action.durationMs ?? 4000),
      };
      return { ...state, annotations: [...state.annotations, annotation] };
    }

    case '_cleanupAnnotations':
      return {
        ...state,
        annotations: state.annotations.filter(a => a.expiresAt > Date.now()),
        pulseSegments: Object.fromEntries(
          Object.entries(state.pulseSegments).filter(([, v]) => v.expiresAt > Date.now())
        ),
        kpiPulse: state.kpiPulse && state.kpiPulse.expiresAt > Date.now() ? state.kpiPulse : null,
      };

    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Contexts
// ---------------------------------------------------------------------------
const UICommandStateContext = createContext(null);
const UICommandDispatchContext = createContext(null);

export function UICommandContextProvider({ children }) {
  const [state, dispatch] = useReducer(uiCommandReducer, initialState);

  // Periodic cleanup of expired pulses/annotations (every 500ms)
  React.useEffect(() => {
    const id = setInterval(() => dispatch({ type: '_cleanupAnnotations' }), 500);
    return () => clearInterval(id);
  }, []);

  return (
    <UICommandStateContext.Provider value={state}>
      <UICommandDispatchContext.Provider value={dispatch}>
        {children}
      </UICommandDispatchContext.Provider>
    </UICommandStateContext.Provider>
  );
}

export const useUICommand = () => {
  const ctx = useContext(UICommandStateContext);
  if (!ctx) throw new Error('useUICommand must be inside UICommandContextProvider');
  return ctx;
};

export const useUICommandDispatch = () => {
  // Allow null during initial render (AgentContext imports this before provider mounts check)
  return useContext(UICommandDispatchContext);
};
