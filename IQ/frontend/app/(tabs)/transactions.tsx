import React, { useState, useCallback, useEffect } from 'react';
import {
  View, Text, TouchableOpacity, ScrollView, StyleSheet,
  Platform, ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Colors } from '../../src/constants/colors';
import { api, TransactionRow } from '../../src/services/api';
import { useMerchant } from '../../src/context/MerchantContext';
import DuxIQChat from '../../src/components/DuxIQChat';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtCurrency(n: number | null) {
  if (n == null) return '—';
  return '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

function fmtDateTime(iso: string | null) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    const date = d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
    const time = d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });
    return { date, time };
  } catch { return { date: iso, time: '' }; }
}

type FilterStatus = 'ALL' | 'SUCCESS' | 'FAILURE';

const FILTER_TABS: { key: FilterStatus; label: string }[] = [
  { key: 'ALL', label: 'All' },
  { key: 'SUCCESS', label: 'Success' },
  { key: 'FAILURE', label: 'Failed' },
];

const STATUS_CFG: Record<string, { color: string; bg: string; icon: string }> = {
  SUCCESS: { color: Colors.success, bg: Colors.successLight, icon: 'check-circle' },
  FAILURE: { color: Colors.danger, bg: Colors.dangerLight, icon: 'close-circle' },
  FAILED:  { color: Colors.danger, bg: Colors.dangerLight, icon: 'close-circle' },
};

function statusCfg(s: string) {
  return STATUS_CFG[s?.toUpperCase()] ?? {
    color: Colors.warning, bg: Colors.warningLight, icon: 'clock-outline',
  };
}

// ---------------------------------------------------------------------------
// Row component
// ---------------------------------------------------------------------------

function TxnRow({ txn, onAsk }: { txn: TransactionRow; onAsk: (txn: TransactionRow) => void }) {
  const cfg = statusCfg(txn.status);
  const dt = fmtDateTime(txn.initiated_at || txn.p_date);
  const dtParsed = typeof dt === 'string' ? { date: dt, time: '' } : dt;

  return (
    <TouchableOpacity
      style={s.txnCard}
      onPress={() => onAsk(txn)}
      activeOpacity={0.75}
      testID={`transaction-item-${txn.tx_id}`}
    >
      <View style={[s.txnIconWrap, { backgroundColor: cfg.bg }]}>
        <MaterialCommunityIcons name={cfg.icon as any} size={22} color={cfg.color} />
      </View>
      <View style={s.txnMid}>
        <Text style={s.txnId}>#{txn.tx_id}</Text>
        <Text style={s.txnMeta}>
          {dtParsed.date}
          {dtParsed.time ? ` \u2022 ${dtParsed.time}` : ''}
          {txn.payment_mode ? ` \u2022 ${txn.payment_mode}` : ''}
        </Text>
      </View>
      <View style={s.txnRight}>
        <Text style={s.txnAmt}>{fmtCurrency(txn.amount_rupees)}</Text>
        <Text style={[s.txnStatus, { color: cfg.color }]}>{txn.status}</Text>
      </View>
      <View style={s.chatCue}>
        <MaterialCommunityIcons name="robot-outline" size={14} color={Colors.primary} />
      </View>
    </TouchableOpacity>
  );
}

// ---------------------------------------------------------------------------
// Screen
// ---------------------------------------------------------------------------

