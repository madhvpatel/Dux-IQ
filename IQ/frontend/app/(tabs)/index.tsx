import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, ScrollView, StyleSheet,
  Platform, ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { Colors } from '../../src/constants/colors';
import { api, Snapshot, SettlementRow } from '../../src/services/api';
import { useMerchant } from '../../src/context/MerchantContext';
import DuxIQChat from '../../src/components/DuxIQChat';

function fmtCurrency(n: number) {
  return '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

function fmtDate(d: string | null) {
  if (!d) return '—';
  try {
    return new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch { return d; }
}

function lastSettledRow(rows: SettlementRow[]): SettlementRow | null {
  const settled = rows.filter(r => ['PROCESSED', 'SETTLED'].includes(r.status?.toUpperCase()));
  if (!settled.length) return null;
  return settled.reduce((a, b) => {
    const da = new Date(a.settled_at || a.expected_date || '').getTime();
    const db = new Date(b.settled_at || b.expected_date || '').getTime();
    return db > da ? b : a;
  });
}

function KPICard({ label, icon, value, testID }: { label: string; icon: string; value: string; testID: string }) {
  return (
    <View style={s.kpiCard} testID={testID}>
      <View style={s.kpiIconWrap}>
        <MaterialCommunityIcons name={icon as any} size={20} color={Colors.primary} />
      </View>
      <Text style={s.kpiLabel}>{label}</Text>
      <Text style={s.kpiValue}>{value}</Text>
    </View>
  );
}

export default function Dashboard() {
  const router = useRouter();
  const { merchantId, merchantName, merchantMid } = useMerchant();
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chatVisible, setChatVisible] = useState(false);

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    setError(null);
    try {
      const snap = await api.getSnapshot(merchantId);
      setSnapshot(snap);
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load dashboard');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [merchantId]);

  useEffect(() => { if (merchantId) load(); }, [load, merchantId]);

  const onRefresh = () => { setRefreshing(true); load(true); };

  if (loading) {
    return (
      <SafeAreaView style={s.safeArea} edges={['top']}>
        <View style={s.center}>
          <ActivityIndicator size="large" color={Colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  if (error || !snapshot) {
    return (
      <SafeAreaView style={s.safeArea} edges={['top']}>
        <View style={s.center}>
          <MaterialCommunityIcons name="wifi-off" size={40} color={Colors.textMuted} />
          <Text style={s.errorText}>{error ?? 'No data'}</Text>
          <TouchableOpacity style={s.retryBtn} onPress={() => load()}>
            <Text style={s.retryText}>Retry</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const { summary, cashflow, settlements, merchant_profile } = snapshot;
  const profile = merchant_profile?.merchant;
  const lastPayout = lastSettledRow(settlements?.rows ?? []);

  const kpis = [
    { label: 'TOTAL SALES (GMV)', icon: 'credit-card-outline', value: fmtCurrency(summary.success_gmv), testID: 'kpi-sales-today' },
    { label: 'SUCCESS TRANSACTIONS', icon: 'file-document-outline', value: String(summary.success_txns), testID: 'kpi-total-transactions' },
    { label: 'PENDING SETTLEMENT', icon: 'cash-clock', value: fmtCurrency(cashflow.amounts.pending_amount), testID: 'kpi-pending-settlement' },
    { label: 'LAST PAYOUT', icon: 'cash-check', value: lastPayout ? fmtCurrency(lastPayout.amount_rupees) : '—', testID: 'kpi-last-payout' },
  ];

  return (
    <SafeAreaView style={s.safeArea} edges={['top']}>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={s.scrollContent}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.primary} />}
      >
        {/* Header Bar */}
        <View style={s.headerBar}>
          <TouchableOpacity testID="header-menu-btn" style={s.headerIcon}>
            <MaterialCommunityIcons name="menu" size={24} color={Colors.textMain} />
          </TouchableOpacity>
          <View style={s.headerRight}>
            <TouchableOpacity style={s.headerIcon}>
              <MaterialCommunityIcons name="wallet-outline" size={22} color={Colors.textMain} />
            </TouchableOpacity>
            <TouchableOpacity style={s.headerIcon}>
              <MaterialCommunityIcons name="account-outline" size={22} color={Colors.textMain} />
            </TouchableOpacity>
          </View>
        </View>

        {/* Merchant Info */}
        <View style={s.merchantCard}>
          <View style={s.merchantLeft}>
            <Text testID="header-merchant-name" style={s.merchantName}>
              {profile?.merchant_trade_name ?? merchantName}
            </Text>
            <Text style={s.merchantIds}>
              MID: {profile?.mid ?? merchantMid}
              {profile?.business_city ? `  \u2022  ${profile.business_city}` : ''}
            </Text>
          </View>
          <TouchableOpacity onPress={() => router.push('/(tabs)/profile')}>
            <Text style={s.viewDetailsLink}>View Details {'>'}</Text>
          </TouchableOpacity>
        </View>

        {/* KPI Grid */}
        <View style={s.kpiGrid}>
          {kpis.map(k => (
            <KPICard key={k.testID} label={k.label} icon={k.icon} value={k.value} testID={k.testID} />
          ))}
        </View>

        {/* Last Payout Card */}
        <View style={s.payoutCard} testID="payout-details-card">
          <View style={s.payoutTop}>
            <View>
              <Text style={s.payoutLabel}>LAST PAYOUT DETAILS</Text>
              <Text style={s.payoutAmount}>
                {lastPayout ? fmtCurrency(lastPayout.amount_rupees) : '—'}
              </Text>
              <Text style={s.payoutDate}>
                {lastPayout
                  ? fmtDate(lastPayout.settled_at || lastPayout.expected_date)
                  : 'No payouts yet'}
              </Text>
            </View>
            <View style={s.payoutIconWrap}>
              <MaterialCommunityIcons name="bank" size={28} color="rgba(255,255,255,0.3)" />
            </View>
          </View>
          <View style={s.payoutBtns}>
            <TouchableOpacity
              style={s.payoutBtnOutline}
              testID="btn-view-payout-history"
              onPress={() => router.push('/(tabs)/settlements')}
            >
              <Text style={s.payoutBtnOutlineText}>View History</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={s.payoutBtnFilled}
              testID="btn-ask-dux-iq"
              onPress={() => setChatVisible(true)}
            >
              <Text style={s.payoutBtnFilledPre}>Ask </Text>
              <Text style={s.payoutBtnDux}>DUX</Text>
              <Text style={s.payoutBtnIq}>{'\u00AE'}IQ</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Quick Stats */}
        <View style={s.statsRow}>
          <View style={s.statCard}>
            <Text style={s.statValue}>{summary.success_rate_pct?.toFixed(1) ?? '—'}%</Text>
            <Text style={s.statLabel}>Success Rate</Text>
          </View>
          <View style={s.statCard}>
            <Text style={s.statValue}>{summary.terminal_count ?? '—'}</Text>
            <Text style={s.statLabel}>Terminals</Text>
          </View>
          <View style={s.statCard}>
            <Text style={[s.statValue, summary.open_chargebacks > 0 && { color: Colors.danger }]}>
              {summary.open_chargebacks ?? 0}
            </Text>
            <Text style={s.statLabel}>Open Disputes</Text>
          </View>
          <View style={s.statCard}>
            <Text style={s.statValue}>{summary.fail_txns ?? '—'}</Text>
            <Text style={s.statLabel}>Failed Txns</Text>
          </View>
        </View>

        {/* Transactions shortcut */}
        <TouchableOpacity style={s.txnShortcut} onPress={() => router.push('/(tabs)/transactions')}>
          <View style={s.txnShortcutLeft}>
            <MaterialCommunityIcons name="swap-horizontal" size={20} color={Colors.primary} />
            <Text style={s.txnShortcutText}>View Transactions</Text>
          </View>
          <MaterialCommunityIcons name="chevron-right" size={20} color={Colors.textMuted} />
        </TouchableOpacity>

        <View style={{ height: 24 }} />
      </ScrollView>

      <DuxIQChat visible={chatVisible} onClose={() => setChatVisible(false)} merchantId={merchantId} />
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: Colors.background },
  scroll: { flex: 1 },
  scrollContent: { paddingBottom: 20 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 },
  errorText: { fontSize: 14, color: Colors.textMuted, textAlign: 'center', paddingHorizontal: 32 },
  retryBtn: { paddingHorizontal: 24, paddingVertical: 10, backgroundColor: Colors.primary, borderRadius: 12 },
  retryText: { color: Colors.white, fontWeight: '700', fontSize: 14 },
  headerBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: Colors.white,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  headerIcon: {
    width: 40, height: 40, borderRadius: 20,
    alignItems: 'center', justifyContent: 'center',
  },
  headerRight: { flexDirection: 'row', gap: 4 },
  merchantCard: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginHorizontal: 16,
    marginTop: 16,
    backgroundColor: Colors.white,
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  merchantLeft: { flex: 1 },
  merchantName: { fontSize: 18, fontWeight: '800', color: Colors.textMain },
  merchantIds: {
    fontSize: 11, color: Colors.textMuted, marginTop: 4,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  viewDetailsLink: { fontSize: 13, color: Colors.primary, fontWeight: '600' },
  kpiGrid: {
    flexDirection: 'row', flexWrap: 'wrap',
    paddingHorizontal: 16, marginTop: 16, gap: 12,
  },
  kpiCard: {
    width: '47%', backgroundColor: Colors.white, borderRadius: 16,
    padding: 16, borderWidth: 1, borderColor: Colors.border,
  },
  kpiIconWrap: {
    width: 36, height: 36, borderRadius: 10,
    backgroundColor: '#FFF1E6', alignItems: 'center',
    justifyContent: 'center', marginBottom: 10,
  },
  kpiLabel: { fontSize: 10, fontWeight: '700', color: Colors.textMuted, letterSpacing: 0.5 },
  kpiValue: { fontSize: 20, fontWeight: '800', color: Colors.textMain, marginTop: 4 },
  payoutCard: {
    marginHorizontal: 16, marginTop: 16,
    backgroundColor: Colors.darkCardBg,
    borderRadius: 20, padding: 20, overflow: 'hidden',
  },
  payoutTop: { flexDirection: 'row', justifyContent: 'space-between' },
  payoutLabel: { fontSize: 11, fontWeight: '700', color: '#A8A29E', letterSpacing: 1 },
  payoutAmount: { fontSize: 28, fontWeight: '900', color: Colors.white, marginTop: 6 },
  payoutDate: { fontSize: 13, color: '#A8A29E', marginTop: 4 },
  payoutIconWrap: {
    width: 48, height: 48, borderRadius: 14,
    backgroundColor: 'rgba(255,255,255,0.08)',
    alignItems: 'center', justifyContent: 'center',
  },
  payoutBtns: { flexDirection: 'row', gap: 12, marginTop: 20 },
  payoutBtnOutline: {
    flex: 1, borderWidth: 1, borderColor: '#57534E',
    borderRadius: 14, paddingVertical: 14,
    alignItems: 'center', justifyContent: 'center',
  },
  payoutBtnOutlineText: { fontSize: 14, fontWeight: '700', color: Colors.white },
  payoutBtnFilled: {
    flex: 1, backgroundColor: Colors.primary, borderRadius: 14,
    paddingVertical: 14, alignItems: 'center', justifyContent: 'center',
    flexDirection: 'row',
  },
  payoutBtnFilledPre: { fontSize: 14, fontWeight: '700', color: Colors.white },
  payoutBtnDux: { fontSize: 14, fontWeight: '900', color: Colors.white },
  payoutBtnIq: { fontSize: 14, fontWeight: '900', color: '#86EFAC' },
  statsRow: {
    flexDirection: 'row', marginHorizontal: 16, marginTop: 16, gap: 10,
  },
  statCard: {
    flex: 1, backgroundColor: Colors.white,
    borderRadius: 14, padding: 12,
    alignItems: 'center', borderWidth: 1, borderColor: Colors.border,
  },
  statValue: { fontSize: 18, fontWeight: '900', color: Colors.textMain },
  statLabel: { fontSize: 9, fontWeight: '700', color: Colors.textMuted, marginTop: 3, textAlign: 'center' },
  txnShortcut: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    marginHorizontal: 16, marginTop: 16, backgroundColor: Colors.white,
    borderRadius: 14, padding: 16, borderWidth: 1, borderColor: Colors.border,
  },
  txnShortcutLeft: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  txnShortcutText: { fontSize: 15, fontWeight: '700', color: Colors.textMain },
});
