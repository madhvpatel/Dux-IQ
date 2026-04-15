# Bank Foundry API Specification
Version: 1.1.0

## 1. Health
`GET /health`
Returns system health status.
**Response:** `{"status": "ok"}`

## 2. Merchant Workspace

### Get Merchant Options
`GET /api/v1/merchants/options`
**Query Parameters:**
- `limit` (int, default: 25, 1-100)

### Get Merchant Snapshot
`GET /api/v1/merchant/snapshot`
**Query Parameters:**
- `merchant_id` (string, optional)
- `terminal_id` (string, optional)
- `days` (int, default: 30, 7-90)

### Get Merchant Reports
`GET /api/v1/merchant/reports`
**Query Parameters:**
- `merchant_id` (string, optional)
- `terminal_id` (string, optional)
- `days` (int, default: 30, 7-90)

### Get Terminal Options
`GET /api/v1/merchant/terminals`
**Query Parameters:**
- `merchant_id` (string, optional)
- `days` (int, default: 30, 7-90)

## 3. Chat & Copilot

### Ask Endpoint (Chat)
`POST /api/v1/ask`
**JSON Body:**
```json
{
  "merchant_id": "string (optional)",
  "prompt": "string",
  "terminal_id": "string (optional)",
  "thread_scope": "string (optional)",
  "history": [{"role": "string", "content": "string"}],
  "debug": false
}
```

## 4. Proactive Inbox

### Get Proactive Nudges
`GET /api/v1/copilot/proactive`
**Query Parameters:**
- `merchant_id` (string, optional)
- `terminal_id` (string, optional)
- `lane` (string, "operations"|"growth"|"all", default: "operations")
- `days` (int, default: 30, 7-90)

### Refresh Proactive Cards
`POST /api/v1/copilot/proactive/refresh`
**JSON Body:**
```json
{
  "merchant_id": "string (optional)",
  "days": 30,
  "force": true
}
```

### Set Proactive Card State
`POST /api/v1/copilot/proactive/card/state`
**JSON Body:**
```json
{
  "merchant_id": "string (optional)",
  "dedupe_key": "string",
  "state": "NEW" | "ACKNOWLEDGED" | "DISMISSED" | "CONVERTED",
  "card_notes": "string (optional)"
}
```

### Preview Proactive Card Action
`POST /api/v1/copilot/proactive/card/preview-action`
**JSON Body:**
```json
{
  "merchant_id": "string (optional)",
  "dedupe_key": "string"
}
```

### Confirm Proactive Card Action
`POST /api/v1/copilot/proactive/card/confirm-action`
**JSON Body:**
```json
{
  "merchant_id": "string (optional)",
  "dedupe_key": "string",
  "confirmation_token": "string"
}
```

## 5. Action Center

### Preview Action
`POST /api/v1/actions/preview`
**JSON Body:**
```json
{
  "merchant_id": "string (optional)",
  "action_type": "string",
  "payload": {}
}
```

### Confirm Action
`POST /api/v1/actions/confirm`
**JSON Body:**
```json
{
  "merchant_id": "string (optional)",
  "confirmation_token": "string"
}
```

### Set Action Status
`POST /api/v1/actions/status`
**JSON Body:**
```json
{
  "merchant_id": "string (optional)",
  "action_id": "any",
  "status": "string"
}
```

### Set Action Details
`POST /api/v1/actions/details`
**JSON Body:**
```json
{
  "merchant_id": "string (optional)",
  "action_id": "any",
  "owner": "string (optional)",
  "notes": "string (optional)",
  "blocked_reason": "string (optional)",
  "follow_up_date": "string (optional)"
}
```

### Cleanup Legacy Actions
`POST /api/v1/actions/cleanup-legacy`
**JSON Body:**
```json
{
  "merchant_id": "string (optional)"
}
```

## 6. Bank Operations Console

### Get Ops Queue
`GET /api/v1/ops/queue`
**Query Parameters:**
- `merchant_id` (string, optional)
- `lane` (string, "operations"|"support"|"risk", default: "operations")
- `role` (string, default: "acquiring_ops")
- `status` (string, optional)
- `owner` (string, optional)
- `limit` (int, default: 25, 1-100)

