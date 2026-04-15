import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Colors } from '../../src/constants/colors';
import { api, SettlementRow } from '../../src/services/api';
import { useMerchant } from '../../src/context/MerchantContext';
import DuxIQChat from '../../src/components/DuxIQChat';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtCurrency(n: number | string) {
  return '₹' + Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

function fmtDate(d: string | null) {
  if (!d) return '—';
  try {
    return new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch { return d; }
}

const STATUS_CFG: Record<string, { icon: string; color: string; bg: string; label: string }> = {
  PROCESSED: { icon: 'check-circle',    color: Colors.success, bg: Colors.successLight, label: 'Processed' },
  SETTLED:   { icon: 'check-circle',    color: Colors.success, bg: Colors.successLight, label: 'Settled'   },
  HELD:      { icon: 'clock-alert',     color: Colors.warning, bg: Colors.warningLight, label: 'Held'      },
  PENDING:   { icon: 'clock-outline',   color: '#3B82F6',      bg: '#EFF6FF',           label: 'Pending'   },
  FAILED:    { icon: 'close-circle',    color: Colors.danger,  bg: Colors.dangerLight,  label: 'Failed'    },
};

function statusCfg(s: string) {
  return STATUS_CFG[s?.toUpperCase()] ?? { icon: 'help-circle-outline', color: Colors.textMuted, bg: '#F5F5F4', label: s || '—' };
}

// ---------------------------------------------------------------------------
// Screen
// ---------------------------------------------------------------------------

export default function SettlementsScreen() {
  const { merchantId } = useMerchant();
  const [settlements, setSettlements] = useState<SettlementRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Chat state
  const [chatVisible, setChatVisible] = useState(false);
  const [selectedSettlement, setSelectedSettlement] = useState<SettlementRow | null>(null);

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    setError(null);
    try {
      const rows = await api.getSettlements(merchantId, 60);
      setSettlements(rows);
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load settlements');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [merchantId]);

  useEffect(() => { load(); }, [load]);

  const onRefresh = () => {
    setRefreshing(true);
    load(true);
  };

  const openChat = (s: SettlementRow) => {
    setSelectedSettlement(s);
    setChatVisible(true);
  };

  // Summary stats
  const totalSettled = settlements
    .filter(s => ['PROCESSED', 'SETTLED'].includes(s.status?.toUpperCase()))
    .reduce((sum, s) => sum + (Number(s.amount_rupees) || 0), 0);
  const heldCount = settlements.filter(s => ['HELD', 'PENDING'].includes(s.status?.toUpperCase())).length;

  return (
    <SafeAreaView style={s.safeArea} edges={['top']}>
      <View style={s.header}>
        <Text style={s.headerTitle}>Settlements</Text>
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
        <ScrollView
          style={s.list}
          contentContainerStyle={s.listContent}
          showsVerticalScrollIndicator={false}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.primary} />}
        >
          {/* Summary Card */}
          <View style={s.summaryCard}>
            <Text style={s.summaryLabel}>TOTAL SETTLED (LAST 60 DAYS)</Text>
            <Text style={s.summaryValue}>{fmtCurrency(totalSettled)}</Text>
            <Text style={s.summaryCount}>
              {settlements.length} settlement{settlements.length !== 1 ? 's' : ''} •{' '}
              {heldCount > 0 ? `${heldCount} held/pending` : 'all clear'}
            </Text>
          </View>

          {/* Hint */}
          <View style={s.hintRow}>
            <MaterialCommunityIcons name="gesture-tap" size={14} color={Colors.textMuted} />
            <Text style={s.hintText}>Tap any settlement to ask DUX IQ about it</Text>
          </View>

          {/* Settlement rows */}
          {settlements.length === 0 ? (
            <View style={s.empty}>
              <Text style={s.emptyText}>No settlements in the last 60 days</Text>
            </View>
          ) : (
            settlements.map(item => {
              const cfg = statusCfg(item.status);
              const date = item.expected_date || item.settled_at;
              return (
                <TouchableOpacity
                  key={item.settlement_id}
                  testID={`settlement-item-${item.settlement_id}`}
                  style={s.itemCard}
                  onPress={() => openChat(item)}
                  activeOpacity={0.75}
                >
                  <View style={s.itemLeft}>
                    <View style={[s.itemIconWrap, { backgroundColor: cfg.bg }]}>
                      <MaterialCommunityIcons name={cfg.icon as any} size={20} color={cfg.color} />
                    </View>
                    <View>
                      <Text style={s.itemId}>#{item.settlement_id}</Text>
                      <Text style={s.itemDate}>{fmtDate(date)}</Text>
                    </View>
                  </View>
                  <View style={s.itemRight}>
                    <Text style={s.itemAmount}>{fmtCurrency(item.amount_rupees)}</Text>
                    <Text style={[s.itemStatus, { color: cfg.color }]}>{cfg.label}</Text>
                  </View>

                  {/* Ask DUX IQ caret */}
                  <View style={s.chatCue}>
                    <MaterialCommunityIcons name="robot-outline" size={15} color={Colors.primary} />
                  </View>
                </TouchableOpacity>
              );
            })
          )}
        </ScrollView>
      )}

      {/* Chat modal */}
      <DuxIQChat
        visible={chatVisible}
        onClose={() => { setChatVisible(false); setSelectedSettlement(null); }}
        merchantId={merchantId}
        settlement={
          selectedSettlement
            ? {
                id: selectedSettlement.settlement_id,
                amount: selectedSettlement.amount_rupees,
                status: selectedSettlement.status,
                date: selectedSettlement.expected_date || selectedSettlement.settled_at,
              }
            : undefined
        }
      />
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const s = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: Colors.background },
  header: {
    paddingHorizontal: 16,
    paddingVertical: 16,
    backgroundColor: Colors.white,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  headerTitle: { fontSize: 22, fontWeight: '800', color: Colors.textMain },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 },
  errorText: { fontSize: 14, color: Colors.textMuted, textAlign: 'center', paddingHorizontal: 32 },
  retryBtn: {
    paddingHorizontal: 24, paddingVertical: 10,
    backgroundColor: Colors.primary, borderRadius: 12,
  },
  retryText: { color: Colors.white, fontWeight: '700', fontSize: 14 },
  list: { flex: 1 },
  listContent: { padding: 16, paddingBottom: 30 },
  summaryCard: {
    backgroundColor: Colors.darkCardBg,
    borderRadius: 20, padding: 24, marginBottom: 16,
  },
  summaryLabel: {
    fontSize: 11, fontWeight: '700', color: '#A8A29E', letterSpacing: 0.8,
  },
  summaryValue: {
    fontSize: 28, fontWeight: '900', color: Colors.white, marginTop: 6,
  },
  summaryCount: { fontSize: 13, color: '#A8A29E', marginTop: 4 },
  hintRow: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    marginBottom: 12, paddingHorizontal: 2,
  },
  hintText: { fontSize: 12, color: Colors.textMuted, fontStyle: 'italic' },
  empty: { alignItems: 'center', paddingTop: 48 },
  emptyText: { fontSize: 14, color: Colors.textMuted },
  itemCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.white,
    borderRadius: 16,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  itemLeft: { flexDirection: 'row', alignItems: 'center', gap: 12, flex: 1 },
  itemIconWrap: {
    width: 38, height: 38, borderRadius: 19,
    alignItems: 'center', justifyContent: 'center',
  },
  itemId: { fontSize: 14, fontWeight: '700', color: Colors.textMain },
  itemDate: { fontSize: 11, color: Colors.textMuted, marginTop: 2 },
  itemRight: { alignItems: 'flex-end', marginRight: 8 },
  itemAmount: { fontSize: 16, fontWeight: '800', color: Colors.textMain },
  itemStatus: { fontSize: 11, fontWeight: '700', marginTop: 2 },
  chatCue: {
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: '#FFF1E6',
    alignItems: 'center', justifyContent: 'center',
  },
});
