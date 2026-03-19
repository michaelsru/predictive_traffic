import React, { useState, useRef, useEffect } from 'react';
import { sendChat } from './api';

export default function ChatPanel({ history, onResponse, onHoverAnchor }) {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [history]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg = input;
    setInput('');
    setLoading(true);

    try {
      // Pass history without talking_points for the API
      const apiHistory = history.map(h => ({ role: h.role, content: h.content }));
      const response = await sendChat(userMsg, apiHistory);
      onResponse(response, userMsg);
    } catch (err) {
      console.error(err);
      alert('Failed to send message');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chat-panel">
      <div className="chat-history">
        {history.map((msg, idx) => (
          <div key={idx} className={`chat-message ${msg.role}`}>
            <div className="message-content">{msg.content}</div>
            {msg.talking_points && msg.talking_points.length > 0 && (
              <div className="talking-points">
                {msg.talking_points.map(tp => (
                  <div 
                    key={tp.id} 
                    className="talking-point-card"
                    onMouseEnter={() => onHoverAnchor(tp.anchor)}
                    onMouseLeave={() => onHoverAnchor(null)}
                  >
                    <div className="tp-header">
                      <span className="tp-id">{tp.id}</span>
                      <span className={`tp-severity ${tp.severity}`}>{tp.severity}</span>
                    </div>
                    <div className="tp-text">{tp.text}</div>
                    <div className="tp-confidence">
                      <div className="confidence-bar" style={{ width: `${tp.confidence * 100}%` }}></div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
        {loading && <div className="chat-message assistant loading">Analyzing corridor...</div>}
        <div ref={messagesEndRef} />
      </div>
      <form className="chat-input-form" onSubmit={handleSubmit}>
        <input 
          type="text" 
          value={input} 
          onChange={(e) => setInput(e.target.value)} 
          placeholder="Ask about road conditions..."
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>Send</button>
      </form>
    </div>
  );
}
