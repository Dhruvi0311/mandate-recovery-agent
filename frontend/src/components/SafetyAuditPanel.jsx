import React, { useState, useEffect } from 'react';
import { ShieldAlert, ShieldCheck, AlertOctagon, CheckCircle2, XCircle, ChevronDown, ChevronUp, RefreshCw, Eye } from 'lucide-react';
import { api } from '../services/api';

export default function SafetyAuditPanel({
  selectedAttemptId,
  recoveryStatus,
  executionResult
}) {
  const [auditData, setAuditData] = useState(null);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(true);
  const [simulatingRogue, setSimulatingRogue] = useState(false);
  const [rogueResult, setRogueResult] = useState(null);

  const fetchAuditLog = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getAuditLog();
      setAuditData(data);

      if (selectedAttemptId) {
        try {
          const rec = await api.getAttemptAuditRecord(selectedAttemptId);
          setSelectedRecord(rec);
        } catch {
          // Fallback to record in list if available
          const found = data?.records?.find(r => r.attempt_id === selectedAttemptId);
          setSelectedRecord(found || null);
        }
      } else if (data?.records?.length > 0) {
        setSelectedRecord(data.records[0]);
      }
    } catch (err) {
      setError(err.message || 'Failed to fetch safety audit trail');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAuditLog();
  }, [selectedAttemptId, recoveryStatus?.status, executionResult?.result]);

  const handleSimulateRogue = async () => {
    if (!selectedAttemptId) return;
    setSimulatingRogue(true);
    setRogueResult(null);
    try {
      // Execute the real adversarial scenario through backend tool boundary
      const res = await api.simulateRogueAgent(selectedAttemptId);
      setRogueResult(res);
      await fetchAuditLog();
    } catch (err) {
      setError(err.message || 'Rogue agent simulation failed');
      await fetchAuditLog();
    } finally {
      setSimulatingRogue(false);
    }
  };

  const blockedCount = auditData?.blocked_violations_count ?? 0;
  const isBlocked = selectedRecord?.is_blocked || selectedRecord?.validation_result === 'BLOCKED';

  return (
    <div className="content-card safety-audit-panel" style={{ marginTop: '1.25rem' }}>
      {/* Header with Blocked Counter Banner */}
      <div className="safety-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <div style={{
            background: blockedCount > 0 ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)',
            color: blockedCount > 0 ? '#ef4444' : '#10b981',
            padding: '0.4rem',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            {blockedCount > 0 ? <ShieldAlert size={22} /> : <ShieldCheck size={22} />}
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0 }}>Safety Boundary & Compliant Audit Trail</h3>
              <span className="badge" style={{
                background: 'rgba(59, 130, 246, 0.12)',
                color: 'var(--primary)',
                fontSize: '0.7rem',
                fontWeight: 600,
                padding: '0.15rem 0.45rem',
                borderRadius: '4px'
              }}>
                Non-Bypassable
              </span>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
              Deterministic Escalation & Stopping Rules • SQLite Persisted
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {/* Blocked Hallucination Counter Badge */}
          <div
            className="blocked-counter-badge"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.45rem',
              background: blockedCount > 0 ? 'rgba(239, 68, 68, 0.12)' : 'rgba(245, 158, 11, 0.12)',
              border: `1px solid ${blockedCount > 0 ? 'rgba(239, 68, 68, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
              color: blockedCount > 0 ? '#f87171' : '#fbbf24',
              padding: '0.35rem 0.65rem',
              borderRadius: '6px',
              fontSize: '0.8rem',
              fontWeight: 700
            }}
            title="Count of unauthorized actions, missing consent attempts, or hallucinated dates blocked by safety boundary"
          >
            <AlertOctagon size={16} />
            <span id="blocked-attempts-count">{blockedCount} blocked hallucination/consent-violation attempts</span>
          </div>

          <button
            type="button"
            className="btn-icon"
            onClick={fetchAuditLog}
            disabled={loading}
            title="Refresh Audit Trail"
            style={{ padding: '0.4rem', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--bg-subtle)' }}
          >
            <RefreshCw size={15} className={loading ? 'spinning' : ''} />
          </button>

          <button
            type="button"
            className="btn-icon"
            onClick={() => setExpanded(!expanded)}
            style={{ padding: '0.4rem', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--bg-subtle)' }}
          >
            {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          </button>
        </div>
      </div>

      {expanded && (
        <div style={{ marginTop: '0.9rem' }}>
          {/* Selected Attempt Banner & Adversarial Test Action */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-subtle)', padding: '0.5rem 0.75rem', borderRadius: '6px', fontSize: '0.8rem', marginBottom: '0.85rem' }}>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>Target Attempt: </span>
              <strong style={{ color: 'var(--text)' }}>{selectedAttemptId || 'None selected'}</strong>
              {selectedRecord && (
                <span style={{ marginLeft: '0.75rem', color: 'var(--text-dim)' }}>
                  Customer: {selectedRecord.customer_id} | Lifecycle: <strong>{selectedRecord.lifecycle_status}</strong>
                </span>
              )}
            </div>

            {selectedAttemptId && (
              <button
                type="button"
                className="action-btn"
                id="simulate-rogue-btn"
                onClick={handleSimulateRogue}
                disabled={simulatingRogue}
                style={{
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  padding: '0.35rem 0.75rem',
                  background: 'rgba(239, 68, 68, 0.15)',
                  color: '#f87171',
                  border: '1px solid rgba(239, 68, 68, 0.35)',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem'
                }}
                title="Runs the adversarial MockLLM scenario to attempt an unauthorized retry date (2099-01-01) against the real tool boundary"
              >
                <AlertOctagon size={14} />
                <span>{simulatingRogue ? 'Running Boundary Intercept...' : 'Simulate Rogue Agent'}</span>
              </button>
            )}
          </div>

          {/* Real-Time Rogue Simulation Intercept Flow */}
          {rogueResult && (
            <div className="rogue-simulation-box" style={{
              background: 'rgba(239, 68, 68, 0.08)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              borderRadius: '8px',
              padding: '0.85rem 1rem',
              marginBottom: '0.85rem',
              fontFamily: 'monospace'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <strong style={{ color: '#f87171', fontSize: '0.85rem' }}>🛑 Adversarial Simulation: Rogue Agent Intercepted</strong>
                <span style={{ fontSize: '0.7rem', background: 'rgba(239, 68, 68, 0.2)', color: '#fca5a5', padding: '0.15rem 0.4rem', borderRadius: '4px' }}>
                  Real Tool Boundary Check
                </span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem', fontSize: '0.8rem', color: 'var(--text)' }}>
                <div><span style={{ color: 'var(--text-muted)' }}>Agent: </span><strong>Rogue Agent</strong></div>
                <div style={{ color: 'var(--text-dim)', paddingLeft: '1rem' }}>↓</div>
                <div><span style={{ color: 'var(--text-muted)' }}>Attempted: </span><code style={{ color: '#f59e0b', background: 'rgba(0,0,0,0.3)', padding: '0.1rem 0.3rem', borderRadius: '3px' }}>{rogueResult.attempted_action}</code></div>
                <div style={{ color: 'var(--text-dim)', paddingLeft: '1rem' }}>↓</div>
                <div style={{ color: '#ef4444', fontWeight: 800 }}>🛑 BLOCKED BY TOOL BOUNDARY</div>
                <div style={{ color: 'var(--text-dim)', paddingLeft: '1rem' }}>↓</div>
                <div><span style={{ color: 'var(--text-muted)' }}>Reason: </span><span style={{ color: '#fca5a5' }}>{rogueResult.rejection_reason}</span></div>
                <div style={{ color: 'var(--text-dim)', paddingLeft: '1rem' }}>↓</div>
                <div style={{ color: '#10b981', fontWeight: 600 }}>✓ Audit event recorded (Blocked Counter: {rogueResult.blocked_violations_count})</div>
              </div>
            </div>
          )}

          {/* Blocked Alert Banner if Attempt has Violation */}
          {isBlocked && (
            <div style={{
              background: 'rgba(239, 68, 68, 0.12)',
              border: '1px solid rgba(239, 68, 68, 0.35)',
              color: '#fca5a5',
              padding: '0.65rem 0.85rem',
              borderRadius: '6px',
              marginBottom: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.6rem',
              fontSize: '0.82rem'
            }}>
              <XCircle size={18} color="#ef4444" style={{ flexShrink: 0 }} />
              <div>
                <strong>SAFETY VIOLATION BLOCKED: </strong>
                <span>{selectedRecord?.violation_type || 'BOUNDARY_REJECTION'} — </span>
                <span>{selectedRecord?.validation_details || 'The tool boundary blocked an unauthorized execution attempt.'}</span>
              </div>
            </div>
          )}

          {/* Six-Stage Safety Boundary Stepper: Rule -> Reason -> Consent -> Action -> Validation -> Outcome */}
          <div style={{ marginBottom: '1rem' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.4rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Safety Boundary Enforcement Flow
            </div>
            <div className="audit-flow-grid" style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
              gap: '0.5rem'
            }}>
              {/* 1. Rule */}
              <div className="audit-stage-card" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '6px', padding: '0.6rem' }}>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>1. DECISION RULE</div>
                <div style={{ fontSize: '0.82rem', fontWeight: 700, marginTop: '0.15rem', color: 'var(--primary)' }}>
                  {selectedRecord?.decision || 'EVALUATING'}
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '0.2rem' }}>
                  Prob: {selectedRecord ? `${(selectedRecord.recovery_probability * 100).toFixed(0)}%` : '--'}
                </div>
              </div>

              {/* 2. Reason */}
              <div className="audit-stage-card" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '6px', padding: '0.6rem' }}>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>2. REASON CODES</div>
                <div style={{ fontSize: '0.75rem', fontWeight: 600, marginTop: '0.15rem' }}>
                  {selectedRecord?.reason_codes?.slice(0, 2).join(', ') || 'NONE'}
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '0.2rem' }}>
                  {selectedRecord?.consent_requirement ? 'Consent Mandatory' : 'Consent Optional'}
                </div>
              </div>

              {/* 3. Consent */}
              <div className="audit-stage-card" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '6px', padding: '0.6rem' }}>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>3. CONSENT CHECK</div>
                <div style={{
                  fontSize: '0.8rem',
                  fontWeight: 700,
                  marginTop: '0.15rem',
                  color: selectedRecord?.consent_status === 'GRANTED' ? '#10b981' : (selectedRecord?.consent_status === 'REJECTED' ? '#ef4444' : '#f59e0b')
                }}>
                  {selectedRecord?.consent_status || 'PENDING'}
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '0.2rem' }}>
                  {selectedRecord?.consent_status === 'GRANTED' ? 'Explicit Agreement' : 'Awaiting Consent'}
                </div>
              </div>

              {/* 4. Action */}
              <div className="audit-stage-card" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '6px', padding: '0.6rem' }}>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>4. REQUESTED ACTION</div>
                <div style={{ fontSize: '0.75rem', fontWeight: 600, marginTop: '0.15rem', wordBreak: 'break-all' }}>
                  {selectedRecord?.requested_action || (selectedRecord?.recommended_retry_date ? `schedule_retry(${selectedRecord.recommended_retry_date})` : 'None')}
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '0.2rem' }}>
                  Tool invocation
                </div>
              </div>

              {/* 5. Validation */}
              <div className="audit-stage-card" style={{
                background: isBlocked ? 'rgba(239, 68, 68, 0.08)' : 'var(--bg-card)',
                border: `1px solid ${isBlocked ? 'rgba(239, 68, 68, 0.3)' : 'var(--border)'}`,
                borderRadius: '6px',
                padding: '0.6rem'
              }}>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>5. TOOL VALIDATION</div>
                <div style={{
                  fontSize: '0.82rem',
                  fontWeight: 700,
                  marginTop: '0.15rem',
                  color: isBlocked ? '#ef4444' : (selectedRecord?.validation_result === 'ACCEPTED' ? '#10b981' : '#f59e0b')
                }}>
                  {isBlocked ? 'BLOCKED' : (selectedRecord?.validation_result || 'PENDING')}
                </div>
                <div style={{ fontSize: '0.7rem', color: isBlocked ? '#f87171' : 'var(--text-dim)', marginTop: '0.2rem' }}>
                  {isBlocked ? (selectedRecord?.violation_type || 'Safety Rejected') : 'Boundary verified'}
                </div>
              </div>

              {/* 6. Outcome */}
              <div className="audit-stage-card" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '6px', padding: '0.6rem' }}>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>6. OUTCOME</div>
                <div style={{
                  fontSize: '0.82rem',
                  fontWeight: 700,
                  marginTop: '0.15rem',
                  color: selectedRecord?.execution_outcome === 'SUCCESS' ? '#10b981' : (selectedRecord?.execution_outcome === 'FAILURE' ? '#ef4444' : 'var(--text)')
                }}>
                  {selectedRecord?.execution_outcome || 'NOT_EXECUTED'}
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '0.2rem' }}>
                  Lifecycle: {selectedRecord?.lifecycle_status || 'PENDING'}
                </div>
              </div>
            </div>
          </div>

          {/* Chronological Event Log for Selected Attempt */}
          {selectedRecord?.timeline && selectedRecord.timeline.length > 0 && (
            <div style={{ background: 'var(--bg-subtle)', borderRadius: '6px', padding: '0.65rem 0.85rem' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.4rem', textTransform: 'uppercase' }}>
                Chronological Audit Events ({selectedRecord.timeline.length})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                {selectedRecord.timeline.map((evt, idx) => (
                  <div key={idx} style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '0.5rem',
                    fontSize: '0.75rem',
                    padding: '0.25rem 0',
                    borderBottom: idx < selectedRecord.timeline.length - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none'
                  }}>
                    <span style={{
                      fontWeight: 700,
                      padding: '0.1rem 0.35rem',
                      borderRadius: '3px',
                      fontSize: '0.68rem',
                      background: evt.status === 'BLOCKED' || evt.status === 'REJECTED' || evt.status === 'FAILURE'
                        ? 'rgba(239, 68, 68, 0.2)'
                        : (evt.status === 'PASSED' || evt.status === 'ACCEPTED' || evt.status === 'SUCCESS'
                          ? 'rgba(16, 185, 129, 0.2)'
                          : 'rgba(59, 130, 246, 0.2)'),
                      color: evt.status === 'BLOCKED' || evt.status === 'REJECTED' || evt.status === 'FAILURE'
                        ? '#f87171'
                        : (evt.status === 'PASSED' || evt.status === 'ACCEPTED' || evt.status === 'SUCCESS'
                          ? '#34d399'
                          : '#60a5fa')
                    }}>
                      {evt.status}
                    </span>
                    <div style={{ flex: 1 }}>
                      <strong>{evt.label}: </strong>
                      <span style={{ color: 'var(--text-muted)' }}>{evt.detail}</span>
                    </div>
                    <span style={{ color: 'var(--text-dim)', fontSize: '0.68rem', whiteSpace: 'nowrap' }}>
                      {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : ''}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
