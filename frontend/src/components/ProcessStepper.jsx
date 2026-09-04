import React from 'react';

const STEPS = [
  { id: 1, label: 'Failure', desc: 'Mandate attempt failed' },
  { id: 2, label: 'Prediction', desc: 'Point-in-time scoring' },
  { id: 3, label: 'Decision', desc: 'Policy engine evaluation' },
  { id: 4, label: 'Consent', desc: 'Two-tier verification' },
  { id: 5, label: 'Execution', desc: 'Scheduled retry' },
  { id: 6, label: 'Outcome', desc: 'Simulation & settlement' }
];

export default function ProcessStepper({ analysis, recoveryState, outcome }) {
  // Determine current stage
  // Stage 1: Attempt loaded
  // Stage 2 & 3: Analysis performed (decision exists)
  // Stage 4: Consent obtained / SCHEDULED
  // Stage 5 & 6: Executed / Outcome
  let currentStage = 1;
  if (analysis) {
    currentStage = 3;
  }
  if (recoveryState === 'SCHEDULED') {
    currentStage = 4;
  }
  if (recoveryState === 'EXECUTED' || outcome) {
    currentStage = 6;
  }

  return (
    <div className="stepper-container">
      {STEPS.map((step, idx) => {
        const isCompleted = step.id < currentStage;
        const isActive = step.id === currentStage;
        return (
          <React.Fragment key={step.id}>
            <div className={`step-item ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}`}>
              <div className="step-number">{isCompleted ? '✓' : step.id}</div>
              <div>
                <div>{step.label}</div>
              </div>
            </div>
            {idx < STEPS.length - 1 && (
              <div className={`step-divider ${isCompleted ? 'active' : ''}`} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
