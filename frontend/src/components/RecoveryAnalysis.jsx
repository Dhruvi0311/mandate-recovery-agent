import React from 'react';
import { Calendar, ShieldAlert, CheckCircle, Clock } from 'lucide-react';

export default function RecoveryAnalysis({ analysis, loading, error }) {
  if (loading) {
    return (
      <div className="content-card">
        <div className="empty-state">
          <div className="spinner" />
          <span>Running Feature Engine & Decision Engine analysis...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="content-card">
        <div className="error-banner">
          Analysis Error: {error}
        </div>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="content-card">
        <div className="empty-state">
          <span>Select a failed mandate attempt from the list to analyze recovery.</span>
        </div>
      </div>
    );
  }

  const {
    attempt_id,
    amount,
    failure_reason,
    recovery_probability,
    recommended_retry_date,
    decision,
    reason_codes,
    requires_customer_consent,
    candidate_retry_windows
  } = analysis;

  const probPercent = Math.round(recovery_probability * 100);
  const decisionClass = decision.toLowerCase();

  return (
    <div className="content-card">
      <div className="analysis-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 800 }}>Attempt {attempt_id} Recovery Intelligence</h3>
            <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>• ₹{Number(amount).toLocaleString('en-IN')}</span>
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
            Failure Cause: <span style={{ color: 'var(--danger)', fontWeight: 600 }}>{failure_reason}</span>
          </div>
        </div>

        <div className={`decision-badge ${decisionClass}`}>
          {decision === 'RESCHEDULE' && <Calendar size={16} />}
          {decision === 'RETRY_NOW' && <Clock size={16} />}
          {decision === 'DO_NOT_RETRY' && <ShieldAlert size={16} />}
          <span>{decision}</span>
        </div>
      </div>

      {/* Recommended Date Highlight Banner */}
      {recommended_retry_date ? (
        <div className="recommended-banner">
          <div>
            <div className="recommended-title">RECOMMENDED RETRY WINDOW (ML OPTIMIZED)</div>
            <div className="recommended-date">{recommended_retry_date}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '0.15rem' }}>
              Highest predicted cashflow inflow timing based on transaction history
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Confidence</span>
            <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--success)' }}>{probPercent}%</div>
          </div>
        </div>
      ) : (
        <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: 'var(--radius-md)', padding: '0.85rem 1.25rem', color: '#fca5a5', fontSize: '0.85rem' }}>
          <strong>No retry window recommended:</strong> Probability of auto-debit recovery is below the minimum policy threshold. Automatic retries are paused to protect customer fees.
        </div>
      )}

      {/* Metrics Grid */}
      <div className="metrics-grid">
        <div className="metric-box highlight">
          <span className="metric-label">Recovery Probability</span>
          <span className="metric-value" style={{ color: probPercent >= 70 ? 'var(--success)' : probPercent <= 40 ? 'var(--danger)' : 'var(--warning)' }}>
            {probPercent}%
          </span>
          <div className="progress-bar-bg">
            <div
              className="progress-bar-fill"
              style={{
                width: `${probPercent}%`,
                background: probPercent >= 70 ? 'var(--success)' : probPercent <= 40 ? 'var(--danger)' : 'var(--warning)'
              }}
            />
          </div>
        </div>

        <div className="metric-box">
          <span className="metric-label">Consent Requirement</span>
          <span className="metric-value" style={{ fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.4rem', color: requires_customer_consent ? 'var(--warning)' : 'var(--text-muted)' }}>
            {requires_customer_consent ? 'Mandatory Customer Consent' : 'Autonomous Action'}
          </span>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
            {requires_customer_consent ? 'Agent must ask customer before action' : 'No explicit opt-in needed'}
          </span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Policy Reason Codes</span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem', marginTop: '0.3rem' }}>
            {reason_codes.map(rc => (
              <span key={rc} className="reason-tag" style={{ color: 'var(--primary)', borderColor: 'var(--primary)' }}>
                {rc}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Candidate Retry Windows */}
      {candidate_retry_windows && candidate_retry_windows.length > 0 && (
        <div>
          <h4 style={{ fontSize: '0.85rem', fontWeight: 700, marginBottom: '0.5rem', color: 'var(--text-muted)' }}>
            Candidate Retry Distribution (Top Scored Windows)
          </h4>
          <table className="candidates-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Success Probability</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {candidate_retry_windows.slice(0, 5).map(cw => {
                const isOptimal = cw.date === recommended_retry_date;
                const p = Math.round(cw.success_probability * 100);
                return (
                  <tr key={cw.date} className={isOptimal ? 'best-date' : ''}>
                    <td>{cw.date}</td>
                    <td>
                      <span style={{ fontWeight: 700 }}>{p}%</span>
                    </td>
                    <td>{isOptimal ? '★ Optimal Window' : 'Alternative'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
