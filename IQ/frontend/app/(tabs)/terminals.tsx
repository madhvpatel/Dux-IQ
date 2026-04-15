import React, { useState, useCallback, useEffect } from 'react';
import {
  View, Text, TouchableOpacity, ScrollView, StyleSheet,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Colors } from '../../src/constants/colors';
import { api, TerminalRow } from '../../src/services/api';
import { useMerchant } from '../../src/context/MerchantContext';
import DuxIQChat from '../../src/components/DuxIQChat';

function fmtCurrency(n: number) {
  return '₹' + Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

function healthColor(rate: number) {
  if (rate >= 90) return Colors.success;
  if (rate >= 70) return Colors.warning;
  return Colors.danger;
}

function HealthBar({ pct, color }: { pct: number; color: string }) {
  return (
    <View style={hb.track}>
      <View style={[hb.fill, { width: `${Math.min(pct, 100)}%` as any, backgroundColor: color }]} />
    </View>
  );
}

const hb = StyleSheet.create({
  track: { height: 4, backgroundColor: '#E7E5E4', borderRadius: 2, flex: 1 },
  fill: { height: 4, borderRadius: 2 },
});

function TerminalCard({ terminal, onAsk }: { terminal: TerminalRow; onAsk: (t: TerminalRow) => void }) {
  const color = healthColor(terminal.success_rate_pct);
  const isHealthy = terminal.success_rate_pct >= 90;

  return (
    <TouchableOpacity style={s.card} onPress={() => onAsk(terminal)} activeOpacity={0.75}>
      <View style={s.cardHeader}>
        <View style={s.tidWrap}>
          <MaterialCommunityIcons
            name={isHealthy ? 'credit-card-check-outline' : 'credit-card-remove-outline'}
            size={20}
            color={color}
          />
          <Text style={s.tid}>{terminal.terminal_id}</Text>
        </View>
        <View style={[s.statusDot, { backgroundColor: color + '22' }]}>
          <Text style={[s.statusText, { color }]}>
            {isHealthy ? 'Healthy' : terminal.success_rate_pct >= 70 ? 'Warning' : 'Critical'}
          </Text>
        </View>
      </View>

      <View style={s.statsRow}>
        <View style={s.stat}>
          <Text style={s.statVal}>{terminal.success_rate_pct.toFixed(1)}%</Text>
          <Text style={s.statLbl}>Success Rate</Text>
        </View>
        <View style={s.stat}>
          <Text style={s.statVal}>{terminal.attempts}</Text>
          <Text style={s.statLbl}>Attempts</Text>
        </View>
        <View style={s.stat}>
          <Text style={s.statVal}>{fmtCurrency(terminal.success_gmv)}</Text>
          <Text style={s.statLbl}>GMV</Text>
        </View>
      </View>

      <View style={s.barRow}>
        <HealthBar pct={terminal.success_rate_pct} color={color} />
        <View style={s.chatCue}>
          <MaterialCommunityIcons name="robot-outline" size={14} color={Colors.primary} />
        </View>
      </View>
    </TouchableOpacity>
  );
}

export default function TerminalsScreen() {
  const { merchantId } = useMerchant();
  const [terminals, setTerminals] = useState<TerminalRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chatVisible, setChatVisible] = useState(false);
  const [selectedTerminal, setSelectedTerminal] = useState<TerminalRow | null>(null);

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    setError(null);
    try {
      const rows = await api.getTerminalPerformance(merchantId, 30);
      setTerminals(rows);
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load terminals');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [merchantId]);

  useEffect(() => { if (merchantId) load(); }, [load, merchantId]);

  const onRefresh = () => { setRefreshing(true); load(true); };

  const openChat = (t: TerminalRow) => {
    setSelectedTerminal(t);
    setChatVisible(true);
  };

  const avgSuccessRate = terminals.length
    ? terminals.reduce((sum, t) => sum + t.success_rate_pct, 0) / terminals.length
    : 0;
  const criticalCount = terminals.filter(t => t.success_rate_pct < 70).length;

  return (
    <SafeAreaView style={s.safeArea} edges={['top']}>
      <View style={s.header}>
        <Text style={s.headerTitle}>Terminals</Text>
        {!loading && !error && (
          <Text style={s.headerSub}>{terminals.length} device{terminals.length !== 1 ? 's' : ''}</Text>
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
        <ScrollView
          contentContainerStyle={s.scrollContent}
          showsVerticalScrollIndicator={false}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.primary} />}
        >
          {/* Summary */}
          <View style={s.summaryCard}>
            <View style={s.summaryRow}>
              <View style={s.summaryItem}>
                <Text style={s.summaryVal}>{terminals.length}</Text>
                <Text style={s.summaryLbl}>TOTAL</Text>
              </View>
              <View style={s.divider} />
              <View style={s.summaryItem}>
                <Text style={[s.summaryVal, { color: Colors.success }]}>
                  {terminals.filter(t => t.success_rate_pct >= 90).length}
                </Text>
                <Text style={s.summaryLbl}>HEALTHY</Text>
              </View>
              <View style={s.divider} />
              <View style={s.summaryItem}>
                <Text style={[s.summaryVal, { color: criticalCount > 0 ? Colors.danger : Colors.textLight }]}>
                  {criticalCount}
                </Text>
                <Text style={s.summaryLbl}>CRITICAL</Text>
              </View>
              <View style={s.divider} />
              <View style={s.summaryItem}>
                <Text style={s.summaryVal}>{avgSuccessRate.toFixed(1)}%</Text>
                <Text style={s.summaryLbl}>AVG RATE</Text>
              </View>
            </View>
          </View>

          <View style={s.hintRow}>
            <MaterialCommunityIcons name="gesture-tap" size={13} color={Colors.textMuted} />
            <Text style={s.hintText}>Tap any terminal to ask DUX IQ about it</Text>
          </View>

          {terminals.length === 0 ? (
            <View style={s.empty}>
              <MaterialCommunityIcons name="credit-card-off-outline" size={44} color={Colors.textLight} />
              <Text style={s.emptyText}>No terminal data in last 30 days</Text>
            </View>
          ) : (
            terminals.map(t => (
              <TerminalCard key={t.terminal_id} terminal={t} onAsk={openChat} />
            ))
          )}
          <View style={{ height: 24 }} />
        </ScrollView>
      )}

      <DuxIQChat
        visible={chatVisible}
        onClose={() => { setChatVisible(false); setSelectedTerminal(null); }}
        merchantId={merchantId}
        initialPrompt={
          selectedTerminal
            ? `Analyze terminal ${selectedTerminal.terminal_id} — ${selectedTerminal.success_rate_pct.toFixed(1)}% success rate, ${selectedTerminal.attempts} attempts, ${fmtCurrency(selectedTerminal.success_gmv)} GMV. What issues should I know about?`
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
  headerSub: { fontSize: 13, color: Colors.textMuted, fontWeight: '600' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 },
  errorText: { fontSize: 14, color: Colors.textMuted, textAlign: 'center', paddingHorizontal: 32 },
  retryBtn: { paddingHorizontal: 24, paddingVertical: 10, backgroundColor: Colors.primary, borderRadius: 12 },
  retryText: { color: Colors.white, fontWeight: '700', fontSize: 14 },
  scrollContent: { padding: 16 },
  summaryCard: {
    backgroundColor: Colors.darkCardBg, borderRadius: 20, padding: 20, marginBottom: 16,
  },
  summaryRow: { flexDirection: 'row', alignItems: 'center' },
  summaryItem: { flex: 1, alignItems: 'center' },
  summaryVal: { fontSize: 22, fontWeight: '900', color: Colors.white },
  summaryLbl: { fontSize: 9, fontWeight: '700', color: '#A8A29E', marginTop: 3, letterSpacing: 0.5 },
  divider: { width: 1, height: 36, backgroundColor: 'rgba(255,255,255,0.1)' },
  hintRow: {
    flexDirection: 'row', alignItems: 'center', gap: 5, marginBottom: 12, paddingHorizontal: 2,
  },
  hintText: { fontSize: 12, color: Colors.textMuted, fontStyle: 'italic' },
  empty: { alignItems: 'center', paddingTop: 60, gap: 12 },
  emptyText: { fontSize: 15, color: Colors.textMuted, fontWeight: '600' },
  card: {
    backgroundColor: Colors.white, borderRadius: 16,
    padding: 16, marginBottom: 12,
    borderWidth: 1, borderColor: Colors.border,
  },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 },
  tidWrap: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  tid: { fontSize: 16, fontWeight: '800', color: Colors.textMain },
  statusDot: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20 },
  statusText: { fontSize: 11, fontWeight: '700' },
  statsRow: { flexDirection: 'row', marginBottom: 14, gap: 4 },
  stat: { flex: 1, alignItems: 'center', backgroundColor: Colors.background, borderRadius: 10, paddingVertical: 8 },
  statVal: { fontSize: 15, fontWeight: '800', color: Colors.textMain },
  statLbl: { fontSize: 9, fontWeight: '700', color: Colors.textMuted, marginTop: 2 },
  barRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  chatCue: {
    width: 26, height: 26, borderRadius: 13,
    backgroundColor: '#FFF1E6', alignItems: 'center', justifyContent: 'center',
  },
});
