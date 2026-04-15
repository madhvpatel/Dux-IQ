import React, { useEffect, useState } from 'react';
import {
  View, Text, TouchableOpacity, ScrollView, StyleSheet,
  ActivityIndicator, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { Colors } from '../src/constants/colors';
import { api, MerchantOption } from '../src/services/api';
import { useMerchant } from '../src/context/MerchantContext';

export default function LoginScreen() {
  const router = useRouter();
  const { setMerchant } = useMerchant();
  const [merchants, setMerchants] = useState<MerchantOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selecting, setSelecting] = useState<string | null>(null);

  useEffect(() => {
    api.getMerchants()
      .then(data => setMerchants(data.merchants))
      .catch(e => setError(e?.message ?? 'Could not load merchants'))
      .finally(() => setLoading(false));
  }, []);

  const select = async (m: MerchantOption) => {
    setSelecting(m.merchant_id);
    setMerchant(m.merchant_id, m.merchant_trade_name, m.merchant_id);
    router.replace('/(tabs)');
  };

  return (
    <SafeAreaView style={s.safe} edges={['top', 'bottom']}>
      <View style={s.topBar}>
        <Text style={s.brand}>
          <Text style={s.brandDux}>DUX</Text>
          <Text style={s.brandIq}>{'\u00AE'}IQ</Text>
        </Text>
        <Text style={s.tagline}>Merchant Intelligence Platform</Text>
      </View>

      <View style={s.body}>
        <Text style={s.heading}>Select Merchant</Text>
        <Text style={s.sub}>Choose the merchant account to manage</Text>

        {loading ? (
          <View style={s.center}>
            <ActivityIndicator size="large" color={Colors.primary} />
          </View>
        ) : error ? (
          <View style={s.center}>
            <MaterialCommunityIcons name="wifi-off" size={40} color={Colors.textMuted} />
            <Text style={s.errorText}>{error}</Text>
            <TouchableOpacity
              style={s.retryBtn}
              onPress={() => {
                setLoading(true);
                setError(null);
                api.getMerchants()
                  .then(data => setMerchants(data.merchants))
                  .catch(e => setError(e?.message ?? 'Could not load merchants'))
                  .finally(() => setLoading(false));
              }}
            >
              <Text style={s.retryText}>Retry</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={s.list}>
            {merchants.map(m => {
              const initials = m.merchant_trade_name
                .split(' ')
                .slice(0, 2)
                .map(w => w[0]?.toUpperCase() ?? '')
                .join('');
              const isSelecting = selecting === m.merchant_id;
              return (
                <TouchableOpacity
                  key={m.merchant_id}
                  style={s.card}
                  onPress={() => select(m)}
                  activeOpacity={0.75}
                  disabled={!!selecting}
                >
                  <View style={s.avatar}>
                    <Text style={s.avatarText}>{initials}</Text>
                  </View>
                  <View style={s.cardBody}>
                    <Text style={s.cardName}>{m.merchant_trade_name}</Text>
                    <Text style={s.cardId} numberOfLines={1}>
                      MID: {m.merchant_id}
                    </Text>
                  </View>
                  {isSelecting ? (
                    <ActivityIndicator size="small" color={Colors.primary} />
                  ) : (
                    <MaterialCommunityIcons
                      name="chevron-right"
                      size={22}
                      color={Colors.textLight}
                    />
                  )}
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        )}
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  topBar: {
    alignItems: 'center',
    paddingVertical: 40,
    paddingTop: Platform.OS === 'ios' ? 40 : 48,
  },
  brand: {
    fontSize: 36,
    fontWeight: '900',
  },
  brandDux: {
    color: Colors.textMain,
  },
  brandIq: {
    color: Colors.primary,
  },
  tagline: {
    fontSize: 13,
    color: Colors.textMuted,
    marginTop: 6,
    fontWeight: '600',
    letterSpacing: 0.5,
  },
  body: {
    flex: 1,
    paddingHorizontal: 20,
  },
  heading: {
    fontSize: 22,
    fontWeight: '800',
    color: Colors.textMain,
    marginBottom: 4,
  },
  sub: {
    fontSize: 14,
    color: Colors.textMuted,
    marginBottom: 20,
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    paddingBottom: 60,
  },
  errorText: {
    fontSize: 14,
    color: Colors.textMuted,
    textAlign: 'center',
    paddingHorizontal: 20,
  },
  retryBtn: {
    paddingHorizontal: 24,
    paddingVertical: 10,
    backgroundColor: Colors.primary,
    borderRadius: 12,
  },
  retryText: {
    color: Colors.white,
    fontWeight: '700',
    fontSize: 14,
  },
  list: {
    gap: 12,
    paddingBottom: 30,
  },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.white,
    borderRadius: 18,
    padding: 16,
    borderWidth: 1,
    borderColor: Colors.border,
    gap: 14,
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 14,
    backgroundColor: '#FFF1E6',
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontSize: 18,
    fontWeight: '900',
    color: Colors.primary,
  },
  cardBody: {
    flex: 1,
  },
  cardName: {
    fontSize: 16,
    fontWeight: '800',
    color: Colors.textMain,
  },
  cardId: {
    fontSize: 11,
    color: Colors.textMuted,
    marginTop: 3,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
});
