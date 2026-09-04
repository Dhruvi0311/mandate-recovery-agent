import React, { useState, useEffect, useRef } from 'react';
import { Send, CheckCircle2, XCircle, Bot } from 'lucide-react';

export default function AgentChat({ attemptId, onMessageSent, messages, consentGranted, actionStatus, loading }) {
  const [inputMessage, setInputMessage] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (typeof messagesEndRef.current?.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const handleSend = async (text) => {
    const msgToSend = (text || inputMessage).trim();
    if (!msgToSend || sending) return;

    setSending(true);
    setInputMessage('');
    try {
      await onMessageSent(msgToSend);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="content-card">
      <div className="analysis-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <div style={{ width: 32, height: 32, background: 'var(--primary-light)', color: 'var(--primary)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Bot size={18} />
          </div>
          <div>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700 }}>AI Recovery Agent</h3>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Stateful LangGraph Agent with Strict Boundary Enforcement
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div style={{
            fontSize: '0.75rem',
            padding: '0.25rem 0.6rem',
            borderRadius: 'var(--radius-sm)',
            fontWeight: 700,
            background: consentGranted ? 'var(--success-light)' : 'rgba(255,255,255,0.05)',
            color: consentGranted ? 'var(--success)' : 'var(--text-dim)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.3rem'
          }}>
            {consentGranted ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
            <span>Action Consent: {consentGranted ? 'GRANTED' : 'NOT GRANTED'}</span>
          </div>
        </div>
      </div>

      <div className="chat-panel">
        <div className="chat-messages">
          {(!messages || messages.length === 0) && (
            <div className="empty-state">
              <span>Start the conversation with the agent or use quick reply chips below.</span>
            </div>
          )}

          {messages && messages.map((m, idx) => {
            if (m.startsWith('Customer: ')) {
              return (
                <div key={idx} className="message-bubble customer">
                  {m.replace('Customer: ', '')}
                </div>
              );
            } else if (m.startsWith('Agent: ')) {
              return (
                <div key={idx} className="message-bubble agent">
                  <div style={{ fontSize: '0.7rem', color: 'var(--primary)', fontWeight: 700, marginBottom: '0.2rem' }}>AI Recovery Agent</div>
                  {m.replace('Agent: ', '')}
                </div>
              );
            } else if (m.startsWith('Tool execution rejected:')) {
              return (
                <div key={idx} className="message-bubble tool-error">
                  🛑 Boundary Protection: {m.replace('Tool execution rejected: ', '')}
                </div>
              );
            } else if (m.startsWith('Tool ')) {
              return (
                <div key={idx} className="message-bubble tool">
                  ⚡ Tool Execution: {m}
                </div>
              );
            } else {
              return (
                <div key={idx} className="message-bubble agent">
                  {m}
                </div>
              );
            }
          })}
          <div ref={messagesEndRef} />
        </div>

        {/* Quick Consent Chips */}
        <div className="chat-quick-actions">
          <button
            type="button"
            className="chip-btn positive"
            disabled={sending || loading}
            onClick={() => handleSend('Yes, please schedule it')}
          >
            ✓ Yes, schedule it
          </button>
          <button
            type="button"
            className="chip-btn negative"
            disabled={sending || loading}
            onClick={() => handleSend('No, do not schedule retry')}
          >
            ✕ No, cancel retry
          </button>
          <button
            type="button"
            className="chip-btn"
            disabled={sending || loading}
            onClick={() => handleSend('What caused this mandate to fail?')}
          >
            ? Why did it fail?
          </button>
        </div>

        {/* Message Input */}
        <form
          className="chat-input-row"
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
        >
          <input
            type="text"
            className="chat-input"
            placeholder="Type customer reply or question..."
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            disabled={sending || loading}
          />
          <button
            type="submit"
            className="chat-send-btn"
            disabled={!inputMessage.trim() || sending || loading}
          >
            <Send size={15} />
          </button>
        </form>
      </div>
    </div>
  );
}
