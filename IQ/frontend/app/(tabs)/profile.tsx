import React, { useEffect, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, ActivityIndicator, TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { Colors } from '../../src/constants/colors';
import { api, Snapshot } from '../../src/services/api';
import { useMerchant } from '../../src/context/MerchantContext';

export default function ProfileScreen() {
  const router = useRouter();
  const { merchantId, merchantName, setMerchant } = useMerchant();
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!merchantId) return;
    api.getSnapshot(merchantId)
      .then(setSnapshot)
      .catch(e => setError(e?.message ?? 'Failed to load profile'))
      .finally(() => setLoading(false));
  }, [merchantId]);

  const profile = snapshot?.merchant_profile?.merchant;
  const summary = snapshot?.summary;

  const initials = (profile?.merchant_trade_name ?? merchantName)
    .split(' ')
    .slice(0, 2)
    .map(w => w[0]?.toUpperCase() ?? '')
    .join('');

  const profileItems = profile ? [
    { icon: 'store', label: 'Business Name', value: profile.merchant_trade_name },
    { icon: 'identifier', label: 'Merchant ID', value: profile.mid },
    { icon: 'briefcase-outline', label: 'Business Type', value: profile.nature_of_business ?? '—' },
    { icon: 'map-marker-outline', label: 'City', value: profile.business_city ?? '—' },
  ] : [];

  const statItems = summary ? [
    { icon: 'check-circle-outline', label: 'Success Transactions', value: String(summary.success_txns) },
    { icon: 'close-circle-outline', label: 'Failed Transactions', value: String(summary.fail_txns) },
    { icon: 'percent', label: 'Success Rate', value: `${summary.success_rate_pct?.toFixed(1)}%` },
    { icon: 'credit-card-settings-outline', label: 'Active Terminals', value: String(summary.terminal_count) },
    { icon: 'alert-circle-outline', label: 'Open Chargebacks', value: String(summary.open_chargebacks) },
  ] : [];

  return (
    <SafeAreaView style={s.safeArea} edges={['top']}>
      <View style={s.header}>
        <Text style={s.headerTitle}>Profile</Text>
        <TouchableOpacity
          style={s.switchBtn}
          onPress={() => {
            setMerchant('', '', '');
            router.replace('/login');
          }}
        >
          <MaterialCommunityIcons name="swap-horizontal" size={18} color={Colors.primary} />
          <Text style={s.switchText}>Switch</Text>
        </TouchableOpacity>
      </View>

      {loading ? (
        <View style={s.center}>
          <ActivityIndicator size="large" color={Colors.primary} />
        </View>
      ) : error ? (
        <View style={s.center}>
          <Text style={s.errorText}>{error}</Text>
        </View>
      ) : (
        <ScrollView style={s.list} contentContainerStyle={s.listContent} showsVerticalScrollIndicator={false}>
          {/* Avatar Card */}
          <View style={s.avatarCard}>
            <View style={s.avatarCircle}>
              <Text style={s.avatarText}>{initials}</Text>
            </View>
            <Text style={s.avatarName}>{profile?.merchant_trade_name ?? merchantName}</Text>
            <Text style={s.avatarSub}>MID: {profile?.mid ?? merchantId}</Text>
          </View>

          {/* Profile Details */}
          {profileItems.length > 0 && (
            <Text style={s.sectionLabel}>MERCHANT DETAILS</Text>
          )}
          {profileItems.map((item, i) => (
            <View key={i} style={s.itemRow} testID={`profile-item-${i}`}>
              <View style={s.itemIconWrap}>
                <MaterialCommunityIcons name={item.icon as any} size={20} color={Colors.primary} />
              </View>
              <View style={s.itemContent}>
                <Text style={s.itemLabel}>{item.label}</Text>
                <Text style={s.itemValue}>{item.value}</Text>
              </View>
            </View>
          ))}

          {/* Stats */}
          {statItems.length > 0 && (
            <Text style={[s.sectionLabel, { marginTop: 20 }]}>PERFORMANCE SUMMARY</Text>
          )}
          {statItems.map((item, i) => (
            <View key={i} style={s.itemRow}>
              <View style={s.itemIconWrap}>
                <MaterialCommunityIcons name={item.icon as any} size={20} color={Colors.primary} />
              </View>
              <View style={s.itemContent}>
                <Text style={s.itemLabel}>{item.label}</Text>
                <Text style={s.itemValue}>{item.value}</Text>
              </View>
            </View>
          ))}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: Colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 16,
    backgroundColor: Colors.white,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  headerTitle: { fontSize: 22, fontWeight: '800', color: Colors.textMain },
  switchBtn: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  switchText: { fontSize: 13, fontWeight: '700', color: Colors.primary },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 },
  errorText: { fontSize: 14, color: Colors.textMuted, textAlign: 'center', paddingHorizontal: 32 },
  list: { flex: 1 },
  listContent: { padding: 16, paddingBottom: 30 },
  sectionLabel: {
    fontSize: 11, fontWeight: '700', color: Colors.textMuted,
    letterSpacing: 0.8, marginBottom: 10, paddingHorizontal: 2,
  },
  avatarCard: {
    backgroundColor: Colors.white, borderRadius: 20, padding: 24,
    alignItems: 'center', marginBottom: 20, borderWidth: 1, borderColor: Colors.border,
  },
  avatarCircle: {
    width: 72, height: 72, borderRadius: 36,
    backgroundColor: '#FFF1E6', alignItems: 'center',
    justifyContent: 'center', marginBottom: 12,
  },
  avatarText: { fontSize: 26, fontWeight: '900', color: Colors.primary },
  avatarName: { fontSize: 20, fontWeight: '800', color: Colors.textMain },
  avatarSub: { fontSize: 13, color: Colors.textMuted, marginTop: 4 },
  itemRow: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: Colors.white, borderRadius: 14,
    padding: 16, marginBottom: 10, borderWidth: 1, borderColor: Colors.border,
  },
  itemIconWrap: {
    width: 40, height: 40, borderRadius: 12,
    backgroundColor: '#FFF1E6', alignItems: 'center',
    justifyContent: 'center', marginRight: 14,
  },
  itemContent: { flex: 1 },
  itemLabel: { fontSize: 11, fontWeight: '600', color: Colors.textMuted, letterSpacing: 0.3 },
  itemValue: { fontSize: 15, fontWeight: '700', color: Colors.textMain, marginTop: 2 },
});
