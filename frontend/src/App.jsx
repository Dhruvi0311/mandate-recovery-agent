import React, { useState, useEffect, useCallback, useRef } from 'react';
import { api } from './services/api';
import Header from './components/Header';
import ProcessStepper from './components/ProcessStepper';
import MandateList from './components/MandateList';
import RecoveryAnalysis from './components/RecoveryAnalysis';
import AgentChat from './components/AgentChat';
import ExecutionPanel from './components/ExecutionPanel';
import BatchImpactPanel from './components/BatchImpactPanel';
import SafetyAuditPanel from './components/SafetyAuditPanel';
import BatchImpactScreen from './components/BatchImpactScreen';
import AttemptDetailScreen from './components/AttemptDetailScreen';
import LiveAgentTraceScreen from './components/LiveAgentTraceScreen';

const cleanConsecutiveMessages = (msgs) => {
  if (!Array.isArray(msgs)) return [];
  return msgs.filter((msg, idx, arr) => idx === 0 || msg !== arr[idx - 1]);
};

export default function App() {
  const [currentScreen, setCurrentScreen] = useState('batch-impact');
  const [mandates, setMandates] = useState([]);
  const [loadingMandates, setLoadingMandates] = useState(true);
  const [mandatesError, setMandatesError] = useState(null);

  const [selectedAttemptId, setSelectedAttemptId] = useState('ATMPT00005');
  const [analysis, setAnalysis] = useState(null);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);

  const [recoveryStatus, setRecoveryStatus] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [consentGranted, setConsentGranted] = useState(false);
  const [actionStatus, setActionStatus] = useState('PENDING');

  const [executing, setExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState(null);

  const activeAttemptRef = useRef(selectedAttemptId);
  activeAttemptRef.current = selectedAttemptId;

  // Load initial mandates
  const loadMandates = useCallback(async (selectId = null) => {
    setLoadingMandates(true);
    setMandatesError(null);
    try {
      const data = await api.getMandates();
      setMandates(data);
      if (data.length > 0) {
        if (selectId) {
          setSelectedAttemptId(selectId);
        } else if (!activeAttemptRef.current) {
          setSelectedAttemptId(data[0].attempt_id);
        }
      }
    } catch (err) {
      setMandatesError(err.message);
    } finally {
      setLoadingMandates(false);
    }
  }, []);

  useEffect(() => {
    loadMandates();
  }, [loadMandates]);

  const loadAttemptData = useCallback(async (attemptId) => {
    if (!attemptId) return;
    activeAttemptRef.current = attemptId;
    setLoadingAnalysis(true);
    setAnalysis(null);
    setRecoveryStatus(null);
    setAnalysisError(null);
    setExecutionResult(null);
    setChatMessages([]);
    setConsentGranted(false);
    setActionStatus('PENDING');

    try {
      // 1. Run recovery analysis
      const analysisData = await api.analyzeRecovery(attemptId);
      if (activeAttemptRef.current !== attemptId) return;
      setAnalysis(analysisData);

      // 2. Fetch current recovery status
      const statusData = await api.getRecoveryStatus(attemptId);
      if (activeAttemptRef.current !== attemptId) return;
      setRecoveryStatus(statusData);

      // 3. Retrieve or initialize agent chat turn with idempotent GET
      try {
        const chatInit = await api.getAgentConversation(attemptId);
        if (activeAttemptRef.current !== attemptId) return;
        setChatMessages(cleanConsecutiveMessages(chatInit.messages));
        setConsentGranted(chatInit.consent_granted || false);
        setActionStatus(chatInit.action_status || 'PENDING');
      } catch (chatErr) {
        console.warn('Initial chat error:', chatErr);
      }
    } catch (err) {
      if (activeAttemptRef.current === attemptId) {
        setAnalysisError(err.message);
      }
    } finally {
      if (activeAttemptRef.current === attemptId) {
        setLoadingAnalysis(false);
      }
    }
  }, []);

  const selectAttempt = useCallback((attemptId) => {
    activeAttemptRef.current = attemptId;
    setSelectedAttemptId(attemptId);
    // Immediately invalidate and clear attempt-specific state on switch to prevent stale data flash
    setAnalysis(null);
    setRecoveryStatus(null);
    setExecutionResult(null);
    setChatMessages([]);
    setConsentGranted(false);
    setActionStatus('PENDING');
    setLoadingAnalysis(true);
    setAnalysisError(null);
  }, []);

  useEffect(() => {
    if (selectedAttemptId) {
      loadAttemptData(selectedAttemptId);
    }
  }, [selectedAttemptId, loadAttemptData]);

  // Handle customer message send
  const handleSendMessage = async (text) => {
    if (!selectedAttemptId) return;
    try {
      const res = await api.sendAgentMessage(selectedAttemptId, text);
      if (activeAttemptRef.current !== selectedAttemptId) return;
      setChatMessages(cleanConsecutiveMessages(res.messages));
      setConsentGranted(res.consent_granted || false);
      setActionStatus(res.action_status || 'PENDING');

      // Refresh lifecycle status
      const updatedStatus = await api.getRecoveryStatus(selectedAttemptId);
      if (activeAttemptRef.current !== selectedAttemptId) return;
      setRecoveryStatus(updatedStatus);

      // Update mandate list status pill
      setMandates(prev => prev.map(m => (
        m.attempt_id === selectedAttemptId
          ? { ...m, recovery_state: updatedStatus.status }
          : m
      )));
    } catch (err) {
      alert(`Agent conversation error: ${err.message}`);
    }
  };

  // Handle retry execution
  const handleExecuteRetry = async () => {
    if (!selectedAttemptId) return;
    setExecuting(true);
    try {
      const res = await api.executeRecovery(selectedAttemptId);
      setExecutionResult(res);

      // Refresh status
      const updatedStatus = await api.getRecoveryStatus(selectedAttemptId);
      setRecoveryStatus(updatedStatus);

      // Update mandate list status
      setMandates(prev => prev.map(m => (
        m.attempt_id === selectedAttemptId
          ? { ...m, recovery_state: updatedStatus.status }
          : m
      )));
    } catch (err) {
      alert(`Execution error: ${err.message}`);
    } finally {
      setExecuting(false);
    }
  };

  const handleSelectScenario = (attemptId) => {
    selectAttempt(attemptId);
    setCurrentScreen('attempt-detail');
  };

  return (
    <div className="app-container">
      <Header
        currentScreen={currentScreen}
        onSelectScreen={setCurrentScreen}
        onSelectScenario={handleSelectScenario}
        activeAttemptId={selectedAttemptId}
      />

      {currentScreen === 'batch-impact' && (
        <BatchImpactScreen onNavigateToAttempt={handleSelectScenario} />
      )}

      {currentScreen === 'attempt-detail' && (
        <AttemptDetailScreen
          attemptId={selectedAttemptId}
          onSelectAttempt={selectAttempt}
          mandates={mandates}
          analysis={analysis}
          loadingAnalysis={loadingAnalysis}
          analysisError={analysisError}
          recoveryStatus={recoveryStatus}
          executionResult={executionResult}
          executing={executing}
          onExecuteRetry={handleExecuteRetry}
          onNavigateToScreen={setCurrentScreen}
        />
      )}

      {currentScreen === 'agent-trace' && (
        <LiveAgentTraceScreen
          attemptId={selectedAttemptId}
          onSelectAttempt={selectAttempt}
          mandates={mandates}
          analysis={analysis}
          recoveryStatus={recoveryStatus}
          executionResult={executionResult}
          chatMessages={chatMessages}
          consentGranted={consentGranted}
          actionStatus={actionStatus}
          loadingAnalysis={loadingAnalysis}
          executing={executing}
          onSendMessage={handleSendMessage}
          onExecuteRetry={handleExecuteRetry}
          onNavigateToScreen={setCurrentScreen}
        />
      )}
    </div>
  );
}
