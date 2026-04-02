import React, { useState } from 'react';
import ChatPanel from './ChatPanel';
import MapPanel from './MapPanel';
import SegmentPanel from './SegmentPanel';
import AlertPanel from './AlertPanel';
import KpiBar from './KpiBar';
import CctvSidebar from './CctvSidebar';
import { fetchStatus, setScenario } from './api';
import { useQuery } from '@tanstack/react-query';
import { UICommandContextProvider } from './contexts/UICommandContext';
import { AgentContextProvider } from './contexts/AgentContext';
import './index.css';

function App() {
  const [chatHistory, setChatHistory] = useState([]);
  const [scenario, setCurrentScenario] = useState('normal');
  const [cctvOpen, setCctvOpen] = useState(false);

  const { data: statusData = {} } = useQuery({
    queryKey: ['status'],
    queryFn: fetchStatus,
    refetchInterval: 5000,
  });

  const handleScenarioChange = async (mode) => {
    try { await setScenario(mode); setCurrentScenario(mode); }
    catch (err) { console.error(err); }
  };

  const handleChatResponse = (response, userMessage) => {
    setChatHistory(prev => [
      ...prev,
      { role: 'user', content: userMessage },
      { role: 'assistant', content: response.narrative?.[0] ?? '' },
    ]);
  };

  const scenarioColors = {
    normal:   'bg-emerald-700 border-emerald-500',
    forming:  'bg-yellow-700 border-yellow-500',
    incident: 'bg-red-800 border-red-600',
  };

  return (
    <UICommandContextProvider>
      <AgentContextProvider>
        <div className="flex flex-col h-screen bg-gray-950 text-gray-100 font-sans overflow-hidden">

          {/* ── Header ─────────────────────────────────────── */}
          <header className="flex items-center justify-between px-4 py-2 bg-gray-900 border-b border-gray-800 shrink-0 gap-4">
            <KpiBar statusData={statusData} />

            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xs text-gray-500 uppercase tracking-widest mr-1">Scenario</span>
              {['normal', 'forming', 'incident'].map(mode => (
                <button
                  key={mode}
                  onClick={() => handleScenarioChange(mode)}
                  className={`px-3 py-1 rounded text-xs font-semibold border transition-all
                    ${scenario === mode
                      ? scenarioColors[mode] + ' text-white'
                      : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500'}`}
                >
                  {mode.charAt(0).toUpperCase() + mode.slice(1)}
                </button>
              ))}
            </div>
          </header>

          {/* ── Main ───────────────────────────────────────── */}
          <main className="flex flex-1 overflow-hidden">
            <ChatPanel history={chatHistory} onResponse={handleChatResponse} onViewFootage={() => setCctvOpen(true)} />
            <MapPanel statusData={statusData} />
            <AlertPanel statusData={statusData} />
            <SegmentPanel statusData={statusData} />
          </main>
          <CctvSidebar open={cctvOpen} onClose={() => setCctvOpen(false)} />
        </div>
      </AgentContextProvider>
    </UICommandContextProvider>
  );
}

export default App;
