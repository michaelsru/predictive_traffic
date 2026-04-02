import React, { createContext, useContext, useReducer, useEffect } from 'react';
import { useUICommandDispatch } from './UICommandContext';

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------
const initialState = {
  narrative: [],       // string[]
  uiCommands: [],      // object[]
  currentStep: -1,     // -1 = no active briefing
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
