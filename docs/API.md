# Mandate Recovery Agent API Documentation

## 1. Overview & Architecture

The FastAPI application provides a thin, non-blocking adapter and orchestration layer over the core Mandate Recovery Agent modules. It exposes RESTful HTTP endpoints for dashboard queries, automated pipeline execution, interactive conversational negotiation, and simulated payment retries.

### Architectural Stack

```
   ┌────────────────────────────────────────────────┐
   │         React Frontend (Future Layer)          │
   └───────────────────────┬────────────────────────┘
                           │ HTTP / JSON
   ┌───────────────────────▼────────────────────────┐
   │                  FastAPI API                   │
   │           (src/api/routes & schemas)           │
   └───────────────────────┬────────────────────────┘
                           │
       ┌───────────────────┼───────────────────┐
       ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│Feature Engine│    │  Prediction  │    │   Decision   │
│(src/features)│───►│ (src/pred)   │───►│(src/decision)│
└──────────────┘    └──────────────┘    └──────┬───────┘
                                               │
                                               ▼
                                      ┌────────────────┐
                                      │LangGraph Agent │
                                      │  (src/agent)   │
                                      └────────┬───────┘
                                               │
                                               ▼
                                      ┌────────────────┐
                                      │Consent & State │
                                      │ (src/consent)  │
                                      └────────┬───────┘
                                               │
                                               ▼
                                      ┌────────────────┐
                                      │   Simulator    │
                                      │(src/simulator) │
                                      └────────────────┘
```

### Data Privacy & Ground-Truth Isolation
To strictly prevent data leakage and maintain compliance with testing contracts:
- `ground_truth_recoverable`, `ground_truth_retry_date`, `actual_retry_result`, and `customer_response` are **strictly blocked** from all API responses.
- The `PaymentSimulator` reads ground truth lazily only at the instant of retry execution.

---

## 2. Server Setup & Local Execution

### Start the API Server
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Interactive Documentation
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **Health Check:** `http://localhost:8000/health`

---

## 3. Endpoints Catalog

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Service health status check |
| `GET` | `/api/mandates` | List all failed mandate attempts for dashboard display |
| `GET` | `/api/mandates/{attempt_id}` | Retrieve detailed attempt information and latest recovery state |
| `POST` | `/api/recovery/{attempt_id}/analyze` | Trigger Feature → Prediction → Decision analysis |
| `POST` | `/api/agent/{attempt_id}/message` | Send customer/operator message to LangGraph recovery agent |
| `GET` | `/api/recovery/{attempt_id}/status` | Query current recovery lifecycle state |
| `POST` | `/api/recovery/{attempt_id}/execute` | Execute scheduled retry via PaymentSimulator |

---

## 4. Endpoint Specifications

### 4.1 Health Check
**Endpoint:** `GET /health`

**Response (`200 OK`):**
```json
{
  "status": "healthy",
  "service": "mandate-recovery-agent",
  "version": "1.0.0"
}
```

---

### 4.2 Mandate Dashboard List
**Endpoint:** `GET /api/mandates`

Returns failed mandate attempts enriched with current SQLite recovery state.

**Response (`200 OK`):**
```json
[
  {
    "attempt_id": "ATMPT00005",
    "customer_id": "CUST0001",
    "mandate_id": "MNDT00001",
    "amount": 1500.0,
    "attempt_date": "2026-06-05",
    "failure_reason": "INSUFFICIENT_FUNDS",
    "recovery_state": "PENDING"
  }
]
```

---

### 4.3 Mandate Details
**Endpoint:** `GET /api/mandates/{attempt_id}`

Returns comprehensive attempt details, merchant info, and cached analysis if available.

**Response (`200 OK`):**
```json
{
  "attempt_id": "ATMPT00005",
  "customer_id": "CUST0001",
  "mandate_id": "MNDT00001",
  "merchant_name": "Tata Power",
  "amount": 1500.0,
  "attempt_date": "2026-06-05",
  "attempt_number": 1,
  "balance_at_attempt": 240.5,
  "failure_reason": "INSUFFICIENT_FUNDS",
  "recovery_state": "SCHEDULED",
  "decision": "RESCHEDULE",
  "recommended_retry_date": "2026-06-08",
  "recovery_probability": 0.885
}
```

**Errors:**
- `404 Not Found`: Mandate attempt does not exist.

