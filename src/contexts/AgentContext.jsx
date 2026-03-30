import React, { createContext, useContext, useReducer, useRef, useEffect } from 'react';
import { useUICommandDispatch } from './UICommandContext';

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------
const initialState = {
  narrative: [],       // string[]
  uiCommands: [],      // object[]
  currentStep: -1,     // -1 = no active briefing
  isPlaying: false,
  query: '',           // the user query that produced this briefing
};

// ---------------------------------------------------------------------------
// Reducer
// ---------------------------------------------------------------------------
function agentReducer(state, action) {
  switch (action.type) {
    case 'LOAD':
      return {
        ...state,
        narrative: action.narrative,
        uiCommands: action.uiCommands,
        currentStep: 0,
        isPlaying: false,
        query: action.query ?? '',
      };
    case 'NEXT':
      if (state.currentStep >= state.narrative.length - 1) return state;
      return { ...state, currentStep: state.currentStep + 1 };
    case 'PREV':
      if (state.currentStep <= 0) return state;
      return { ...state, currentStep: state.currentStep - 1 };
    case 'JUMP':
      if (action.step < 0 || action.step >= state.narrative.length) return state;
      return { ...state, currentStep: action.step };
    case 'PLAY':
      return { ...state, isPlaying: true };
    case 'PAUSE':
      return { ...state, isPlaying: false };
    case 'RESET':
      return { ...initialState };
    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------
const AgentStateContext = createContext(null);
const AgentDispatchContext = createContext(null);

export function AgentContextProvider({ children }) {
  const [state, dispatch] = useReducer(agentReducer, initialState);
  const dispatchUICommand = useUICommandDispatch();
  const autoAdvanceRef = useRef(null);

  // Fire the UI command whenever currentStep changes
  const prevStep = useRef(-1);
  useEffect(() => {
    if (state.currentStep === -1) return;
    if (state.currentStep === prevStep.current) return;
    prevStep.current = state.currentStep;
    const cmd = state.uiCommands[state.currentStep];
    if (cmd && dispatchUICommand) {
      dispatchUICommand(cmd);
    }
  }, [state.currentStep, state.uiCommands, dispatchUICommand]);

  // Reset prevStep when a new briefing loads so step 0 always fires
  useEffect(() => {
    prevStep.current = -1;
  }, [state.uiCommands]);

  // Auto-advance every 4 s while playing
  useEffect(() => {
    if (state.isPlaying) {
      autoAdvanceRef.current = setInterval(() => {
        dispatch({ type: 'NEXT' });
      }, 4000);
    } else {
      clearInterval(autoAdvanceRef.current);
    }
    return () => clearInterval(autoAdvanceRef.current);
  }, [state.isPlaying]);

  // Auto-stop at the last step
  useEffect(() => {
    if (state.isPlaying && state.currentStep === state.narrative.length - 1) {
      dispatch({ type: 'PAUSE' });
    }
  }, [state.currentStep, state.narrative.length, state.isPlaying]);

  return (
    <AgentStateContext.Provider value={state}>
      <AgentDispatchContext.Provider value={dispatch}>
        {children}
      </AgentDispatchContext.Provider>
    </AgentStateContext.Provider>
  );
}

export const useAgentState = () => {
  const ctx = useContext(AgentStateContext);
  if (!ctx) throw new Error('useAgentState must be used inside AgentContextProvider');
  return ctx;
};

export const useAgentDispatch = () => {
  const ctx = useContext(AgentDispatchContext);
  if (!ctx) throw new Error('useAgentDispatch must be used inside AgentContextProvider');
  return ctx;
};
