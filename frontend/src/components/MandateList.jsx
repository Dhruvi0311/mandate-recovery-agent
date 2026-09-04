import React, { useState } from 'react';
import { Search } from 'lucide-react';

export default function MandateList({ mandates, selectedAttemptId, onSelect, loading, error }) {
  const [searchTerm, setSearchTerm] = useState('');

  const filtered = (mandates || []).filter(m => {
    const term = searchTerm.toLowerCase();
    return (
      m.attempt_id.toLowerCase().includes(term) ||
      m.customer_id.toLowerCase().includes(term) ||
      m.mandate_id.toLowerCase().includes(term) ||
      m.failure_reason.toLowerCase().includes(term)
    );
  });

  return (
    <aside className="mandate-list-panel">
      <div className="panel-header">
        <h2 className="panel-title">Failed Mandate Attempts</h2>
        <span className="badge-count">{filtered.length}</span>
      </div>

      <div style={{ position: 'relative' }}>
        <input
          type="text"
          className="search-input"
          placeholder="Filter attempts, customers..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </div>

      {loading && (
        <div className="empty-state">
          <div className="spinner" />
          <span>Loading failed mandates...</span>
        </div>
      )}

      {error && !loading && (
        <div className="error-banner">
          {error}
        </div>
      )}

      {!loading && !error && filtered.length === 0 && (
        <div className="empty-state">
          <span>No matching attempts found.</span>
        </div>
      )}

      <div className="mandates-scroll">
        {filtered.map((m) => {
          const isSelected = m.attempt_id === selectedAttemptId;
          const statusClass = (m.recovery_state || 'PENDING').toLowerCase();
          return (
            <button
              key={m.attempt_id}
              type="button"
              className={`mandate-card ${isSelected ? 'selected' : ''}`}
              onClick={() => onSelect(m.attempt_id)}
            >
              <div className="card-top">
                <span className="card-id">{m.attempt_id}</span>
                <span className="card-amount">₹{Number(m.amount).toLocaleString('en-IN')}</span>
              </div>
              <div className="card-meta">
                <span>{m.customer_id} • {m.mandate_id}</span>
                <span>{m.attempt_date}</span>
              </div>
              <div className="card-bottom">
                <span className="reason-tag">{m.failure_reason}</span>
                <span className={`status-pill ${statusClass}`}>{m.recovery_state || 'PENDING'}</span>
              </div>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
