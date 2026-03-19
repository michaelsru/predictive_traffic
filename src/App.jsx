import React, { useState, useEffect } from 'react';
import ChatPanel from './ChatPanel';
import MapPanel from './MapPanel';
import SegmentPanel from './SegmentPanel';
import { fetchStatus, setScenario } from './api';
import './index.css';

export default function App() {
  const [statusData, setStatusData] = useState({});
  const [chatHistory, setChatHistory] = useState([]);
  const [highlights, setHighlights] = useState([]);
  const [activeAnchor, setActiveAnchor] = useState(null);
  const [scenario, setCurrentScenario] = useState('normal');

  useEffect(() => {
    const loadStatus = async () => {
      try {
        const data = await fetchStatus();
        setStatusData(data);
      } catch (err) {
        console.error(err);
      }
    };
    
    loadStatus();
    const interval = setInterval(loadStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleScenarioChange = async (mode) => {
    try {
      await setScenario(mode);
      setCurrentScenario(mode);
    } catch (err) {
      console.error(err);
    }
  };

  const handleChatResponse = (response, userMessage) => {
    setChatHistory(prev => [
      ...prev,
      { role: 'user', content: userMessage },
      { role: 'assistant', content: response.narrative, talking_points: response.talking_points }
    ]);
    if (response.highlights) {
      setHighlights(response.highlights);
    }
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Corridor Intelligence Dashboard - Highway 401</h1>
        <div className="scenario-controls">
          <button 
            className={scenario === 'normal' ? 'active' : ''} 
            onClick={() => handleScenarioChange('normal')}>Normal</button>
          <button 
            className={scenario === 'forming' ? 'active' : ''} 
            onClick={() => handleScenarioChange('forming')}>Forming</button>
          <button 
            className={scenario === 'incident' ? 'active' : ''} 
            onClick={() => handleScenarioChange('incident')}>Incident</button>
        </div>
      </header>
      <main className="app-main">
        <ChatPanel 
          history={chatHistory} 
          onResponse={handleChatResponse} 
          onHoverAnchor={setActiveAnchor} 
        />
        <MapPanel 
          highlights={highlights} 
          activeAnchor={activeAnchor} 
          talkingPoints={chatHistory.length > 0 ? chatHistory[chatHistory.length - 1].talking_points : []}
        />
        <SegmentPanel statusData={statusData} />
      </main>
    </div>
  );
}
