import { Platform } from 'react-native';

// iOS simulator → localhost, Android emulator → 10.0.2.2
const BASE =
  Platform.OS === 'android'
    ? 'http://10.0.2.2:8000/api/v1'
    : 'http://localhost:8000/api/v1';

// ---------------------------------------------------------------------------
// Shared types
// ---------------------------------------------------------------------------

export interface MerchantOption {
  merchant_id: string;
  label: string;
  merchant_trade_name: string;
}

export interface SettlementRow {
  settlement_id: number;
  amount_rupees: number;
  status: string;
  expected_date: string | null;
  settled_at: string | null;
}

export interface TransactionRow {
  tx_id: number | string;
  p_date: string;
  initiated_at: string | null;
  completed_at: string | null;
  payment_mode: string | null;
  status: string;
  response_code: string | null;
  amount_rupees: number | null;
  terminal_id: string | null;
}

export interface TerminalRow {
  terminal_id: string;
  attempts: number;
  success_rate_pct: number;
  success_gmv: number;
}

export interface ChargebackRow {
  chargeback_id: number | string;
  status: string | null;
  opened_at: string | null;
  due_by: string | null;
  amount_rupees: number | string | null;
  reason_code: string | null;
}

export interface RefundRow {
  refund_id: number | string | null;
  status: string;
  created_at: string | null;
  amount_rupees: number | string | null;
  tx_id: number | string | null;
}

export interface ChargebackSummary {
  chargebacks_count: number;
  open_chargebacks_count: number;
  overdue_chargebacks_count: number;
  due_soon_chargebacks_count: number;
  chargebacks_amount: number;
  top_reason: { reason_code: string; count: number } | null;
  stage_distribution: { status: string; count: number }[];
}

export interface MerchantProfile {
  mid: string;
  merchant_trade_name: string;
  nature_of_business: string | null;
  business_city: string | null;
}

export interface SnapshotSummary {
  attempts: number;
  success_txns: number;
  fail_txns: number;
  success_rate_pct: number;
  success_gmv: number;
  terminal_count: number;
  open_chargebacks: number;
}

export interface SnapshotCashflow {
  amounts: {
    pending_amount: number;
    settled_amount: number;
  };
}

export interface Snapshot {
  merchant_profile: { merchant: MerchantProfile };
  summary: SnapshotSummary;
  cashflow: SnapshotCashflow;
  settlements: { rows: SettlementRow[] };
}

export interface ContextObject {
  type: 'settlement';
  id: string;
  metadata: {
    amount?: number;
    status?: string;
    date?: string;
  };
}

export interface ChatHistoryItem {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  answer: string;
  follow_ups: string[];
  sources: string[];
  agent_name?: string;
  handoff_chain?: string[];
  trace?: unknown;
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${text || path}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getMerchants: () =>
    req<{ merchants: MerchantOption[]; default_merchant_id: string }>(
      '/merchants/options'
    ),

  getSnapshot: (merchantId: string, days = 60) =>
    req<{ snapshot: Snapshot }>(
      `/merchant/snapshot?merchant_id=${encodeURIComponent(merchantId)}&days=${days}`
    ).then(d => d.snapshot),

  getTerminalPerformance: (merchantId: string, days = 30) =>
    req<{ terminals: { rows: TerminalRow[]; error: string | null } }>(
      `/merchant/terminal-performance?merchant_id=${encodeURIComponent(merchantId)}&days=${days}&limit=20`
    ).then(d => d?.terminals?.rows ?? []),

  getChargebacks: (merchantId: string, days = 90) =>
    req<{
      chargebacks: { rows: ChargebackRow[] };
      summary: ChargebackSummary;
      refunds: { rows: RefundRow[] };
    }>(`/merchant/chargebacks?merchant_id=${encodeURIComponent(merchantId)}&days=${days}&status=all&limit=100`),

  getTransactions: (merchantId: string, days = 30, status: 'ALL' | 'SUCCESS' | 'FAILURE' = 'ALL', limit = 50) =>
    req<{ transactions: { rows: TransactionRow[]; error: string | null } }>(
      `/merchant/transactions?merchant_id=${encodeURIComponent(merchantId)}&days=${days}&status=${status}&limit=${limit}`
    ).then(d => d?.transactions?.rows ?? []),

  getSettlements: (merchantId: string, days = 60) =>
    req<{ snapshot: { settlements: { rows: SettlementRow[] } } }>(
      `/merchant/snapshot?merchant_id=${encodeURIComponent(merchantId)}&days=${days}`
    ).then(d => d?.snapshot?.settlements?.rows ?? []),

  askSettlement: (params: {
    merchantId: string;
    prompt: string;
    contextObject?: ContextObject;
    history?: ChatHistoryItem[];
  }) =>
    req<ChatResponse>('/ask/settlement', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        merchant_id: params.merchantId,
        prompt: params.prompt,
        context_object: params.contextObject ?? null,
        history: params.history ?? [],
      }),
    }),

  uploadDisputeEvidence: (params: {
    fileUri: string;
    fileName: string;
    mimeType: string;
    merchantId: string;
    chargebackId?: string | number;
  }) => {
    const form = new FormData();
    form.append('file', { uri: params.fileUri, name: params.fileName, type: params.mimeType } as any);
    form.append('merchant_id', params.merchantId);
    if (params.chargebackId != null) {
      form.append('context', JSON.stringify({ chargeback_id: String(params.chargebackId) }));
    }
    return req<{
      ok: boolean;
      error: string | null;
      evidence_id: string;
      confidence: 'high' | 'partial' | 'low';
      extracted: {
        amount?: string;
        date?: string;
        time?: string;
        transaction_id?: string;
        approval_code?: string;
        card_last4?: string;
        card_scheme?: string;
        terminal_id?: string;
        merchant_name?: string;
        status?: string;
      };
    }>('/dispute/upload-receipt', {
      method: 'POST',
      body: form,
    });
  },

  ask: (params: {
    merchantId: string;
    prompt: string;
    history?: ChatHistoryItem[];
  }) =>
    req<ChatResponse>('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        merchant_id: params.merchantId,
        prompt: params.prompt,
        history: params.history ?? [],
      }),
    }),
};
