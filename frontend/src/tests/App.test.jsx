import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from '../App';
import BatchImpactScreen from '../components/BatchImpactScreen';
import { api } from '../services/api';

// Mock API service
vi.mock('../services/api', () => ({
  api: {
    getHealth: vi.fn(),
    getMandates: vi.fn(),
    getMandateDetail: vi.fn(),
    analyzeRecovery: vi.fn(),
    sendAgentMessage: vi.fn(),
    getRecoveryStatus: vi.fn(),
    executeRecovery: vi.fn(),
    getBatchReport: vi.fn(),
    getAuditLog: vi.fn(),
    getAttemptAuditRecord: vi.fn(),
    simulateRogueAgent: vi.fn(),
    getAgentConversation: vi.fn(),
  }
}));

const MOCK_MANDATES = [
  {
    attempt_id: 'ATMPT00005',
    customer_id: 'CUST0001',
    mandate_id: 'MNDT00001',
    amount: 1500,
    attempt_date: '2026-06-05',
    failure_reason: 'INSUFFICIENT_FUNDS',
    recovery_state: 'PENDING'
  },
  {
    attempt_id: 'ATMPT00006',
    customer_id: 'CUST0002',
    mandate_id: 'MNDT00002',
    amount: 500,
    attempt_date: '2026-06-06',
    failure_reason: 'INSUFFICIENT_FUNDS',
    recovery_state: 'PENDING'
  }
];

const MOCK_ANALYSIS = {
  attempt_id: 'ATMPT00005',
  customer_id: 'CUST0001',
  mandate_id: 'MNDT00001',
  amount: 1500,
  failure_reason: 'INSUFFICIENT_FUNDS',
  recovery_probability: 0.88,
  candidate_retry_windows: [
    { date: '2026-07-21', success_probability: 0.88 }
  ],
  recommended_retry_date: '2026-07-21',
  decision: 'RESCHEDULE',
  reason_codes: ['HIGH_RECOVERY_PROBABILITY'],
  requires_customer_consent: true
};

const MOCK_MANDATE_DETAIL = {
  attempt_id: 'ATMPT00005',
  customer_id: 'CUST0001',
  mandate_id: 'MNDT00001',
  merchant_name: 'Health Insurance',
  amount: 1500.0,
  attempt_date: '2026-07-01',
  attempt_number: 1,
  balance_at_attempt: 193.0,
  failure_reason: 'INSUFFICIENT_FUNDS',
  recovery_state: 'SCHEDULED',
  decision: 'RESCHEDULE',
  recommended_retry_date: '2026-07-21',
  recovery_probability: 0.88
};

const MOCK_STATUS_PENDING = {
  attempt_id: 'ATMPT00005',
  status: 'PENDING'
};

const MOCK_STATUS_SCHEDULED = {
  attempt_id: 'ATMPT00005',
  status: 'SCHEDULED',
  scheduled_date: '2026-07-21'
};

const MOCK_EXECUTION_SUCCESS = {
  attempt_id: 'ATMPT00005',
  scheduled_date: '2026-07-21',
  result: 'SUCCESS',
  recovered_amount: 1500.0,
  executed_at: '2026-09-03T18:00:00Z',
  details: 'Payment simulation executed successfully on 2026-07-21.'
};

const MOCK_BATCH_REPORT = {
  total_failed_attempts: 363,
  total_amount: 1652361.0,
  intelligent_strategy: {
    amount_recovered: 441945.0,
    recovery_rate: 0.2507,
    recovered_count: 91,
    retries_attempted: 140
  },
  naive_baseline: {
    amount_recovered: 415091.0,
    recovery_rate: 0.2479,
    recovered_count: 90,
    retries_attempted: 363
  },
  incremental_recovery: 26854.0,
  retries_avoided: 223,
  do_not_retry_count: 193,
  bounce_fee: {
    fee_per_retry: 500.0,
    fee_assumption: '₹500 bank bounce charge per failed attempt as specified in PRD.md',
    savings_from_retries_avoided: 111500.0,
    savings_from_do_not_retry: 96500.0
  },
  decision_breakdown: {
    RESCHEDULE: 99,
    DO_NOT_RETRY: 193,
    RETRY_NOW: 41,
    REAUTHORIZE_MANDATE: 25,
    WAIT_FOR_BETTER_WINDOW: 5
  },
  generated_at: '2026-09-04T02:35:35.183084'
};