### Create Ops Case
`POST /api/v1/ops/cases`
**JSON Body:**
```json
{
  "merchant_id": "string (optional)",
  "terminal_id": "string (optional)",
  "lane": "operations" | "support" | "risk",
  "role": "acquiring_ops",
  "case_type": "manual_ops_review",
  "title": "string",
  "summary": "string",
  "priority": "medium",
  "severity": "string (optional)",
  "owner": "string (optional)",
  "evidence_ids": [],
  "links": []
}
```

### Get Ops Case Details
`GET /api/v1/ops/cases/{case_id}`
**Query Parameters:**
- `merchant_id` (string, optional)
- `role` (string, default: "acquiring_ops")

### Promote Ops Case
`POST /api/v1/ops/cases/promote`
**JSON Body:**
```json
{
  "merchant_id": "string (optional)",
  "lane": "operations" | "support" | "risk",
  "role": "acquiring_ops",
  "source_type": "proactive_card" | "merchant_action" | "chat_finding",
  "source_ref": "string (optional)",
  "source_payload": {}
}
```

### Assign Ops Case
`POST /api/v1/ops/cases/{case_id}/assign`
**JSON Body:**
```json
{
  "merchant_id": "string (optional)",
  "role": "acquiring_ops",
  "owner": "string"
}
```

### Add Ops Case Note
`POST /api/v1/ops/cases/{case_id}/notes`
**JSON Body:**
```json
{
  "merchant_id": "string (optional)",
  "role": "acquiring_ops",
  "body": "string"
}
```

### Get Ops Case Copilot Analysis
`POST /api/v1/ops/cases/{case_id}/copilot`
**JSON Body:**
```json
{
  "merchant_id": "string (optional)",
  "role": "acquiring_ops",
  "prompt": "string (optional)"
}
```

### Update Ops Case Memory
`POST /api/v1/ops/cases/{case_id}/memory`
**JSON Body:**
```json
{
  "merchant_id": "string (optional)",
  "role": "acquiring_ops",
  "settlement_id": "string (optional)",
  "start_date": "string (optional)",
  "end_date": "string (optional)",
  "evidence_ids": [],
  "clear_pinned_context": false,
  "clear_window": false,
  "clear_evidence": false
}
```

### Request Ops Case Approval
`POST /api/v1/ops/cases/{case_id}/approval`
**JSON Body:**
```json
{
  "merchant_id": "string (optional)",
  "role": "acquiring_ops",
  "action_type": "string",
  "payload_summary": "string",
  "payload": {}
}
```

### Resolve Ops Case
`POST /api/v1/ops/cases/{case_id}/resolve`
**JSON Body:**
```json
{
  "merchant_id": "string (optional)",
  "role": "acquiring_ops",
  "resolution_note": "string (optional)",
  "status": "RESOLVED" | "CLOSED"
}
```

### Get Ops Approvals
`GET /api/v1/ops/approvals`
**Query Parameters:**
- `merchant_id` (string, optional)
- `lane` (string, "operations"|"support"|"risk", default: "operations")
- `role` (string, default: "acquiring_ops")
- `status` (string, default: "PENDING")
- `limit` (int, default: 25, 1-100)

### Decide Ops Approval
`POST /api/v1/ops/approvals/{approval_id}/decision`
**JSON Body:**
```json
{
  "merchant_id": "string (optional)",
  "lane": "operations" | "support" | "risk",
  "role": "acquiring_ops",
  "decision": "APPROVED" | "REJECTED",
  "notes": "string (optional)"
}
```

## 7. Analytics

### Get Dashboard Metrics
`GET /api/v1/analytics/dashboard`
**Query Parameters:**
- `merchant_id` (string, optional)
- `terminal_id` (string, optional)

## 8. Disputes

### Upload Dispute Receipt
`POST /api/v1/dispute/upload-receipt`
**Content-Type:** `multipart/form-data`
**Body Parameters:**
- `file` (file, required)
- `merchant_id` (string, optional)
- `context` (JSON string, optional)