---

### 4.4 Recovery Analysis
**Endpoint:** `POST /api/recovery/{attempt_id}/analyze`

Executes the ML prediction and deterministic decision engine pipeline:
1. Feature extraction with temporal windowing (`<= attempt_date`).
2. Point-in-time recovery scoring and 30-day candidate distribution scoring.
3. Policy engine rule evaluation (`RESCHEDULE`, `RETRY_NOW`, `DO_NOT_RETRY`, etc.).
4. Persists the analysis to SQLite for fast retrieval.

**Response (`200 OK`):**
```json
{
  "attempt_id": "ATMPT00005",
  "customer_id": "CUST0001",
  "mandate_id": "MNDT00001",
  "amount": 1500.0,
  "failure_reason": "INSUFFICIENT_FUNDS",
  "recovery_probability": 0.885,
  "candidate_retry_windows": [
    {
      "date": "2026-06-08",
      "success_probability": 0.912
    },
    {
      "date": "2026-06-09",
      "success_probability": 0.895
    }
  ],
  "recommended_retry_date": "2026-06-08",
  "decision": "RESCHEDULE",
  "reason_codes": [
    "HIGH_RECOVERY_PROBABILITY",
    "VALID_RETRY_WINDOW"
  ],
  "requires_customer_consent": true
}
```

---

### 4.5 Conversational Agent Message
**Endpoint:** `POST /api/agent/{attempt_id}/message`

Passes a message to the LangGraph Recovery Agent. Persists conversational context in SQLite across multi-turn exchanges.

**Request Body:**
```json
{
  "message": "Yes, please go ahead and schedule the retry."
}
```

**Response (`200 OK`):**
```json
{
  "attempt_id": "ATMPT00005",
  "response": "Successfully scheduled retry for ATMPT00005 on 2026-06-08.",
  "action_status": "COMPLETED",
  "recovery_state": "SCHEDULED",
  "consent_granted": true,
  "messages": [
    "Agent: Hello! Your mandate payment failed due to insufficient funds. Our recovery model predicts optimal funds on 2026-06-08. Would you like us to schedule a retry for 2026-06-08?",
    "Customer: Yes, please go ahead and schedule the retry.",
    "Tool schedule_retry success: Successfully scheduled retry for ATMPT00005 on 2026-06-08."
  ]
}
```

**Boundary Safeguards:**
- If the customer declines ("No, do not schedule"), the agent triggers fallback (`PAYMENT_LINK`) and will not call `schedule_retry`.
- If a date mismatch occurs, tool boundary triggers `ToolException`, rejected with `ACTION_REJECTED`.

---

### 4.6 Recovery Status
**Endpoint:** `GET /api/recovery/{attempt_id}/status`

Queries the authoritative lifecycle state from SQLite (`db/app_state.db`).

**Response (`200 OK`):**
```json
{
  "attempt_id": "ATMPT00005",
  "customer_id": "CUST0001",
  "status": "SCHEDULED",
  "scheduled_date": "2026-06-08",
  "execution_time": null,
  "outcome": null,
  "reason": null
}
```

**Lifecycle State Values:**
- `PENDING`: Attempt failed, recovery analysis pending or uncommitted.
- `SCHEDULED`: Dual consent verified and retry date locked in SQLite.
- `EXECUTED`: Payment simulator has processed the retry attempt.
- `ACTION_REJECTED`: Request rejected by security bounds (e.g. revoked consent, unauthorized date).

---

### 4.7 Retry Execution
**Endpoint:** `POST /api/recovery/{attempt_id}/execute`

Triggers the isolated `PaymentSimulator` to process a scheduled retry.

**Response (`200 OK`):**
```json
{
  "attempt_id": "ATMPT00005",
  "scheduled_date": "2026-06-08",
  "result": "SUCCESS",
  "reason": "Payment recovered successfully."
}
```

**Errors:**
- `400 Bad Request`: Attempt is not in `SCHEDULED` state.
- `404 Not Found`: Attempt ID has not been recorded in system state.

---

## 5. Standard Error Format

All errors return uniform, JSON-formatted bodies without stack traces:

```json
{
  "error": "ClientError",
  "detail": "Cannot execute retry: Attempt is in 'PENDING' state, expected 'SCHEDULED'."
}
```
