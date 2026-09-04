import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import {
  TrendingUp,
  ShieldCheck,
  RotateCcw,
  AlertOctagon,
  RefreshCw,
  BarChart3,
  IndianRupee,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  HelpCircle
} from 'lucide-react';

export default function BatchImpactPanel() {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [isExpanded, setIsExpanded] = useState(true);

  const fetchReport = async (force = false) => {
    if (force) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);
    try {
      const data = await api.getBatchReport(force);
      setReport(data);
    } catch (err) {
      setError(err.message || 'Failed to load batch impact report.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchReport();
  }, []);

  if (loading && !report) {
    return (
      <section className="batch-impact-card">
        <div className="batch-header">
          <div className="batch-title-group">
            <BarChart3 className="text-primary" size={20} />
            <h2 className="batch-title">Batch Recovery Impact / Money Recovered</h2>
          </div>
        </div>
        <div className="empty-state" style={{ padding: '24px 0' }}>
          <div className="spinner" />
          <span>Loading canonical batch report...</span>
        </div>
      </section>
    );
  }

  if (error && !report) {
    return (
      <section className="batch-impact-card">
        <div className="batch-header">
          <div className="batch-title-group">
            <BarChart3 className="text-primary" size={20} />
            <h2 className="batch-title">Batch Recovery Impact / Money Recovered</h2>
          </div>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => fetchReport(false)}
          >
            <RefreshCw size={14} />
            <span>Retry</span>
          </button>
        </div>
        <div className="error-banner" style={{ margin: '16px 0' }}>
          {error}
        </div>
      </section>
    );
  }

  if (!report) return null;

  const intel = report.intelligent_strategy;
  const naive = report.naive_baseline;
  const bounce = report.bounce_fee;
  const decisions = report.decision_breakdown || {};

  return (
    <section className="batch-impact-card">
      <div className="batch-header">
        <div className="batch-title-group">
          <div className="batch-icon-badge">
            <TrendingUp size={18} />
          </div>
          <div>
            <div className="batch-title-row">
              <h2 className="batch-title">Batch Recovery Impact / Money Recovered</h2>
              <span className="batch-badge">
                {report.total_failed_attempts} Failed Attempts Evaluated
              </span>
            </div>
            <p className="batch-subtitle">
              Evaluating all canonical failed attempts (Total Portfolio: ₹{Number(report.total_amount).toLocaleString('en-IN')})
            </p>
          </div>
        </div>

        <div className="batch-header-actions">
          <button
            type="button"
            className="refresh-report-btn"
            onClick={() => fetchReport(true)}
            disabled={refreshing}
            title="Recompute batch simulation against canonical dataset"
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            <span>{refreshing ? 'Recomputing...' : 'Recompute'}</span>
          </button>

          <button
            type="button"
            className="toggle-expand-btn"
            onClick={() => setIsExpanded(prev => !prev)}
            aria-label={isExpanded ? 'Collapse batch impact' : 'Expand batch impact'}
          >
            {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
      </div>

      {isExpanded && (
        <div className="batch-body">
          {/* Main Comparison Grid */}
          <div className="batch-grid">
            {/* 1. Intelligent Recovery Strategy */}
            <div className="strategy-card intelligent">
              <div className="strategy-badge intelligent">
                <CheckCircle2 size={13} />
                <span>Intelligent Recovery</span>
              </div>
              <div className="metric-headline">
                <span className="currency-sign">₹</span>
                <span className="amount-val">{Number(intel.amount_recovered).toLocaleString('en-IN')}</span>
              </div>
              <div className="metric-row">
                <span className="metric-label">Recovery Rate:</span>
                <span className="metric-val highlight-green">{(intel.recovery_rate * 100).toFixed(1)}%</span>
              </div>
              <div className="metric-subtext">
                {intel.recovered_count} successful recoveries from {intel.retries_attempted} scheduled retries
              </div>
            </div>

            {/* 2. Naive +2-Day Baseline */}
            <div className="strategy-card naive">
              <div className="strategy-badge naive">
                <RotateCcw size={13} />
                <span>Naive +2-Day Baseline</span>
              </div>
              <div className="metric-headline">
                <span className="currency-sign">₹</span>
                <span className="amount-val">{Number(naive.amount_recovered).toLocaleString('en-IN')}</span>
              </div>
              <div className="metric-row">
                <span className="metric-label">Recovery Rate:</span>
                <span className="metric-val highlight-blue">{(naive.recovery_rate * 100).toFixed(1)}%</span>
              </div>
              <div className="metric-subtext">
                {naive.recovered_count} recovered from {naive.retries_attempted} blind, un-targeted retries
              </div>
            </div>

            {/* 3. Incremental Recovery & Impact */}
            <div className="strategy-card impact">
              <div className="strategy-badge impact">
                <IndianRupee size={13} />
                <span>Recovery Impact</span>
              </div>
              <div className="metric-headline">
                <span className="currency-sign">₹</span>
                <span className="amount-val">
                  {Number(report.incremental_recovery).toLocaleString('en-IN')}
                </span>
              </div>
              <div className="metric-row">
                <span className="metric-label">Incremental Recovery:</span>
                <span className={`metric-val ${report.incremental_recovery >= 0 ? 'highlight-green' : 'text-dim'}`}>
                  ₹{Number(report.incremental_recovery).toLocaleString('en-IN')}
                </span>
              </div>
              <div className="metric-subtext">
                Difference in recovered capital between intelligent and naive retry
              </div>
            </div>

            {/* 4. Customer Protection & Bounce-Fee Savings */}
            <div className="strategy-card protection">
              <div className="strategy-badge protection">
                <ShieldCheck size={13} />
                <span>Customer Fee Protection</span>
              </div>
              <div className="metric-headline">
                <span className="currency-sign">₹</span>
                <span className="amount-val">{Number(bounce.savings_from_retries_avoided).toLocaleString('en-IN')}</span>
              </div>
              <div className="metric-row">
                <span className="metric-label">Retries Avoided:</span>
                <span className="metric-val highlight-green">{report.retries_avoided} blind retries</span>
              </div>
              <div className="metric-row">
                <span className="metric-label">DO_NOT_RETRY Count:</span>
                <span className="metric-val">{report.do_not_retry_count} attempts</span>
              </div>
              <div className="fee-assumption-note">
                <HelpCircle size={12} />
                <span>Assumption: {bounce.fee_assumption}</span>
              </div>
            </div>
          </div>

          {/* Decision Engine Breakdown Bar */}
          <div className="batch-decisions-bar">
            <div className="decisions-title">Policy Engine Routing across {report.total_failed_attempts} Attempts:</div>
            <div className="decisions-tags">
              <span className="decision-tag reschedule">
                RESCHEDULE: <strong>{decisions.RESCHEDULE || 0}</strong>
              </span>
              <span className="decision-tag do-not-retry">
                DO_NOT_RETRY: <strong>{decisions.DO_NOT_RETRY || 0}</strong>
              </span>
              <span className="decision-tag retry-now">
                RETRY_NOW: <strong>{decisions.RETRY_NOW || 0}</strong>
              </span>
              <span className="decision-tag reauthorize">
                REAUTHORIZE: <strong>{decisions.REAUTHORIZE_MANDATE || 0}</strong>
              </span>
              <span className="decision-tag wait">
                WAIT: <strong>{decisions.WAIT_FOR_BETTER_WINDOW || 0}</strong>
              </span>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
