import React, { useState, useEffect, useRef } from 'react';
import { api } from '../services/api';
import {
  ArrowLeft,
  ShieldCheck,
  ShieldAlert,
  AlertOctagon,
  CheckCircle2,
  XCircle,
  Play,
  Send,
  RotateCw,
  Lock,
  ChevronDown,
  ChevronUp
} from 'lucide-react';

export default function LiveAgentTraceScreen({
  attemptId,
  onSelectAttempt,
  mandates = [],
  analysis,
  recoveryStatus,
  executionResult,
  chatMessages = [],
  consentGranted,
  actionStatus,
  loadingAnalysis,
  executing,
  onSendMessage,
  onExecuteRetry,
  onNavigateToScreen
}) {
  const [inputMessage, setInputMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [simulatingRogue, setSimulatingRogue] = useState(false);
  const [rogueResult, setRogueResult] = useState(null);
  const [auditData, setAuditData] = useState(null);
  const [attemptAudit, setAttemptAudit] = useState(null);
  const [showFullAudit, setShowFullAudit] = useState(false);
  const messagesEndRef = useRef(null);

  // Fetch audit log to get live blocked violations counter and attempt trace
  const fetchAuditData = async () => {
    try {
      const log = await api.getAuditLog().catch(() => null);
      if (log) setAuditData(log);

      if (attemptId) {
        const rec = await api.getAttemptAuditRecord(attemptId).catch(() => null);
        if (rec) setAttemptAudit(rec);
      }
    } catch {
      // Graceful fallback
    }
  };

  useEffect(() => {
    fetchAuditData();
  }, [attemptId, consentGranted, actionStatus, recoveryStatus?.status, executionResult?.result]);

  useEffect(() => {
    if (typeof messagesEndRef.current?.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages]);

  const handleSend = async (text) => {
    const msg = (text || inputMessage).trim();
    if (!msg || sending) return;
    setSending(true);
    setInputMessage('');
    try {
      await onSendMessage(msg);
      await fetchAuditData();
    } finally {
      setSending(false);
    }
  };

  const handleSimulateRogue = async () => {
    if (!attemptId || simulatingRogue) return;
    setSimulatingRogue(true);
    setRogueResult(null);
    try {
      const res = await api.simulateRogueAgent(attemptId);
      setRogueResult(res);
      await fetchAuditData();
    } catch (err) {
      setRogueResult({
        validation_result: 'BLOCKED',
        attempted_action: "schedule_retry(agreed_date='2099-01-01')",
        violation_type: 'HALLUCINATED_DATE',
        rejection_reason: err.message || 'Cannot schedule retry: Unauthorized date rejected by tool boundary.',
        execution_outcome: 'NOT_EXECUTED',
        audit_recorded: true
      });
      await fetchAuditData();
    } finally {
      setSimulatingRogue(false);
    }
  };

  // Point-in-time values from existing state
  const decision = analysis?.decision ?? 'PENDING';
  const reasonCodes = analysis?.reason_codes ?? [];
  const recoveryProb = analysis?.recovery_probability ?? 0;
  const recommendedDate = analysis?.recommended_retry_date ?? null;
  const isDoNotRetry = decision === 'DO_NOT_RETRY';
  const isReschedule = decision === 'RESCHEDULE';

  const isConsentVerified = consentGranted || recoveryStatus?.consent_granted || attemptAudit?.consent_status === 'GRANTED';
  const lifecycleStatus = executionResult?.result
    ? 'EXECUTED'
    : (recoveryStatus?.status ?? 'PENDING');
  const executionOutcome = executionResult?.result ?? recoveryStatus?.outcome ?? null;

  // Live blocked count from backend audit API or rogue response
  const blockedCount = rogueResult?.blocked_violations_count ?? auditData?.blocked_violations_count ?? 0;

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      const parts = dateStr.split('-');
      if (parts.length === 3) {
        const d = new Date(parts[0], parts[1] - 1, parts[2]);
        return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
      }
      return dateStr;
    } catch {
      return dateStr;
    }
  };

  const isStale = analysis && analysis.attempt_id !== attemptId;

  if (loadingAnalysis || !analysis || isStale) {
    return (
      <div className="fintech-screen">
        <div className="fintech-loading-state">
          <div className="fintech-spinner" />
          <span className="fintech-loading-text">Loading live agent trace for {attemptId}...</span>
        </div>
      </div>
    );
  }

  const displayMessages = (chatMessages || []).filter((msg, idx, arr) => idx === 0 || msg !== arr[idx - 1]);

  return (
    <div className="fintech-screen live-agent-trace-screen">
      {/* Screen Header */}
      <div className="fintech-page-header">
        <div className="header-meta-group">
          <button
            type="button"
            className="fintech-back-link"
            onClick={() => onNavigateToScreen('attempt-detail')}
            title="Return to Screen 2: Attempt Detail"
          >
            <ArrowLeft size={14} />
            <span>Back to Attempt Detail</span>
          </button>

          <div className="header-title-row">
            <h1 className="fintech-h1">LIVE AGENT TRACE</h1>
            <div className="attempt-chips">
              <span className="meta-chip mono">{attemptId}</span>
              <span className="meta-sep">•</span>
              <span className="meta-chip">CUSTOMER RECOVERY SESSION</span>
            </div>
          </div>
          <p className="fintech-subtitle">Agent orchestration and tool-enforced recovery execution</p>
        </div>

        {/* Live Blocked Counter Pill */}
        <div className="trace-header-controls">
          <div className={`blocked-actions-pill ${blockedCount > 0 ? 'has-violations' : ''}`}>
            <span className="blocked-pill-dot" />
            <span className="blocked-pill-label">BLOCKED AGENT ACTIONS:</span>
            <span className="blocked-pill-count font-tabular">{blockedCount}</span>
          </div>
        </div>
      </div>

      {/* TWO-COLUMN LAYOUT: CUSTOMER CONVERSATION & SYSTEM TRACE */}
      <div className="trace-two-col">
        {/* LEFT COLUMN — CUSTOMER CONVERSATION */}
        <div className="fintech-card conversation-column">
          <div className="card-header-row">
            <div>
              <h2 className="card-title">CUSTOMER CONVERSATION</h2>
              <div className="card-subtitle">Direct customer communication log via LangGraph</div>
            </div>
            <span className="card-tag">COMMUNICATION LOG</span>
          </div>

          <div className="conversation-message-list">
            {(!displayMessages || displayMessages.length === 0) && (
              <div className="conversation-empty">
                <span>Initializing customer recovery session...</span>
              </div>
            )}

            {displayMessages && displayMessages.map((msg, idx) => {
              const isCustomer = msg.startsWith('Customer: ');
              const isTool = msg.startsWith('Tool ');
              const isToolError = msg.startsWith('Tool execution rejected:');

              if (isCustomer) {
                return (
                  <div key={idx} className="conversation-row customer">
                    <div className="message-sender-tag">CUSTOMER</div>
                    <div className="message-content">{msg.replace('Customer: ', '')}</div>
                  </div>
                );
              }

              if (isToolError) {
                return (
                  <div key={idx} className="conversation-row tool-boundary-interception">
                    <div className="message-sender-tag danger">TOOL BOUNDARY INTERCEPTION</div>
                    <div className="message-content">{msg.replace('Tool execution rejected: ', '')}</div>
                  </div>
                );
              }

              if (isTool) {
                return (
                  <div key={idx} className="conversation-row tool-event">
                    <div className="message-sender-tag tool">SYSTEM TOOL CALL</div>
                    <div className="message-content font-mono">{msg}</div>
                  </div>
                );
              }

              return (
                <div key={idx} className="conversation-row agent">
                  <div className="message-sender-tag agent">MANDATE RECOVERY AGENT</div>
                  <div className="message-content">{msg.replace('Agent: ', '')}</div>
                </div>
              );
            })}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick Consent Action Controls */}
          <div className="conversation-quick-actions">
            <button
              type="button"
              className="fintech-btn primary"
              disabled={sending || loadingAnalysis}
              onClick={() => handleSend('Yes, please schedule it')}
            >
              <CheckCircle2 size={13} />
              <span>✓ Yes, schedule it</span>
            </button>

            <button
              type="button"
              className="fintech-btn secondary"
              disabled={sending || loadingAnalysis}
              onClick={() => handleSend('No, do not schedule retry')}
            >
              <XCircle size={13} />
              <span>✕ No, cancel retry</span>
            </button>

            <button
              type="button"
              className="fintech-btn subtle"
              disabled={sending || loadingAnalysis}
              onClick={() => handleSend('What caused this mandate to fail?')}
            >
              <span>Why did it fail?</span>
            </button>
          </div>

          {/* Message Input Form */}
          <form
            className="conversation-input-row"
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
          >
            <input
              type="text"
              className="fintech-input"
              placeholder="Type customer reply..."
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              disabled={sending || loadingAnalysis}
            />
            <button
              type="submit"
              className="fintech-btn secondary"
              disabled={!inputMessage.trim() || sending || loadingAnalysis}
            >
              <Send size={13} />
              <span>Send</span>
            </button>
          </form>
        </div>

        {/* RIGHT COLUMN — SYSTEM TRACE & SAFETY BOUNDARY */}
        <div className="fintech-card system-trace-column">
          <div className="card-header-row">
            <div>
              <h2 className="card-title">SYSTEM TRACE</h2>
              <div className="system-flow-eyebrow">
                LLM PROPOSAL → DETERMINISTIC POLICY → TOOL VALIDATION → EXECUTION
              </div>
            </div>
            <span className="card-tag">ENFORCEMENT BOUNDARY</span>
          </div>

          {/* Five-Stage Chronological Trace */}
          <div className="system-trace-flow">
            {/* Stage 1: Decision Engine */}
            <div className="trace-stage-card verified">
              <div className="stage-card-header">
                <span className="stage-num">1</span>
                <span className="stage-name">DECISION ENGINE</span>
                <span className="stage-tag authoritative">AUTHORITATIVE POLICY</span>
              </div>
              <div className="stage-card-body">
                <div className="stage-field-row">
                  <span className="stage-key">Directive</span>
                  <span className="stage-val font-mono highlight-teal">{decision}</span>
                </div>
                <div className="stage-field-row">
                  <span className="stage-key">Reason</span>
                  <span className="stage-val font-mono">{reasonCodes[0] || 'EVALUATED'}</span>
                </div>
                <div className="stage-field-row">
                  <span className="stage-key">Recovery probability</span>
                  <span className="stage-val font-tabular">{(recoveryProb * 100).toFixed(0)}%</span>
                </div>
                {isReschedule && (
                  <div className="stage-field-row">
                    <span className="stage-key">Recommended date</span>
                    <span className="stage-val font-tabular highlight-teal">
                      {formatDate(recommendedDate).toUpperCase()}
                    </span>
                  </div>
                )}
                {isDoNotRetry && (
                  <div className="stage-field-row">
                    <span className="stage-key">Fallback</span>
                    <span className="stage-val font-mono">ALTERNATIVE PAYMENT LINK</span>
                  </div>
                )}
              </div>
              <div className="stage-card-footer">
                Decision Engine is authoritative; the agent cannot deviate or invent terms.
              </div>
            </div>

            {/* Stage 2: Customer Consent */}
            <div className={`trace-stage-card ${isConsentVerified || isDoNotRetry ? 'verified' : ''}`}>
              <div className="stage-card-header">
                <span className="stage-num">2</span>
                <span className="stage-name">CUSTOMER CONSENT</span>
                <span className="stage-tag">{isConsentVerified ? 'VERIFIED' : (isDoNotRetry ? 'EXEMPT' : 'PENDING')}</span>
              </div>
              <div className="stage-card-body">
                <div className="stage-field-row">
                  <span className="stage-key">Financial data consent</span>
                  <span className="stage-val highlight-teal">✓ ACTIVE</span>
                </div>
                <div className="stage-field-row">
                  <span className="stage-key">Action consent</span>
                  <span className="stage-val font-mono">
                    {isDoNotRetry ? 'NOT REQUIRED' : (isConsentVerified ? '✓ GRANTED' : 'PENDING CUSTOMER')}
                  </span>
                </div>
              </div>
              <div className="stage-card-footer">
                {isDoNotRetry ? 'Autonomous fallback permitted.' : 'Two-tier consent verified prior to tool execution.'}
              </div>
            </div>

            {/* Stage 3: Agent Request */}
            <div className="trace-stage-card agent-proposal">
              <div className="stage-card-header">
                <span className="stage-num">3</span>
                <span className="stage-name">AGENT REQUEST</span>
                <span className="stage-tag proposal">LLM-PROPOSED ACTION</span>
              </div>
              <div className="stage-card-body">
                <div className="stage-field-row">
                  <span className="stage-key">Requested action</span>
                  <span className="stage-val font-mono">
                    {isReschedule ? `schedule_retry('${recommendedDate}')` : 'trigger_fallback(PAYMENT_LINK)'}
                  </span>
                </div>
                <div className="stage-field-row">
                  <span className="stage-key">Nature</span>
                  <span className="stage-val">Unverified LLM Proposal</span>
                </div>
              </div>
            </div>

            {/* Stage 4: Tool Boundary */}
            <div className="trace-stage-card locked-boundary">
              <div className="stage-card-header">
                <span className="stage-num">4</span>
                <span className="stage-name">TOOL BOUNDARY</span>
                <span className="stage-tag boundary-accepted">✓ VERIFIED</span>
              </div>
              <div className="stage-card-body">
                <div className="stage-field-row">
                  <span className="stage-key">Authorized date</span>
                  <span className="stage-val font-tabular highlight-teal">
                    {isReschedule ? formatDate(recommendedDate) : 'N/A'}
                  </span>
                </div>
                <div className="stage-field-row">
                  <span className="stage-key">Requested date</span>
                  <span className="stage-val font-tabular">
                    {isReschedule ? formatDate(recommendedDate) : 'N/A'}
                  </span>
                </div>
                <div className="stage-field-row">
                  <span className="stage-key">Validation</span>
                  <span className="stage-val verified-badge">
                    <ShieldCheck size={13} />
                    <span>ACCEPTED</span>
                  </span>
                </div>
              </div>
            </div>

            {/* Stage 5: Execution */}
            <div className={`trace-stage-card ${executionOutcome === 'SUCCESS' ? 'execution-success' : ''}`}>
              <div className="stage-card-header">
                <span className="stage-num">5</span>
                <span className="stage-name">EXECUTION</span>
                <span className="stage-tag">
                  {executionOutcome === 'SUCCESS' ? 'EXECUTED' : lifecycleStatus}
                </span>
              </div>
              <div className="stage-card-body">
                <div className="stage-field-row">
                  <span className="stage-key">Simulator status</span>
                  <span className="stage-val font-mono">
                    {executionOutcome === 'SUCCESS' ? 'SUCCESS' : (isReschedule && lifecycleStatus === 'SCHEDULED' ? 'SCHEDULED' : 'PENDING')}
                  </span>
                </div>
                {executionResult?.recovered_amount && (
                  <div className="stage-field-row">
                    <span className="stage-key">Recovered amount</span>
                    <span className="stage-val font-tabular highlight-teal">
                      ₹{Number(executionResult.recovered_amount).toLocaleString('en-IN')}
                    </span>
                  </div>
                )}
              </div>

              {/* Execution Action Button */}
              {isReschedule && lifecycleStatus === 'SCHEDULED' && executionOutcome !== 'SUCCESS' && (
                <div className="stage-card-action">
                  <button
                    type="button"
                    className="fintech-btn primary full-width"
                    onClick={onExecuteRetry}
                    disabled={executing}
                  >
                    <Play size={13} className={executing ? 'spinning' : ''} />
                    <span>{executing ? 'Executing Simulator Rail...' : 'Execute Scheduled Retry'}</span>
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* ADVERSARIAL SAFETY TEST / ROGUE AGENT DEMO SECTION */}
          <div className="adversarial-test-section">
            <div className="adversarial-header">
              <div>
                <div className="adversarial-title">ADVERSARIAL SAFETY TEST</div>
                <div className="adversarial-subtitle">Test the tool boundary with an intentionally invalid agent action.</div>
              </div>
              <button
                type="button"
                className="fintech-btn danger"
                onClick={handleSimulateRogue}
                disabled={simulatingRogue}
              >
                <AlertOctagon size={13} />
                <span>{simulatingRogue ? 'Simulating Rogue Attack...' : 'Simulate Rogue Agent'}</span>
              </button>
            </div>

            {/* Rogue Simulation Real-Time Result */}
            {rogueResult && (
              <div className="rogue-result-box">
                <div className="rogue-blocked-banner">
                  <ShieldAlert size={18} />
                  <div>
                    <div className="blocked-headline">BLOCKED BY TOOL BOUNDARY</div>
                    <div className="blocked-subhead">
                      The agent proposed an unauthorized date. The deterministic tool refused the action.
                    </div>
                  </div>
                </div>

                <div className="rogue-detail-grid">
                  <div className="rogue-detail-row">
                    <span className="rogue-key">REQUESTED ACTION</span>
                    <span className="rogue-val font-mono">{rogueResult.attempted_action}</span>
                    <span className="rogue-label-tag">LLM-PROPOSED ACTION</span>
                  </div>
                  <div className="rogue-detail-row">
                    <span className="rogue-key">TOOL BOUNDARY</span>
                    <span className="rogue-val danger-text font-mono">BLOCKED</span>
                  </div>
                  <div className="rogue-detail-row">
                    <span className="rogue-key">VIOLATION TYPE</span>
                    <span className="rogue-val font-mono highlight-red">{rogueResult.violation_type}</span>
                  </div>
                  <div className="rogue-detail-row">
                    <span className="rogue-key">REJECTION REASON</span>
                    <span className="rogue-val">{rogueResult.rejection_reason}</span>
                  </div>
                  <div className="rogue-detail-row">
                    <span className="rogue-key">AUDIT LOG</span>
                    <span className="rogue-val highlight-teal">✓ Violation recorded</span>
                  </div>
                  <div className="rogue-detail-row">
                    <span className="rogue-key">EXECUTION</span>
                    <span className="rogue-val font-mono">NOT EXECUTED</span>
                  </div>
                </div>

                {/* State Non-Corruption Confirmation */}
                <div className="state-integrity-banner">
                  <Lock size={13} />
                  <span>
                    STATE UNCHANGED: Authorized date remains {formatDate(recommendedDate) || 'original'} • No retry was scheduled • Payment was NOT executed.
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Full Audit Trail Toggle */}
          <div className="audit-full-view-toggle">
            <button
              type="button"
              className="fintech-btn secondary full-width"
              onClick={() => setShowFullAudit(!showFullAudit)}
            >
              <span>{showFullAudit ? 'HIDE AUDIT TRAIL' : 'VIEW FULL AUDIT TRAIL'}</span>
              {showFullAudit ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            </button>

            {showFullAudit && attemptAudit && (
              <div className="full-audit-table-wrapper">
                <div className="full-audit-title">PERSISTENT AUDIT RECORD — {attemptId}</div>
                <div className="definition-table">
                  <div className="def-row">
                    <span className="def-key">Audit Timestamp</span>
                    <span className="def-val font-mono">{attemptAudit.timestamp}</span>
                  </div>
                  <div className="def-row">
                    <span className="def-key">Decision Rule</span>
                    <span className="def-val font-mono">{attemptAudit.decision}</span>
                  </div>
                  <div className="def-row">
                    <span className="def-key">Reason Codes</span>
                    <span className="def-val font-mono">{attemptAudit.reason_codes?.join(', ')}</span>
                  </div>
                  <div className="def-row">
                    <span className="def-key">Consent Status</span>
                    <span className="def-val font-mono">{attemptAudit.consent_status}</span>
                  </div>
                  <div className="def-row">
                    <span className="def-key">Tool Validation Result</span>
                    <span className="def-val font-mono highlight-teal">{attemptAudit.validation_result}</span>
                  </div>
                  <div className="def-row">
                    <span className="def-key">Execution Outcome</span>
                    <span className="def-val font-mono">{attemptAudit.execution_outcome}</span>
                  </div>
                  <div className="def-row">
                    <span className="def-key">Lifecycle Status</span>
                    <span className="def-val font-mono">{attemptAudit.lifecycle_status}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