const MOCK_AUDIT_LOG = {
  total_records: 2,
  blocked_violations_count: 3,
  records: [
    {
      attempt_id: 'ATMPT00005',
      customer_id: 'CUST0001',
      mandate_id: 'MNDT00001',
      timestamp: '2026-09-03T18:00:00Z',
      decision: 'RESCHEDULE',
      reason_codes: ['HIGH_RECOVERY_PROBABILITY'],
      recovery_probability: 0.88,
      recommended_retry_date: '2026-07-21',
      consent_required: true,
      consent_status: 'GRANTED',
      customer_response: 'ACCEPTED',
      requested_action: "schedule_retry(agreed_date='2026-07-21')",
      tool_validation_result: 'VALID',
      execution_outcome: 'SUCCESS',
      final_status: 'COMPLETED'
    }
  ]
};

describe('Mandate Recovery Fintech Platform Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getHealth.mockResolvedValue({ status: 'healthy' });
    api.getMandates.mockResolvedValue(MOCK_MANDATES);
    api.getMandateDetail.mockImplementation((id) => Promise.resolve({ ...MOCK_MANDATE_DETAIL, attempt_id: id || 'ATMPT00005' }));
    api.getBatchReport.mockResolvedValue(MOCK_BATCH_REPORT);
    api.getAuditLog.mockResolvedValue(MOCK_AUDIT_LOG);
    api.getAttemptAuditRecord.mockResolvedValue(MOCK_AUDIT_LOG.records[0]);
    api.analyzeRecovery.mockResolvedValue(MOCK_ANALYSIS);
    api.getRecoveryStatus.mockResolvedValue(MOCK_STATUS_PENDING);
    api.getAgentConversation.mockResolvedValue({
      attempt_id: 'ATMPT00005',
      response: 'Hello! Would you like to schedule retry for 2026-07-21?',
      action_status: 'PENDING',
      recovery_state: 'PENDING',
      consent_granted: false,
      messages: ['Agent: Hello! Would you like to schedule retry for 2026-07-21?']
    });
    api.sendAgentMessage.mockResolvedValue({
      attempt_id: 'ATMPT00005',
      response: 'Hello! Would you like to schedule retry for 2026-07-21?',
      action_status: 'PENDING',
      recovery_state: 'PENDING',
      consent_granted: false,
      messages: ['Agent: Hello! Would you like to schedule retry for 2026-07-21?']
    });
    api.simulateRogueAgent.mockResolvedValue({
      attempt_id: 'ATMPT00005',
      agent_type: 'ROGUE_AGENT',
      attempted_action: "schedule_retry(agreed_date='2099-01-01')",
      validation_result: 'BLOCKED',
      violation_type: 'HALLUCINATED_DATE',
      rejection_reason: 'Cannot schedule retry: Agreed date 2099-01-01 does not match authorized date 2026-07-21.',
      blocked_violations_count: 4,
      recovery_state: 'PENDING',
      audit_recorded: true
    });
  });

  it('renders fintech shell header with navigation tabs, environment status, and health', async () => {
    render(<App />);
    expect(screen.getByText('MANDATE RECOVERY')).toBeInTheDocument();
    expect(screen.getByText('Batch Impact')).toBeInTheDocument();
    expect(screen.getByText('Attempt Detail')).toBeInTheDocument();
    expect(screen.getByText('Live Agent Trace')).toBeInTheDocument();
    expect(screen.getByText('PROTOTYPE')).toBeInTheDocument();
    expect(screen.getByText('SIMULATED PAYMENT RAIL')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText('FastAPI Connected')).toBeInTheDocument();
    });
  });

  it('defaults to Batch Impact screen on initial load', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'BATCH IMPACT' })).toBeInTheDocument();
      expect(screen.getByText(/Recovery evaluation across 363 failed mandate attempts/i)).toBeInTheDocument();
    });
  });

  it('renders all canonical batch-report metrics and primary count-up KPI accurately', async () => {
    render(<App />);

    await waitFor(() => {
      expect(api.getBatchReport).toHaveBeenCalled();
      // Primary KPI
      expect(screen.getByText('Recovered by intelligent recovery')).toBeInTheDocument();
      expect(screen.getAllByText('₹4,41,945').length).toBeGreaterThanOrEqual(1);

      // Secondary metrics
      expect(screen.getByText('Total amount at risk')).toBeInTheDocument();
      expect(screen.getByText('₹16,52,361')).toBeInTheDocument();

      expect(screen.getByText('Intelligent retries')).toBeInTheDocument();
      expect(screen.getAllByText('140').length).toBeGreaterThanOrEqual(1);

      expect(screen.getAllByText(/Retries avoided/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('223').length).toBeGreaterThanOrEqual(1);

      expect(screen.getAllByText(/Implied bounce-fee savings/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('₹1,11,500').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('renders recovery comparison chart, naive baseline, and incremental recovery', async () => {
    render(<App />);

    await waitFor(() => {
      // Main Chart
      expect(screen.getByRole('heading', { name: 'RECOVERY AMOUNT' })).toBeInTheDocument();
      expect(screen.getAllByText('Intelligent Recovery')[0]).toBeInTheDocument();
      expect(screen.getAllByText('Naive +2-Day Baseline')[0]).toBeInTheDocument();
      expect(screen.getByText('₹4,15,091')).toBeInTheDocument();

      // Incremental recovery
      expect(screen.getByText('Incremental recovery')).toBeInTheDocument();
      expect(screen.getByText(/26,854/)).toBeInTheDocument();

      // Retry Volume & Efficiency
      expect(screen.getByRole('heading', { name: 'RETRY VOLUME' })).toBeInTheDocument();
      expect(screen.getByText('RETRIES AVOIDED')).toBeInTheDocument();
      expect(screen.getByText('Fewer unnecessary retry attempts under the intelligent policy.')).toBeInTheDocument();
      expect(screen.getByText(/Based on the ₹500 bounce-charge assumption documented in the PRD/i)).toBeInTheDocument();
    });
  });

  it('renders decision distribution table and confirms evaluation note is removed', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'DECISION DISTRIBUTION' })).toBeInTheDocument();
      expect(screen.getByText('DO_NOT_RETRY')).toBeInTheDocument();
      expect(screen.getByText('193')).toBeInTheDocument();
      expect(screen.getByText('53.2%')).toBeInTheDocument();

      expect(screen.getByText('RESCHEDULE')).toBeInTheDocument();
      expect(screen.getByText('99')).toBeInTheDocument();
      expect(screen.getByText('27.3%')).toBeInTheDocument();

      expect(screen.getByText('RETRY_NOW')).toBeInTheDocument();
      expect(screen.getByText('41')).toBeInTheDocument();
      expect(screen.getByText('11.3%')).toBeInTheDocument();

      expect(screen.getByText('REAUTHORIZE_MANDATE')).toBeInTheDocument();
      expect(screen.getByText('25')).toBeInTheDocument();
      expect(screen.getByText('6.9%')).toBeInTheDocument();

      expect(screen.getByText('WAIT_FOR_BETTER_WINDOW')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
      expect(screen.getByText('1.4%')).toBeInTheDocument();

      // Evaluation note must be completely removed
      expect(screen.queryByText('Evaluation note')).not.toBeInTheDocument();
      expect(screen.queryByText(/The intelligent policy avoided 223 retry attempts, but recovered less gross payment value/i)).not.toBeInTheDocument();
    });
  });

  it('renders professional loading and error states for BatchImpactScreen', async () => {
    // 1. Loading state
    api.getBatchReport.mockReturnValue(new Promise(() => {})); // Never resolves
    const { unmount } = render(<BatchImpactScreen />);
    expect(screen.getByText('Loading batch evaluation across 363 mandate attempts...')).toBeInTheDocument();
    unmount();

    // 2. Error state
    api.getBatchReport.mockRejectedValue(new Error('Network error: gateway timeout'));
    render(<BatchImpactScreen />);
    await waitFor(() => {
      expect(screen.getByText('Unable to load batch evaluation')).toBeInTheDocument();
      expect(screen.getByText('Network error: gateway timeout')).toBeInTheDocument();
      expect(screen.getByText('Retry Evaluation')).toBeInTheDocument();
    });
  });

  it('allows navigation between Batch Impact, Attempt Detail, and Live Agent Trace', async () => {
    render(<App />);

    // Initial screen is Batch Impact
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'BATCH IMPACT' })).toBeInTheDocument();
    });

    // Switch to Attempt Detail
    fireEvent.click(screen.getByText('Attempt Detail'));
    await waitFor(() => {
      expect(screen.getAllByText('ATMPT00005')[0]).toBeInTheDocument();
      expect(screen.getAllByText('RESCHEDULE')[0]).toBeInTheDocument();
    });

    // Switch to Live Agent Trace
    fireEvent.click(screen.getByText('Live Agent Trace'));
    await waitFor(() => {
      expect(screen.getByText('Simulate Rogue Agent')).toBeInTheDocument();
    });

    // Switch back to Batch Impact
    fireEvent.click(screen.getByText('Batch Impact'));
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'BATCH IMPACT' })).toBeInTheDocument();
    });
  });

  it('renders Attempt Detail screen correctly with financial summary, failure analysis, and back navigation', async () => {
    render(<App />);

    // Navigate to Attempt Detail
    fireEvent.click(screen.getByText('Attempt Detail'));

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'ATTEMPT DETAIL' })).toBeInTheDocument();
      expect(screen.getByText('AMOUNT AT RISK')).toBeInTheDocument();
      expect(screen.getByText('FAILURE ANALYSIS')).toBeInTheDocument();
      expect(screen.getByText('Amount shortfall')).toBeInTheDocument();
      expect(screen.getByText('Back to Batch Impact')).toBeInTheDocument();
    });

    // Test back navigation
    fireEvent.click(screen.getByText('Back to Batch Impact'));
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'BATCH IMPACT' })).toBeInTheDocument();
    });
  });

  it('Scenario A displays canonical recovery decision, single recommended date, and candidate retry table', async () => {
    render(<App />);

    // Click Scenario A in header
    fireEvent.click(screen.getByText('Scenario A'));

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'ATTEMPT DETAIL' })).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'RECOVERY DECISION' })).toBeInTheDocument();
      expect(screen.getAllByText(/88%/)[0]).toBeInTheDocument();
      expect(screen.getAllByText('RESCHEDULE')[0]).toBeInTheDocument();

      // Single canonical recommended retry block
      expect(screen.getByText('RECOMMENDED RETRY')).toBeInTheDocument();
      expect(screen.getAllByText(/21 Jul 2026/i)[0]).toBeInTheDocument();

      // Retry Window Analysis table
      expect(screen.getByRole('heading', { name: 'RETRY WINDOW ANALYSIS' })).toBeInTheDocument();
      expect(screen.getByText('SELECTED')).toBeInTheDocument();

      // Policy decision explanation
      expect(screen.getByRole('heading', { name: 'POLICY DECISION' })).toBeInTheDocument();
      expect(screen.getByText('Decision Engine is authoritative; the agent only orchestrates the recovery conversation.')).toBeInTheDocument();
    });
  });

  it('Scenario B displays DO_NOT_RETRY, fallback recommendation, and no invented retry date', async () => {
    api.analyzeRecovery.mockImplementation((attemptId) => {
      if (attemptId === 'ATMPT00006') {
        return Promise.resolve({
          attempt_id: 'ATMPT00006',
          customer_id: 'CUST0002',
          mandate_id: 'MNDT00002',
          amount: 500,
          failure_reason: 'INSUFFICIENT_FUNDS',
          recovery_probability: 0.15,
          candidate_retry_windows: [],
          recommended_retry_date: null,
          decision: 'DO_NOT_RETRY',
          reason_codes: ['LOW_RECOVERY_PROBABILITY'],
          requires_customer_consent: false
        });
      }
      return Promise.resolve(MOCK_ANALYSIS);
    });

    api.getMandateDetail.mockImplementation((attemptId) => {
      if (attemptId === 'ATMPT00006') {
        return Promise.resolve({
          attempt_id: 'ATMPT00006',
          customer_id: 'CUST0002',
          mandate_id: 'MNDT00002',
          merchant_name: 'Health Insurance',
          amount: 500.0,
          attempt_date: '2026-07-03',
          attempt_number: 2,
          balance_at_attempt: 193.0,
          failure_reason: 'INSUFFICIENT_FUNDS',
          recovery_state: 'PENDING',
          decision: 'DO_NOT_RETRY',
          recommended_retry_date: null,
          recovery_probability: 0.15
        });
      }
      return Promise.resolve(MOCK_MANDATE_DETAIL);
    });

    render(<App />);

    // Click Scenario B in header
    fireEvent.click(screen.getByText('Scenario B'));

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'ATTEMPT DETAIL' })).toBeInTheDocument();
      expect(screen.getByText('15%')).toBeInTheDocument();
      expect(screen.getAllByText('DO_NOT_RETRY')[0]).toBeInTheDocument();

      // Fallback recommendation shown instead of recommended retry date
      expect(screen.getByText('FALLBACK RECOMMENDATION')).toBeInTheDocument();
      expect(screen.getByText('ALTERNATIVE PAYMENT LINK')).toBeInTheDocument();
      expect(screen.queryByText('RECOMMENDED RETRY')).not.toBeInTheDocument();

      // Empty retry window note
      expect(screen.getByText(/No viable retry windows predicted above threshold/i)).toBeInTheDocument();
    });
  });

  it('renders consent and execution state and audit preview accurately', async () => {
    render(<App />);

    fireEvent.click(screen.getByText('Attempt Detail'));

    await waitFor(() => {
      expect(screen.getByText('CONSENT & EXECUTION')).toBeInTheDocument();
      expect(screen.getByText('CUSTOMER CONSENT')).toBeInTheDocument();
      expect(screen.getByText('TOOL VALIDATION')).toBeInTheDocument();
      expect(screen.getAllByText('ACCEPTED')[0]).toBeInTheDocument();

      // Audit trail preview
      expect(screen.getByText('AUDIT TRAIL')).toBeInTheDocument();
      expect(screen.getByText('VIEW FULL AUDIT TRAIL')).toBeInTheDocument();
    });
  });

  it('handles customer consent in Live Agent Trace and updates status to scheduled', async () => {
    api.getAgentConversation.mockResolvedValueOnce({
      attempt_id: 'ATMPT00005',
      response: 'Initial greeting',
      messages: ['Agent: Hello!']
    });
    api.sendAgentMessage.mockResolvedValueOnce({
      attempt_id: 'ATMPT00005',
      response: 'Successfully scheduled retry for ATMPT00005 on 2026-07-21.',
      action_status: 'COMPLETED',
      recovery_state: 'SCHEDULED',
      consent_granted: true,
      messages: [
        'Agent: Hello!',
        'Customer: Yes, please schedule it',
        'Tool schedule_retry success: Successfully scheduled retry for ATMPT00005 on 2026-07-21.'
      ]
    });

    api.getRecoveryStatus.mockResolvedValue(MOCK_STATUS_SCHEDULED);

    render(<App />);

    // Switch to Live Agent Trace
    fireEvent.click(screen.getByText('Live Agent Trace'));

    await waitFor(() => {
      expect(screen.getByText('✓ Yes, schedule it')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('✓ Yes, schedule it'));

    await waitFor(() => {
      expect(api.sendAgentMessage).toHaveBeenCalledWith('ATMPT00005', 'Yes, please schedule it');
    });
  });

  it('executes scheduled retry and displays simulation outcome', async () => {
    api.getRecoveryStatus.mockResolvedValue(MOCK_STATUS_SCHEDULED);
    api.executeRecovery.mockResolvedValue(MOCK_EXECUTION_SUCCESS);

    render(<App />);

    // Switch to Attempt Detail
    fireEvent.click(screen.getByText('Attempt Detail'));

    await waitFor(() => {
      const execBtn = screen.getByText('Execute Scheduled Retry');
      expect(execBtn).toBeInTheDocument();
      expect(execBtn).not.toBeDisabled();
      fireEvent.click(execBtn);
    });

    await waitFor(() => {
      expect(api.executeRecovery).toHaveBeenCalledWith('ATMPT00005');
      expect(screen.getByText('SUCCESS')).toBeInTheDocument();
    });
  });

  it('invokes backend rogue agent simulation and displays real-time tool boundary blocking', async () => {
    render(<App />);

    // Switch to Live Agent Trace
    fireEvent.click(screen.getByText('Live Agent Trace'));

    await waitFor(() => {
      expect(screen.getByText('Simulate Rogue Agent')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Simulate Rogue Agent'));

    await waitFor(() => {
      expect(api.simulateRogueAgent).toHaveBeenCalledWith('ATMPT00005');
      expect(screen.getByText('BLOCKED BY TOOL BOUNDARY')).toBeInTheDocument();
      expect(screen.getByText('HALLUCINATED_DATE')).toBeInTheDocument();
      expect(screen.getByText(/Cannot schedule retry: Agreed date 2099-01-01 does not match authorized date/i)).toBeInTheDocument();
      expect(screen.getByText('✓ Violation recorded')).toBeInTheDocument();
      expect(screen.getAllByText('NOT EXECUTED')[0]).toBeInTheDocument();
      expect(screen.getByText(/STATE UNCHANGED/i)).toBeInTheDocument();
      // Blocked counter updated
      expect(screen.getAllByText('4').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('renders Live Agent Trace two-column layout with System Trace flow stages', async () => {
    render(<App />);

    // Switch to Live Agent Trace
    fireEvent.click(screen.getByText('Live Agent Trace'));

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'LIVE AGENT TRACE' })).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'CUSTOMER CONVERSATION' })).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'SYSTEM TRACE' })).toBeInTheDocument();
      expect(screen.getByText('LLM PROPOSAL → DETERMINISTIC POLICY → TOOL VALIDATION → EXECUTION')).toBeInTheDocument();
      expect(screen.getByText('AUTHORITATIVE POLICY')).toBeInTheDocument();
      expect(screen.getByText('LLM-PROPOSED ACTION')).toBeInTheDocument();
      expect(screen.getByText('✓ VERIFIED')).toBeInTheDocument();
      expect(screen.getByText('ADVERSARIAL SAFETY TEST')).toBeInTheDocument();
      expect(screen.getByText('VIEW FULL AUDIT TRAIL')).toBeInTheDocument();
    });
  });

  it('renders exactly one initial opening agent message without duplicate greeting on fresh load', async () => {
    api.getAgentConversation.mockResolvedValueOnce({
      attempt_id: 'ATMPT00005',
      response: 'Hello! Your mandate payment failed due to insufficient funds. Our recovery model predicts optimal funds on 2026-07-21. Would you like us to schedule a retry for 2026-07-21?',
      action_status: 'PENDING',
      recovery_state: 'PENDING',
      consent_granted: false,
      messages: ['Agent: Hello! Your mandate payment failed due to insufficient funds. Our recovery model predicts optimal funds on 2026-07-21. Would you like us to schedule a retry for 2026-07-21?']
    });

    render(<App />);

    // Switch to Live Agent Trace
    fireEvent.click(screen.getByText('Live Agent Trace'));

    await waitFor(() => {
      expect(api.getAgentConversation).toHaveBeenCalledWith('ATMPT00005');
      const greetings = screen.getAllByText(/predicts optimal funds on 2026-07-21/i);
      expect(greetings).toHaveLength(1);
      // Ensure no dummy Customer "Hello" exists
      expect(screen.queryByText(/^Hello$/)).not.toBeInTheDocument();
    });
  });

  it('sanitizes consecutive duplicate messages returned by API so each message renders exactly once', async () => {
    api.getAgentConversation.mockResolvedValueOnce({
      attempt_id: 'ATMPT00005',
      response: 'Hello!',
      action_status: 'PENDING',
      recovery_state: 'PENDING',
      consent_granted: false,
      messages: [
        'Agent: Hello! Would you like to schedule retry for 2026-07-21?',
        'Agent: Hello! Would you like to schedule retry for 2026-07-21?', // consecutive duplicate
        'Customer: Yes, please schedule it',
        'Tool schedule_retry success: Successfully scheduled retry for ATMPT00005 on 2026-07-21.',
        'Tool schedule_retry success: Successfully scheduled retry for ATMPT00005 on 2026-07-21.' // consecutive duplicate
      ]
    });

    render(<App />);
    fireEvent.click(screen.getByText('Live Agent Trace'));

    await waitFor(() => {
      const agentMsgs = screen.getAllByText('Hello! Would you like to schedule retry for 2026-07-21?');
      expect(agentMsgs).toHaveLength(1);
      const toolMsgs = screen.getAllByText('Tool schedule_retry success: Successfully scheduled retry for ATMPT00005 on 2026-07-21.');
      expect(toolMsgs).toHaveLength(1);
    });
  });

  it('immediately invalidates attempt-specific data when switching attempts and does not flash old data', async () => {
    let resolveScenarioB;
    const slowScenarioBPromise = new Promise((resolve) => {
      resolveScenarioB = resolve;
    });

    api.analyzeRecovery.mockImplementation((attemptId) => {
      if (attemptId === 'ATMPT00006') {
        return slowScenarioBPromise;
      }
      return Promise.resolve(MOCK_ANALYSIS);
    });

    render(<App />);

    // Switch to Attempt Detail for Scenario A first
    fireEvent.click(screen.getByText('Attempt Detail'));
    await waitFor(() => {
      expect(screen.getAllByText('88%')[0]).toBeInTheDocument();
      expect(screen.getAllByText('RESCHEDULE')[0]).toBeInTheDocument();
    });

    // Switch to Scenario B while Scenario B analysis is still pending
    fireEvent.click(screen.getByText('Scenario B'));

    // Loading indicator must immediately appear and Scenario A values must NOT be present
    expect(screen.getByText(/Loading attempt recovery investigation for ATMPT00006/i)).toBeInTheDocument();
    expect(screen.queryByText('88%')).not.toBeInTheDocument();
    expect(screen.queryByText('RESCHEDULE')).not.toBeInTheDocument();

    // Now resolve Scenario B
    resolveScenarioB({
      attempt_id: 'ATMPT00006',
      customer_id: 'CUST0002',
      mandate_id: 'MNDT00002',
      amount: 500,
      failure_reason: 'INSUFFICIENT_FUNDS',
      recovery_probability: 0.03,
      candidate_retry_windows: [],
      recommended_retry_date: null,
      decision: 'DO_NOT_RETRY',
      reason_codes: ['LOW_RECOVERY_PROBABILITY'],
      requires_customer_consent: false
    });

    await waitFor(() => {
      expect(screen.getByText('3%')).toBeInTheDocument();
      expect(screen.getAllByText('DO_NOT_RETRY')[0]).toBeInTheDocument();
    });
  });
});