export default function TransactionsScreen() {
  const { merchantId } = useMerchant();
  const [transactions, setTransactions] = useState<TransactionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<FilterStatus>('ALL');
  const [chatVisible, setChatVisible] = useState(false);
  const [selectedTxn, setSelectedTxn] = useState<TransactionRow | null>(null);

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    setError(null);
    try {
      const rows = await api.getTransactions(merchantId, 30, 'ALL', 100);
      setTransactions(rows);
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load transactions');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [merchantId]);

  useEffect(() => { if (merchantId) load(); }, [load, merchantId]);

  const onRefresh = () => { setRefreshing(true); load(true); };

  const openChat = (txn: TransactionRow) => {
    setSelectedTxn(txn);
    setChatVisible(true);
  };

  const filtered = activeFilter === 'ALL'
    ? transactions
    : transactions.filter(t => {
        const s = t.status?.toUpperCase();
        if (activeFilter === 'SUCCESS') return s === 'SUCCESS';
        return s === 'FAILURE' || s === 'FAILED';
      });

  const successCount = transactions.filter(t => t.status?.toUpperCase() === 'SUCCESS').length;
  const failCount = transactions.filter(t => ['FAILURE','FAILED'].includes(t.status?.toUpperCase())).length;

  return (
    <SafeAreaView style={s.safeArea} edges={['top']}>
      <View style={s.header}>
        <Text style={s.headerTitle}>Transactions</Text>
        {!loading && !error && (
          <Text style={s.headerCount}>{filtered.length} shown</Text>
        )}
      </View>

      {loading ? (
        <View style={s.center}>
          <ActivityIndicator size="large" color={Colors.primary} />
        </View>
      ) : error ? (
        <View style={s.center}>
          <MaterialCommunityIcons name="wifi-off" size={40} color={Colors.textMuted} />
          <Text style={s.errorText}>{error}</Text>
          <TouchableOpacity style={s.retryBtn} onPress={() => load()}>
            <Text style={s.retryText}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <>
          {/* Summary pills */}
          <View style={s.summaryRow}>
            <View style={s.summaryPill}>
              <Text style={[s.pillNum, { color: Colors.success }]}>{successCount}</Text>
              <Text style={s.pillLabel}>Successful</Text>
            </View>
            <View style={s.summaryPill}>
              <Text style={[s.pillNum, { color: Colors.danger }]}>{failCount}</Text>
              <Text style={s.pillLabel}>Failed</Text>
            </View>
            <View style={s.summaryPill}>
              <Text style={[s.pillNum, { color: Colors.textMain }]}>{transactions.length}</Text>
              <Text style={s.pillLabel}>Total (30d)</Text>
            </View>
          </View>

          {/* Filter Tabs */}
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            style={s.filterScroll}
            contentContainerStyle={s.filterContent}
          >
            {FILTER_TABS.map(tab => (
              <TouchableOpacity
                key={tab.key}
                testID={`txn-filter-tab-${tab.key.toLowerCase()}`}
                style={[s.filterTab, activeFilter === tab.key && s.filterTabActive]}
                onPress={() => setActiveFilter(tab.key)}
              >
                <Text style={[s.filterTabText, activeFilter === tab.key && s.filterTabTextActive]}>
                  {tab.label}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          {/* Hint */}
          <View style={s.hintRow}>
            <MaterialCommunityIcons name="gesture-tap" size={13} color={Colors.textMuted} />
            <Text style={s.hintText}>Tap any transaction to ask DUX IQ about it</Text>
          </View>

          {/* List */}
          <ScrollView
            style={s.list}
            contentContainerStyle={s.listContent}
            showsVerticalScrollIndicator={false}
            refreshControl={
              <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.primary} />
            }
          >
            {filtered.length === 0 ? (
              <View style={s.empty}>
                <MaterialCommunityIcons name="file-search-outline" size={44} color={Colors.textLight} />
                <Text style={s.emptyText}>No transactions found</Text>
              </View>
            ) : (
              filtered.map(txn => (
                <TxnRow key={String(txn.tx_id)} txn={txn} onAsk={openChat} />
              ))
            )}
            <View style={{ height: 24 }} />
          </ScrollView>
        </>
      )}

      <DuxIQChat
        visible={chatVisible}
        onClose={() => { setChatVisible(false); setSelectedTxn(null); }}
        merchantId={merchantId}
        initialPrompt={
          selectedTxn
            ? `Tell me about transaction #${selectedTxn.tx_id} — ${selectedTxn.status}, ${fmtCurrency(selectedTxn.amount_rupees)}, ${selectedTxn.payment_mode ?? 'unknown mode'}`
            : undefined
        }
      />
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: Colors.background },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: 16, paddingVertical: 16,
    backgroundColor: Colors.white, borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  headerTitle: { fontSize: 22, fontWeight: '800', color: Colors.textMain },
  headerCount: { fontSize: 13, color: Colors.textMuted, fontWeight: '600' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 },
  errorText: { fontSize: 14, color: Colors.textMuted, textAlign: 'center', paddingHorizontal: 32 },
  retryBtn: { paddingHorizontal: 24, paddingVertical: 10, backgroundColor: Colors.primary, borderRadius: 12 },
  retryText: { color: Colors.white, fontWeight: '700', fontSize: 14 },
  summaryRow: {
    flexDirection: 'row', paddingHorizontal: 16, paddingTop: 14, paddingBottom: 4, gap: 10,
  },
  summaryPill: {
    flex: 1, backgroundColor: Colors.white, borderRadius: 14,
    paddingVertical: 10, alignItems: 'center',
    borderWidth: 1, borderColor: Colors.border,
  },
  pillNum: { fontSize: 20, fontWeight: '900' },
  pillLabel: { fontSize: 10, fontWeight: '700', color: Colors.textMuted, marginTop: 2 },
  filterScroll: { maxHeight: 52, marginTop: 10 },
  filterContent: { paddingHorizontal: 16, gap: 8, alignItems: 'center' },
  filterTab: {
    backgroundColor: Colors.white, borderRadius: 20,
    paddingHorizontal: 18, paddingVertical: 8,
    borderWidth: 1, borderColor: Colors.border,
  },
  filterTabActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  filterTabText: { fontSize: 13, fontWeight: '600', color: Colors.textMuted },
  filterTabTextActive: { color: Colors.white },
  hintRow: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    marginHorizontal: 16, marginTop: 10, marginBottom: 2,
  },
  hintText: { fontSize: 12, color: Colors.textMuted, fontStyle: 'italic' },
  list: { flex: 1 },
  listContent: { paddingTop: 8, paddingBottom: 20 },
  txnCard: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: Colors.white, marginHorizontal: 16, marginBottom: 10,
    borderRadius: 16, padding: 14, borderWidth: 1, borderColor: Colors.border,
  },
  txnIconWrap: {
    width: 42, height: 42, borderRadius: 21,
    alignItems: 'center', justifyContent: 'center', marginRight: 12,
  },
  txnMid: { flex: 1 },
  txnId: { fontSize: 14, fontWeight: '700', color: Colors.textMain },
  txnMeta: {
    fontSize: 11, color: Colors.textMuted, marginTop: 2,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  txnRight: { alignItems: 'flex-end', marginRight: 8 },
  txnAmt: { fontSize: 15, fontWeight: '800', color: Colors.textMain },
  txnStatus: { fontSize: 11, fontWeight: '700', marginTop: 2, letterSpacing: 0.3 },
  chatCue: {
    width: 26, height: 26, borderRadius: 13,
    backgroundColor: '#FFF1E6', alignItems: 'center', justifyContent: 'center',
  },
  empty: { alignItems: 'center', paddingTop: 60, gap: 12 },
  emptyText: { fontSize: 15, color: Colors.textMuted, fontWeight: '600' },
});
