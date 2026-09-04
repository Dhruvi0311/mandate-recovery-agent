import React, { useEffect, useState } from 'react';
import { api } from '../services/api';

export default function Header({ currentScreen, onSelectScreen, onSelectScenario, activeAttemptId }) {
  const [isHealthy, setIsHealthy] = useState(null);

  useEffect(() => {
    let mounted = true;
    api.getHealth()
      .then(() => {
        if (mounted) setIsHealthy(true);
      })
      .catch(() => {
        if (mounted) setIsHealthy(false);
      });
    return () => { mounted = false; };
  }, []);

  return (
    <header className="fintech-shell-header">
      <div className="shell-left">
        <div className="shell-brand">
          <div className="brand-badge">MR</div>
          <span className="brand-name">MANDATE RECOVERY</span>
        </div>

        <nav className="shell-nav">
          <button
            type="button"
            className={`nav-tab ${currentScreen === 'batch-impact' ? 'active' : ''}`}
            onClick={() => onSelectScreen('batch-impact')}
          >
            Batch Impact
          </button>
          <button
            type="button"
            className={`nav-tab ${currentScreen === 'attempt-detail' ? 'active' : ''}`}
            onClick={() => onSelectScreen('attempt-detail')}
          >
            Attempt Detail
          </button>
          <button
            type="button"
            className={`nav-tab ${currentScreen === 'agent-trace' ? 'active' : ''}`}
            onClick={() => onSelectScreen('agent-trace')}
          >
            Live Agent Trace
          </button>
        </nav>
      </div>

      <div className="shell-right">
        {/* Subtle Environment / Simulation Status Indicator */}
        <div className="environment-badge">
          <span className="env-tag">PROTOTYPE</span>
          <span className="env-sep">•</span>
          <span className="env-desc">SIMULATED PAYMENT RAIL</span>
        </div>

        <div className="api-indicator" title={isHealthy ? 'FastAPI Connected' : 'API Connecting...'}>
          <span className={`status-dot ${isHealthy ? 'online' : 'checking'}`} />
          <span className="status-label">{isHealthy ? 'FastAPI Connected' : 'Connecting...'}</span>
        </div>

        {/* Compact Scenario Triggers */}
        <div className="scenario-quick-actions">
          <button
            type="button"
            className={`scenario-pill ${activeAttemptId === 'ATMPT00005' ? 'active' : ''}`}
            onClick={() => onSelectScenario('ATMPT00005')}
            title="Load Scenario A (ATMPT00005): Recoverable Insufficient Funds"
          >
            <span>Scenario A</span>
            <span className="pill-sub">ATMPT00005</span>
          </button>

          <button
            type="button"
            className={`scenario-pill ${activeAttemptId === 'ATMPT00006' ? 'active' : ''}`}
            onClick={() => onSelectScenario('ATMPT00006')}
            title="Load Scenario B (ATMPT00006): Unrecoverable / DO_NOT_RETRY"
          >
            <span>Scenario B</span>
            <span className="pill-sub">ATMPT00006</span>
          </button>
        </div>
      </div>
    </header>
  );
}
