import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import {
  ArrowLeft,
  ArrowUpRight,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Play,
  RotateCw
} from 'lucide-react';

export default function AttemptDetailScreen({
  attemptId,
  onSelectAttempt,
  mandates = [],
  analysis,
  loadingAnalysis,
  analysisError,
  recoveryStatus,
  executionResult,
  executing,
  onExecuteRetry,
  onNavigateToScreen
}) {
  const [mandateDetail, setMandateDetail] = useState(null);
  const [auditRecord, setAuditRecord] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    if (!attemptId) return;
    let mounted = true;
    setMandateDetail(null);
    setAuditRecord(null);
    setLoadingDetail(true);

    const p1 = api.getMandateDetail
      ? Promise.resolve(api.getMandateDetail(attemptId)).catch(() => null)
      : Promise.resolve(null);
    const p2 = api.getAttemptAuditRecord
      ? Promise.resolve(api.getAttemptAuditRecord(attemptId)).catch(() => null)
      : Promise.resolve(null);

    Promise.all([p1, p2]).then(([detail, audit]) => {
      if (mounted) {
        setMandateDetail(detail);
        setAuditRecord(audit);
        setLoadingDetail(false);
      }
    }).catch(() => {
      if (mounted) setLoadingDetail(false);
    });

    return () => { mounted = false; };
  }, [attemptId]);

  const isStale = (analysis && analysis.attempt_id !== attemptId) ||
                  (mandateDetail && mandateDetail.attempt_id !== attemptId);

  if (loadingAnalysis || loadingDetail || !analysis || isStale) {
    return (
      <div className="fintech-screen">
        <div className="fintech-loading-state">
          <div className="fintech-spinner" />
          <span className="fintech-loading-text">Loading attempt recovery investigation for {attemptId}...</span>
        </div>
      </div>
    );
  }

  if (analysisError) {
    return (
      <div className="fintech-screen">
        <div className="fintech-error-box">
          <div className="error-title">Unable to load recovery analysis</div>
          <p className="error-desc">{analysisError}</p>
          <button
            type="button"
            className="fintech-btn secondary"
            onClick={() => onSelectAttempt(attemptId)}
          >
            Retry Investigation
          </button>
        </div>
      </div>
    );
  }

  // Derive values safely from existing API / analysis / mandate / status objects
  const amount = analysis?.amount ?? mandateDetail?.amount ?? 0;
  const failureReason = analysis?.failure_reason ?? mandateDetail?.failure_reason ?? 'INSUFFICIENT_FUNDS';
  const customerId = analysis?.customer_id ?? mandateDetail?.customer_id ?? '';
  const mandateId = analysis?.mandate_id ?? mandateDetail?.mandate_id ?? '';
  const merchantName = mandateDetail?.merchant_name ?? 'Merchant Mandate';
  const attemptDate = mandateDetail?.attempt_date ?? '2026-07-01';
  const balanceAtAttempt = mandateDetail?.balance_at_attempt ?? 0;
  const shortfall = Math.max(0, amount - balanceAtAttempt);

  const decision = analysis?.decision ?? 'PENDING';
  const reasonCodes = analysis?.reason_codes ?? [];
  const recoveryProb = analysis?.recovery_probability ?? 0;
  const recommendedDate = analysis?.recommended_retry_date ?? null;
  const candidateWindows = analysis?.candidate_retry_windows ?? [];

  const lifecycleStatus = executionResult?.result
    ? 'EXECUTED'
    : (recoveryStatus?.status ?? mandateDetail?.recovery_state ?? 'PENDING');
  const executionOutcome = executionResult?.result ?? recoveryStatus?.outcome ?? null;
  const consentGranted = recoveryStatus?.consent_granted ?? auditRecord?.consent_status === 'GRANTED';

  const isReschedule = decision === 'RESCHEDULE';
  const isDoNotRetry = decision === 'DO_NOT_RETRY';

  // Format date nicely e.g. "01 Jul 2026"
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

  return (
    <div className="fintech-screen attempt-detail-screen">
      {/* Top Header & Navigation Bar */}
      <div className="fintech-page-header">
        <div className="header-meta-group">
          <button
            type="button"
            className="fintech-back-link"
            onClick={() => onNavigateToScreen('batch-impact')}
            title="Return to Screen 1: Batch Impact"
          >
            <ArrowLeft size={14} />
            <span>Back to Batch Impact</span>
          </button>

          <div className="header-title-row">
            <h1 className="fintech-h1">ATTEMPT DETAIL</h1>
            <div className="attempt-chips">
              <span className="meta-chip mono">{attemptId}</span>
              <span className="meta-sep">•</span>
              <span className="meta-chip mono">{customerId}</span>
              <span className="meta-sep">•</span>
              <span className="meta-chip mono">{mandateId}</span>
              <span className="meta-sep">•</span>
              <span className="meta-chip">{merchantName}</span>
            </div>
          </div>
        </div>

        {/* Quick Attempt Switcher */}
        <div className="attempt-switcher">
          <label htmlFor="attempt-select" className="switcher-label">Switch Attempt:</label>
          <select
            id="attempt-select"
            className="fintech-select font-mono"
            value={attemptId || ''}
            onChange={(e) => onSelectAttempt(e.target.value)}
          >
            {mandates.map((m) => (
              <option key={m.attempt_id} value={m.attempt_id}>
                {m.attempt_id} — ₹{Number(m.amount).toLocaleString('en-IN')} ({m.recovery_state})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* SECTION 1 — FINANCIAL SUMMARY & LIFECYCLE SEQUENCE */}
      <div className="fintech-card financial-hero-card">
        <div className="financial-hero-grid">
          <div className="hero-amount-block">
            <div className="amount-label">AMOUNT AT RISK</div>
            <div className="amount-headline font-tabular">
              ₹{Number(amount).toLocaleString('en-IN')}
            </div>
            <div className="amount-subtext">
              FAILED PAYMENT • {formatDate(attemptDate)}
            </div>
          </div>

          {/* Compact Lifecycle Sequence */}
          <div className="lifecycle-stepper-block">
            <div className="lifecycle-label">RECOVERY LIFECYCLE SEQUENCE</div>
            <div className="lifecycle-track">
              {/* Step 1: Failed */}
              <div className="lifecycle-step active">
                <div className="step-dot" />
                <span className="step-name">FAILED</span>
              </div>
              <div className="step-connector active" />

              {/* Step 2: Analyzed */}
              <div className="lifecycle-step active">
                <div className="step-dot" />
                <span className="step-name">ANALYZED</span>
              </div>
              <div className={`step-connector ${isDoNotRetry ? 'blocked' : (consentGranted ? 'active' : '')}`} />

              {isDoNotRetry ? (
                <>
                  <div className="lifecycle-step highlight-muted">
                    <div className="step-dot stopped" />
                    <span className="step-name">DO_NOT_RETRY</span>
                  </div>
                  <div className="step-connector" />
                  <div className="lifecycle-step active">
                    <div className="step-dot" />
                    <span className="step-name">PAYMENT_LINK</span>
                  </div>
                </>
              ) : (
                <>
                  {/* Step 3: Consented */}
                  <div className={`lifecycle-step ${consentGranted ? 'active' : ''}`}>
                    <div className="step-dot" />
                    <span className="step-name">CONSENTED</span>
                  </div>
                  <div className={`step-connector ${lifecycleStatus === 'SCHEDULED' || lifecycleStatus === 'EXECUTED' ? 'active' : ''}`} />

                  {/* Step 4: Scheduled */}
                  <div className={`lifecycle-step ${lifecycleStatus === 'SCHEDULED' || lifecycleStatus === 'EXECUTED' ? 'active' : ''}`}>
                    <div className="step-dot" />
                    <span className="step-name">SCHEDULED</span>
                  </div>
                  <div className={`step-connector ${executionOutcome === 'SUCCESS' ? 'active' : ''}`} />

                  {/* Step 5: Executed */}
                  <div className={`lifecycle-step ${executionOutcome === 'SUCCESS' ? 'active' : ''}`}>
                    <div className="step-dot" />
                    <span className="step-name">
                      {executionOutcome === 'SUCCESS' ? 'EXECUTED (SUCCESS)' : 'EXECUTED'}
                    </span>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Two-Column Grid: FAILURE ANALYSIS & RECOVERY DECISION */}
      <div className="fintech-two-col">
        {/* SECTION 2 — FAILURE ANALYSIS */}
        <div className="fintech-card">
          <div className="card-header-row">
            <div>
              <h2 className="card-title">FAILURE ANALYSIS</h2>
              <div className="card-subtitle">Point-in-time failure investigation metrics</div>
            </div>
            <span className="card-tag">ROOT CAUSE</span>
          </div>

          <div className="definition-table">
            <div className="def-row">
              <span className="def-key">Failure reason</span>
              <span className="def-val font-mono">{failureReason.replace(/_/g, ' ')}</span>
            </div>
            <div className="def-row">
              <span className="def-key">Amount required</span>
              <span className="def-val font-tabular">₹{Number(amount).toLocaleString('en-IN')}</span>
            </div>
            <div className="def-row">
              <span className="def-key">Balance at attempt</span>
              <span className="def-val font-tabular">₹{Number(balanceAtAttempt).toLocaleString('en-IN')}</span>
            </div>
            <div className="def-row">
              <span className="def-key">Amount shortfall</span>
              <span className="def-val font-tabular highlight-teal">
                ₹{Number(shortfall).toLocaleString('en-IN')}
              </span>
            </div>
            <div className="def-row">
              <span className="def-key">Failure date</span>
              <span className="def-val">{formatDate(attemptDate)}</span>
            </div>
            <div className="def-row">
              <span className="def-key">Attempt sequence</span>
              <span className="def-val">Attempt {mandateDetail?.attempt_number ?? 1}</span>
            </div>
          </div>
        </div>

        {/* SECTION 3 — RECOVERY DECISION */}
        <div className="fintech-card">
          <div className="card-header-row">
            <div>
              <h2 className="card-title">RECOVERY DECISION</h2>
              <div className="card-subtitle">ML inference output & deterministic policy directive</div>
            </div>
            <span className="card-tag">INTELLIGENCE</span>
          </div>

          <div className="decision-metrics-grid">
            <div className="decision-metric-cell">
              <span className="metric-cell-label">Recovery probability</span>
              <span className="metric-cell-val font-tabular">
                {(recoveryProb * 100).toFixed(0)}%
              </span>
              <span className="metric-cell-sub">Point-in-time ML model score</span>
            </div>

            <div className="decision-metric-cell">
              <span className="metric-cell-label">Decision</span>
              <span className={`metric-cell-val font-mono ${isReschedule ? 'highlight-teal' : ''}`}>
                {decision}
              </span>
              <span className="metric-cell-sub">Deterministic Policy Rule</span>
            </div>

            <div className="decision-metric-cell full-width">
              <span className="metric-cell-label">Reason</span>
              <span className="metric-cell-val font-mono">
                {reasonCodes.join(', ') || 'POLICY_EVALUATED'}
              </span>
            </div>
          </div>

          {/* SINGLE CANONICAL RECOMMENDED RETRY DATE PRESENTATION */}
          <div className="canonical-recommendation-panel">
            {isReschedule && recommendedDate ? (
              <>
                <div className="canon-label">RECOMMENDED RETRY</div>
                <div className="canon-date font-tabular highlight-teal">
                  {formatDate(recommendedDate).toUpperCase()}
                </div>
                <div className="canon-subtext">
                  Optimal liquidity window identified by temporal cash-flow model.
                </div>
              </>
            ) : (
              <>
                <div className="canon-label">FALLBACK RECOMMENDATION</div>
                <div className="canon-date font-mono">ALTERNATIVE PAYMENT LINK</div>
                <div className="canon-subtext">
                  Automatic retries paused to prevent unwanted bounce charges.
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* SECTION 4 & SECTION 5: RETRY WINDOW ANALYSIS & POLICY DECISION */}
      <div className="fintech-two-col">
        {/* SECTION 4 — RETRY WINDOW ANALYSIS */}
        <div className="fintech-card">
          <div className="card-header-row">
            <div>
              <h2 className="card-title">RETRY WINDOW ANALYSIS</h2>
              <div className="card-subtitle">ML candidate distribution ranked by success probability</div>
            </div>
            <span className="card-tag">TEMPORAL INFERENCE</span>
          </div>

          {candidateWindows.length > 0 && isReschedule ? (
            <div className="fintech-table-wrapper">
              <table className="fintech-table candidate-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th style={{ textAlign: 'right' }}>Predicted recovery probability</th>
                    <th style={{ textAlign: 'right' }}>Relative position</th>
                  </tr>
                </thead>
                <tbody>
                  {candidateWindows.slice(0, 5).map((win, idx) => {
                    const isSelected = win.date === recommendedDate;
                    return (
                      <tr
                        key={win.date}
                        className={`candidate-row ${isSelected ? 'selected-window-row' : ''}`}
                      >
                        <td className="font-mono">
                          <div className="date-cell-flex">
                            <span>{formatDate(win.date)}</span>
                            {isSelected && (
                              <span className="selected-tag">SELECTED</span>
                            )}
                          </div>
                        </td>
                        <td className="font-tabular" style={{ textAlign: 'right', fontWeight: isSelected ? 700 : 500 }}>
                          {(win.success_probability * 100).toFixed(1)}%
                        </td>
                        <td className="font-tabular" style={{ textAlign: 'right', color: isSelected ? 'var(--fintech-teal-bright)' : 'var(--fintech-text-dim)' }}>
                          Rank #{idx + 1}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-analysis-notice">
              <AlertCircle size={16} />
              <span>No viable retry windows predicted above threshold. DO_NOT_RETRY policy engaged.</span>
            </div>
          )}
        </div>

        {/* SECTION 5 — POLICY DECISION / WHY */}
        <div className="fintech-card">
          <div className="card-header-row">
            <div>
              <h2 className="card-title">POLICY DECISION</h2>
              <div className="card-subtitle">Deterministic Decision Engine rules and boundaries</div>
            </div>
            <span className="card-tag">GUARDRAIL</span>
          </div>

          <div className="definition-table">
            <div className="def-row">
              <span className="def-key">RULE FIRED</span>
              <span className="def-val">
                {isReschedule ? 'High recovery probability' : 'Low recovery probability / balance protection'}
              </span>
            </div>
            <div className="def-row">
              <span className="def-key">REASON CODE</span>
              <span className="def-val font-mono">{reasonCodes[0] || 'DECISION_EVALUATED'}</span>
            </div>
            <div className="def-row">
              <span className="def-key">DIRECTIVE</span>
              <span className="def-val font-mono highlight-teal">{decision}</span>
            </div>
            <div className="def-row">
              <span className="def-key">CONSENT MANDATE</span>
              <span className="def-val">
                {analysis?.requires_customer_consent ? 'Dual-tier customer consent required' : 'Direct fallback execution'}
              </span>
            </div>
          </div>

          <div className="architectural-footnote">
            Decision Engine is authoritative; the agent only orchestrates the recovery conversation.
          </div>
        </div>
      </div>

      {/* SECTION 6 & SECTION 7: CONSENT + EXECUTION & AUDIT TRAIL PREVIEW */}
      <div className="fintech-two-col">
        {/* SECTION 6 — CONSENT + EXECUTION */}
        <div className="fintech-card">
          <div className="card-header-row">
            <div>
              <h2 className="card-title">CONSENT & EXECUTION</h2>
              <div className="card-subtitle">State progression and simulator validation</div>
            </div>
            <span className="card-tag">SYSTEM EXECUTION</span>
          </div>

          <div className="definition-table">
            <div className="def-row">
              <span className="def-key">CUSTOMER CONSENT</span>
              <span className="def-val font-mono">
                {isDoNotRetry ? 'NOT REQUIRED' : (consentGranted ? 'GRANTED' : 'PENDING')}
              </span>
            </div>
            <div className="def-row">
              <span className="def-key">ACTION</span>
              <span className="def-val">
                {isReschedule ? 'Schedule retry' : 'No retry scheduled (Fallback link)'}
              </span>
            </div>
            {isReschedule && (
              <div className="def-row">
                <span className="def-key">AUTHORIZED DATE</span>
                <span className="def-val font-tabular">{formatDate(recommendedDate)}</span>
              </div>
            )}
            <div className="def-row">
              <span className="def-key">TOOL VALIDATION</span>
              <span className="def-val verified-badge">
                <ShieldCheck size={13} />
                <span>ACCEPTED</span>
              </span>
            </div>
            <div className="def-row">
              <span className="def-key">SIMULATOR OUTCOME</span>
              <span className="def-val">
                {executionOutcome === 'SUCCESS' ? (
                  <span className="verified-badge success">
                    <CheckCircle2 size={13} />
                    <span>SUCCESS</span>
                  </span>
                ) : (
                  <span className="font-mono">{lifecycleStatus}</span>
                )}
              </span>
            </div>
          </div>

          {/* Execution Action Button */}
          {isReschedule && lifecycleStatus === 'SCHEDULED' && executionOutcome !== 'SUCCESS' && (
            <div className="execution-trigger-box">
              <button
                type="button"
                className="fintech-btn primary"
                onClick={onExecuteRetry}
                disabled={executing}
              >
                <Play size={13} className={executing ? 'spinning' : ''} />
                <span>{executing ? 'Simulating Payment...' : 'Execute Scheduled Retry'}</span>
              </button>
              <span className="execution-trigger-note">Triggers isolated UPI payment simulation rail.</span>
            </div>
          )}

          {/* Link to live conversation */}
          <div className="conversation-deep-link">
            <span className="link-note">Customer conversation state & consent flow:</span>
            <button
              type="button"
              className="fintech-btn subtle"
              onClick={() => onNavigateToScreen('agent-trace')}
            >
              <span>Open Live Agent Trace</span>
              <ArrowUpRight size={13} />
            </button>
          </div>
        </div>

        {/* SECTION 7 — AUDIT TRAIL PREVIEW */}
        <div className="fintech-card">
          <div className="card-header-row">
            <div>
              <h2 className="card-title">AUDIT TRAIL</h2>
              <div className="card-subtitle">Chronological compliance & safety boundary verification</div>
            </div>
            <span className="card-tag">SAFETY AUDIT</span>
          </div>

          {/* Chronological Event Flow Preview */}
          <div className="audit-preview-flow">
            <div className="audit-flow-item">
              <div className="flow-step-num">1</div>
              <div className="flow-step-body">
                <span className="flow-step-title">Decision rule</span>
                <span className="flow-step-desc font-mono">{decision} evaluated by Decision Engine</span>
              </div>
            </div>

            <div className="audit-flow-item">
              <div className="flow-step-num">2</div>
              <div className="flow-step-body">
                <span className="flow-step-title">Reason code</span>
                <span className="flow-step-desc font-mono">{reasonCodes[0] || 'REASON_VERIFIED'}</span>
              </div>
            </div>

            <div className="audit-flow-item">
              <div className="flow-step-num">3</div>
              <div className="flow-step-body">
                <span className="flow-step-title">Consent check</span>
                <span className="flow-step-desc">
                  {isDoNotRetry ? 'Autonomous fallback permitted' : (consentGranted ? 'Two-tier customer consent verified' : 'Pending customer authorization')}
                </span>
              </div>
            </div>

            <div className="audit-flow-item">
              <div className="flow-step-num">4</div>
              <div className="flow-step-body">
                <span className="flow-step-title">Tool validation</span>
                <span className="flow-step-desc">Safety boundary verified parameters and date match</span>
              </div>
            </div>

            <div className="audit-flow-item">
              <div className="flow-step-num">5</div>
              <div className="flow-step-body">
                <span className="flow-step-title">Execution</span>
                <span className="flow-step-desc">
                  {executionOutcome === 'SUCCESS' ? 'Payment simulator recorded recovery success' : 'Payment simulation ready on scheduled date'}
                </span>
              </div>
            </div>
          </div>

          <div className="audit-preview-footer">
            <button
              type="button"
              className="fintech-btn secondary full-width"
              onClick={() => onNavigateToScreen('agent-trace')}
            >
              <span>VIEW FULL AUDIT TRAIL</span>
              <ArrowUpRight size={13} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
