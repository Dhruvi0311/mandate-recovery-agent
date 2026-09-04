import React from 'react';
import { Play, CheckCircle2, XCircle, Clock } from 'lucide-react';

export default function ExecutionPanel({
  attemptId,
  recoveryStatus,
  onExecute,
  executing,
  executionResult
}) {
  const status = recoveryStatus?.status || 'PENDING';
  const isScheduled = status === 'SCHEDULED';
  const isExecuted = status === 'EXECUTED' || !!executionResult;

  const resultType = executionResult?.result || recoveryStatus?.outcome;
  const reasonText = executionResult?.reason || recoveryStatus?.reason;
  const scheduledDate = executionResult?.scheduled_date || recoveryStatus?.scheduled_date;

  return (
    <div className="content-card execution-panel">
      <div>
        <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.25rem' }}>
          Payment Recovery Execution
        </h3>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          State Machine Persistence & Deterministic Ground-Truth Simulator
        </div>
      </div>

      <div className="state-tracker">
        <div className="current-state-box">
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>LIFECYCLE STATE</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 800, marginTop: '0.2rem' }}>
              <span className={`status-pill ${status.toLowerCase()}`}>
                {status}
              </span>
            </div>
          </div>
          {scheduledDate && (
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>LOCKED DATE</div>
              <div style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--primary)', marginTop: '0.2rem' }}>
                {scheduledDate}
              </div>
            </div>
          )}
        </div>

        {/* Execute Button */}
        <button
          type="button"
          className="execute-btn"
          disabled={!isScheduled || executing}
          onClick={onExecute}
        >
          <Play size={18} />
          <span>{executing ? 'Simulating Settlement...' : isScheduled ? 'Execute Scheduled Retry' : 'Awaiting Schedule Authorization'}</span>
        </button>
      </div>

      {/* Outcome Banner */}
      {resultType ? (
        <div className={`outcome-box ${resultType.toLowerCase()}`}>
          <div className={`outcome-header ${resultType.toLowerCase()}`}>
            <span>Payment Simulation: {resultType}</span>
            {resultType === 'SUCCESS' ? <CheckCircle2 size={22} /> : <XCircle size={22} />}
          </div>
          <div className="outcome-desc">
            {reasonText || (resultType === 'SUCCESS' ? 'Funds successfully recovered from customer bank account.' : 'Payment debit could not be recovered.')}
          </div>
          {recoveryStatus?.execution_time && (
            <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '0.3rem' }}>
              Executed at: {new Date(recoveryStatus.execution_time).toLocaleString()}
            </div>
          )}
        </div>
      ) : (
        <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', textAlign: 'center', padding: '1rem 0' }}>
          {isScheduled
            ? 'Mandate retry is scheduled in SQLite. Click above to simulate payment execution.'
            : 'Complete the conversational negotiation above to obtain consent and schedule a retry.'}
        </div>
      )}
    </div>
  );
}
