import React, { useState, useCallback, useEffect } from 'react';
import {
  View, Text, TouchableOpacity, ScrollView, StyleSheet, Modal,
  ActivityIndicator, RefreshControl, Alert, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
// Lazy-load to avoid native module crash if not linked (e.g. older Expo Go)
let ImagePicker: typeof import('expo-image-picker') | null = null;
try { ImagePicker = require('expo-image-picker'); } catch { ImagePicker = null; }
import { Colors } from '../../src/constants/colors';
import { api, ChargebackRow, ChargebackSummary, RefundRow } from '../../src/services/api';
import { useMerchant } from '../../src/context/MerchantContext';
import DuxIQChat from '../../src/components/DuxIQChat';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtCurrency(n: number | string | null) {
  if (n == null) return '—';
  return '₹' + Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

function fmtDate(d: string | null) {
  if (!d) return '—';
  try {
    return new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch { return d; }
}

function daysUntil(due: string | null): number | null {
  if (!due) return null;
  const diff = new Date(due).getTime() - Date.now();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

function urgencyConfig(cb: ChargebackRow) {
  const status = (cb.status || '').toUpperCase();
  if (['CLOSED', 'RESOLVED'].includes(status)) {
    return { color: Colors.success, bg: Colors.successLight, icon: 'check-circle', label: 'Resolved' };
  }
  const days = daysUntil(cb.due_by);
  if (days !== null && days < 0) {
    return { color: Colors.danger, bg: Colors.dangerLight, icon: 'alert-circle', label: 'Overdue' };
  }
  if (days !== null && days <= 3) {
    return { color: Colors.warning, bg: Colors.warningLight, icon: 'clock-alert', label: `Due in ${days}d` };
  }
  return { color: '#3B82F6', bg: '#EFF6FF', icon: 'clock-outline', label: days !== null ? `Due in ${days}d` : 'Open' };
}

type FilterTab = 'all' | 'open' | 'overdue' | 'resolved';

// ---------------------------------------------------------------------------
// Evidence Upload Sheet
// ---------------------------------------------------------------------------

interface EvidenceSheetProps {
  chargeback: ChargebackRow;
  merchantId: string;
  onClose: () => void;
  onSuccess: (evidenceId: string) => void;
}

function EvidenceSheet({ chargeback, merchantId, onClose, onSuccess }: EvidenceSheetProps) {
  const [uploading, setUploading] = useState(false);
  const [extracted, setExtracted] = useState<Record<string, string> | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const pickAndUpload = async (useCamera: boolean) => {
    if (!ImagePicker) {
      Alert.alert('Not available', 'Image picker is not available on this build. Please update your Expo Go app or use a development build.');
      return;
    }
    try {
      let result;
      if (useCamera) {
        const { status } = await ImagePicker.requestCameraPermissionsAsync();
        if (status !== 'granted') {
          Alert.alert('Permission required', 'Camera access is needed to capture receipts.');
          return;
        }
        result = await ImagePicker.launchCameraAsync({
          mediaTypes: ImagePicker.MediaTypeOptions.Images,
          quality: 0.85,
          allowsEditing: false,
        });
      } else {
        result = await ImagePicker.launchImageLibraryAsync({
          mediaTypes: ImagePicker.MediaTypeOptions.Images,
          quality: 0.85,
          allowsEditing: false,
        });
      }

      if (result.canceled || !result.assets?.[0]) return;
      const asset = result.assets[0];

      setUploading(true);
      setUploadError(null);
      setExtracted(null);

      const ext = asset.uri.split('.').pop() ?? 'jpg';
      const mime = ext === 'png' ? 'image/png' : 'image/jpeg';

      const response = await api.uploadDisputeEvidence({
        fileUri: asset.uri,
        fileName: `receipt_${chargeback.chargeback_id}.${ext}`,
        mimeType: mime,
        merchantId,
        chargebackId: chargeback.chargeback_id,
      });

      if (response.ok) {
        setExtracted(response.extracted as Record<string, string>);
        onSuccess(response.evidence_id);
      } else {
        setUploadError(response.error ?? 'Upload failed');
      }
    } catch (e: any) {
      setUploadError(e?.message ?? 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const days = daysUntil(chargeback.due_by);
  const isOverdue = days !== null && days < 0;

  return (
    <Modal visible animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <SafeAreaView style={ev.safe} edges={['top', 'bottom']}>
        {/* Header */}
        <View style={ev.header}>
          <TouchableOpacity onPress={onClose} style={ev.closeBtn}>
            <MaterialCommunityIcons name="close" size={22} color={Colors.textMain} />
          </TouchableOpacity>
          <Text style={ev.headerTitle}>Submit Evidence</Text>
          <View style={{ width: 40 }} />
        </View>

        <ScrollView contentContainerStyle={ev.body} showsVerticalScrollIndicator={false}>
          {/* Chargeback context */}
          <View style={[ev.contextCard, isOverdue && ev.contextCardOverdue]}>
            <View style={ev.contextRow}>
              <MaterialCommunityIcons
                name={isOverdue ? 'alert-circle' : 'file-document-outline'}
                size={20}
                color={isOverdue ? Colors.danger : Colors.primary}
              />
              <Text style={ev.contextId}>Chargeback #{chargeback.chargeback_id}</Text>
            </View>
            <Text style={ev.contextAmount}>{fmtCurrency(chargeback.amount_rupees)}</Text>
            {chargeback.reason_code && (
              <Text style={ev.contextReason}>Reason: {chargeback.reason_code}</Text>
            )}
            {chargeback.due_by && (
              <View style={[ev.duePill, isOverdue && ev.duePillOverdue]}>
                <MaterialCommunityIcons
                  name={isOverdue ? 'clock-remove' : 'clock-outline'}
                  size={13}
                  color={isOverdue ? Colors.danger : Colors.warning}
                />
                <Text style={[ev.dueText, isOverdue && { color: Colors.danger }]}>
                  {isOverdue ? `Overdue by ${Math.abs(days!)} day${Math.abs(days!) !== 1 ? 's' : ''}` : `Due: ${fmtDate(chargeback.due_by)}`}
                </Text>
              </View>
            )}
          </View>

          {/* What merchants need to submit */}
          <Text style={ev.sectionLabel}>WHAT TO SUBMIT</Text>
          <View style={ev.guideCard}>
            {[
              { icon: 'receipt', text: 'Original payment receipt / transaction slip' },
              { icon: 'bank-transfer', text: 'Bank / POS authorization confirmation' },
              { icon: 'truck-delivery-outline', text: 'Proof of delivery or service rendered' },
              { icon: 'account-check-outline', text: 'Customer ID / signature if applicable' },
              { icon: 'email-check-outline', text: 'Communication records with the cardholder' },
            ].map((item, i) => (
              <View key={i} style={ev.guideRow}>
                <MaterialCommunityIcons name={item.icon as any} size={16} color={Colors.primary} />
                <Text style={ev.guideText}>{item.text}</Text>
              </View>
            ))}
          </View>

          {/* Upload options */}
          {!extracted && !uploading && (
            <>
              <Text style={ev.sectionLabel}>UPLOAD RECEIPT / PROOF</Text>
              <TouchableOpacity style={ev.uploadBtn} onPress={() => pickAndUpload(true)}>
                <MaterialCommunityIcons name="camera-outline" size={22} color={Colors.white} />
                <Text style={ev.uploadBtnText}>Take Photo</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[ev.uploadBtn, ev.uploadBtnOutline]} onPress={() => pickAndUpload(false)}>
                <MaterialCommunityIcons name="image-outline" size={22} color={Colors.primary} />
                <Text style={[ev.uploadBtnText, { color: Colors.primary }]}>Choose from Gallery</Text>
              </TouchableOpacity>
            </>
          )}

          {/* Uploading spinner */}
          {uploading && (
            <View style={ev.uploadingWrap}>
              <ActivityIndicator size="large" color={Colors.primary} />
              <Text style={ev.uploadingText}>Extracting evidence data…</Text>
            </View>
          )}

          {/* Upload error */}
          {uploadError && (
            <View style={ev.errorBox}>
              <MaterialCommunityIcons name="alert-circle-outline" size={18} color={Colors.danger} />
              <Text style={ev.errorText}>{uploadError}</Text>
              <TouchableOpacity onPress={() => setUploadError(null)}>
                <Text style={ev.retryLink}>Try again</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* Extracted data preview */}
          {extracted && (
            <View style={ev.successCard}>
              <View style={ev.successHeader}>
                <MaterialCommunityIcons name="check-circle" size={22} color={Colors.success} />
                <Text style={ev.successTitle}>Evidence Submitted</Text>
              </View>
              <Text style={ev.successSub}>The following data was extracted from your receipt:</Text>
              {Object.entries(extracted)
                .filter(([, v]) => v && v !== 'null')
                .map(([k, v]) => (
                  <View key={k} style={ev.extractedRow}>
                    <Text style={ev.extractedKey}>{k.replace(/_/g, ' ').toUpperCase()}</Text>
                    <Text style={ev.extractedVal}>{String(v)}</Text>
                  </View>
                ))}
              <TouchableOpacity style={ev.uploadAnotherBtn} onPress={() => setExtracted(null)}>
                <Text style={ev.uploadAnotherText}>Submit Another Document</Text>
              </TouchableOpacity>
            </View>
          )}
        </ScrollView>
      </SafeAreaView>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Chargeback card
// ---------------------------------------------------------------------------

function ChargebackCard({
  cb, onUploadEvidence, onAskIQ,
}: {
  cb: ChargebackRow;
  onUploadEvidence: (cb: ChargebackRow) => void;
  onAskIQ: (cb: ChargebackRow) => void;
}) {
  const cfg = urgencyConfig(cb);
  const isResolved = ['CLOSED', 'RESOLVED'].includes((cb.status || '').toUpperCase());

  return (
    <View style={s.cbCard}>
      <View style={s.cbTop}>
        <View style={s.cbLeft}>
          <View style={[s.cbIconWrap, { backgroundColor: cfg.bg }]}>
            <MaterialCommunityIcons name={cfg.icon as any} size={20} color={cfg.color} />
          </View>
          <View>
            <Text style={s.cbId}>#{cb.chargeback_id}</Text>
            <Text style={s.cbDate}>{fmtDate(cb.opened_at)}</Text>
          </View>
        </View>
        <View style={s.cbRight}>
          <Text style={s.cbAmount}>{fmtCurrency(cb.amount_rupees)}</Text>
          <View style={[s.statusPill, { backgroundColor: cfg.bg }]}>
            <Text style={[s.statusPillText, { color: cfg.color }]}>{cfg.label}</Text>
          </View>
        </View>
      </View>

      {cb.reason_code && (
        <View style={s.reasonRow}>
          <MaterialCommunityIcons name="tag-outline" size={13} color={Colors.textMuted} />
          <Text style={s.reasonText}>Reason Code: {cb.reason_code}</Text>
        </View>
      )}

      {!isResolved && (
        <View style={s.cbActions}>
          <TouchableOpacity style={s.actionBtnOutline} onPress={() => onAskIQ(cb)}>
            <MaterialCommunityIcons name="robot-outline" size={15} color={Colors.primary} />
            <Text style={s.actionBtnOutlineText}>Ask DUX IQ</Text>
          </TouchableOpacity>
          <TouchableOpacity style={s.actionBtnFilled} onPress={() => onUploadEvidence(cb)}>
            <MaterialCommunityIcons name="upload-outline" size={15} color={Colors.white} />
            <Text style={s.actionBtnFilledText}>Submit Evidence</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Screen
// ---------------------------------------------------------------------------

export default function DisputesScreen() {
  const { merchantId } = useMerchant();
  const [chargebacks, setChargebacks] = useState<ChargebackRow[]>([]);
  const [refunds, setRefunds] = useState<RefundRow[]>([]);
  const [summary, setSummary] = useState<ChargebackSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<FilterTab>('open');
  const [evidenceCb, setEvidenceCb] = useState<ChargebackRow | null>(null);
  const [submittedIds, setSubmittedIds] = useState<Set<string>>(new Set());
  const [chatVisible, setChatVisible] = useState(false);
  const [chatCb, setChatCb] = useState<ChargebackRow | null>(null);

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    setError(null);
    try {
      const data = await api.getChargebacks(merchantId, 90);
      setChargebacks(data.chargebacks?.rows ?? []);
      setSummary(data.summary ?? null);
      setRefunds(data.refunds?.rows ?? []);
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load disputes');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [merchantId]);

  useEffect(() => { if (merchantId) load(); }, [load, merchantId]);

  const onRefresh = () => { setRefreshing(true); load(true); };

  const filtered = chargebacks.filter(cb => {
    const status = (cb.status || '').toUpperCase();
    const days = daysUntil(cb.due_by);
    if (activeTab === 'resolved') return ['CLOSED', 'RESOLVED'].includes(status);
    if (activeTab === 'overdue') return !['CLOSED', 'RESOLVED'].includes(status) && days !== null && days < 0;
    if (activeTab === 'open') return !['CLOSED', 'RESOLVED'].includes(status);
    return true;
  });

  const TABS: { key: FilterTab; label: string; count?: number }[] = [
    { key: 'open', label: 'Open', count: summary?.open_chargebacks_count },
    { key: 'overdue', label: 'Overdue', count: summary?.overdue_chargebacks_count },
    { key: 'resolved', label: 'Resolved' },
    { key: 'all', label: 'All', count: summary?.chargebacks_count },
  ];

  return (
    <SafeAreaView style={s.safeArea} edges={['top']}>
      <View style={s.header}>
        <Text style={s.headerTitle}>Disputes</Text>
        {(summary?.overdue_chargebacks_count ?? 0) > 0 && (
          <View style={s.alertBadge}>
            <MaterialCommunityIcons name="alert" size={13} color={Colors.white} />
            <Text style={s.alertBadgeText}>{summary!.overdue_chargebacks_count} overdue</Text>
          </View>
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
          {/* Summary strip */}
          {summary && (
            <View style={s.summaryStrip}>
              <View style={s.stripItem}>
                <Text style={[s.stripVal, { color: Colors.danger }]}>{summary.open_chargebacks_count}</Text>
                <Text style={s.stripLbl}>Open</Text>
              </View>
              <View style={s.stripDivider} />
              <View style={s.stripItem}>
                <Text style={[s.stripVal, summary.overdue_chargebacks_count > 0 && { color: Colors.danger }]}>
                  {summary.overdue_chargebacks_count}
                </Text>
                <Text style={s.stripLbl}>Overdue</Text>
              </View>
              <View style={s.stripDivider} />
              <View style={s.stripItem}>
                <Text style={s.stripVal}>{fmtCurrency(summary.chargebacks_amount)}</Text>
                <Text style={s.stripLbl}>Exposure</Text>
              </View>
              <View style={s.stripDivider} />
              <View style={s.stripItem}>
                <Text style={s.stripVal}>{refunds.length}</Text>
                <Text style={s.stripLbl}>Refunds</Text>
              </View>
            </View>
          )}

          {/* Top reason banner */}
          {summary?.top_reason && (
            <View style={s.reasonBanner}>
              <MaterialCommunityIcons name="information-outline" size={14} color={Colors.warning} />
              <Text style={s.reasonBannerText}>
                Most common reason: <Text style={{ fontWeight: '800' }}>{summary.top_reason.reason_code}</Text>
                {' '}({summary.top_reason.count} cases)
              </Text>
            </View>
          )}

          {/* Filter tabs */}
          <ScrollView
            horizontal showsHorizontalScrollIndicator={false}
            style={s.tabScroll} contentContainerStyle={s.tabContent}
          >
            {TABS.map(tab => (
              <TouchableOpacity
                key={tab.key}
                style={[s.tab, activeTab === tab.key && s.tabActive]}
                onPress={() => setActiveTab(tab.key)}
              >
                <Text style={[s.tabText, activeTab === tab.key && s.tabTextActive]}>
                  {tab.label}{tab.count != null ? ` (${tab.count})` : ''}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          <ScrollView
            contentContainerStyle={s.listContent}
            showsVerticalScrollIndicator={false}
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.primary} />}
          >
            {filtered.length === 0 ? (
              <View style={s.empty}>
                <MaterialCommunityIcons name="check-circle-outline" size={44} color={Colors.textLight} />
                <Text style={s.emptyText}>No disputes in this category</Text>
              </View>
            ) : (
              filtered.map(cb => (
                <ChargebackCard
                  key={String(cb.chargeback_id)}
                  cb={cb}
                  onUploadEvidence={setEvidenceCb}
                  onAskIQ={cb => { setChatCb(cb); setChatVisible(true); }}
                />
              ))
            )}

            {/* Refunds section */}
            {activeTab === 'all' && refunds.length > 0 && (
              <>
                <Text style={s.refundSectionLabel}>RECENT REFUNDS</Text>
                {refunds.map((r, i) => (
                  <View key={i} style={s.refundCard}>
                    <View style={s.refundLeft}>
                      <MaterialCommunityIcons name="cash-refund" size={18} color={Colors.textMuted} />
                      <View>
                        <Text style={s.refundId}>{r.refund_id ? `#${r.refund_id}` : 'Refund'}</Text>
                        <Text style={s.refundDate}>{fmtDate(r.created_at)}</Text>
                      </View>
                    </View>
                    <Text style={s.refundAmount}>{fmtCurrency(r.amount_rupees)}</Text>
                  </View>
                ))}
              </>
            )}
            <View style={{ height: 24 }} />
          </ScrollView>
        </>
      )}

      {/* Evidence upload sheet */}
      {evidenceCb && (
        <EvidenceSheet
          chargeback={evidenceCb}
          merchantId={merchantId}
          onClose={() => setEvidenceCb(null)}
          onSuccess={id => {
            setSubmittedIds(prev => new Set([...prev, String(evidenceCb.chargeback_id)]));
          }}
        />
      )}

      {/* DUX IQ chat */}
      <DuxIQChat
        visible={chatVisible}
        onClose={() => { setChatVisible(false); setChatCb(null); }}
        merchantId={merchantId}
        initialPrompt={
          chatCb
            ? `Tell me about chargeback #${chatCb.chargeback_id} — ${fmtCurrency(chatCb.amount_rupees)}, reason ${chatCb.reason_code ?? 'unknown'}. What steps should I take to respond?`
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
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 16,
    backgroundColor: Colors.white, borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  headerTitle: { fontSize: 22, fontWeight: '800', color: Colors.textMain },
  alertBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: Colors.danger, borderRadius: 20, paddingHorizontal: 10, paddingVertical: 4,
  },
  alertBadgeText: { fontSize: 11, fontWeight: '800', color: Colors.white },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 },
  errorText: { fontSize: 14, color: Colors.textMuted, textAlign: 'center', paddingHorizontal: 32 },
  retryBtn: { paddingHorizontal: 24, paddingVertical: 10, backgroundColor: Colors.primary, borderRadius: 12 },
  retryText: { color: Colors.white, fontWeight: '700', fontSize: 14 },
  summaryStrip: {
    flexDirection: 'row', backgroundColor: Colors.white,
    paddingVertical: 14, paddingHorizontal: 8,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  stripItem: { flex: 1, alignItems: 'center' },
  stripVal: { fontSize: 18, fontWeight: '900', color: Colors.textMain },
  stripLbl: { fontSize: 9, fontWeight: '700', color: Colors.textMuted, marginTop: 2 },
  stripDivider: { width: 1, backgroundColor: Colors.border },
  reasonBanner: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: Colors.warningLight, paddingHorizontal: 16, paddingVertical: 8,
  },
  reasonBannerText: { fontSize: 12, color: Colors.textMain, flex: 1 },
  tabScroll: { maxHeight: 48, backgroundColor: Colors.white },
  tabContent: { paddingHorizontal: 16, gap: 8, alignItems: 'center', paddingVertical: 8 },
  tab: {
    backgroundColor: Colors.background, borderRadius: 20,
    paddingHorizontal: 16, paddingVertical: 6,
    borderWidth: 1, borderColor: Colors.border,
  },
  tabActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  tabText: { fontSize: 13, fontWeight: '600', color: Colors.textMuted },
  tabTextActive: { color: Colors.white },
  listContent: { padding: 16 },
  cbCard: {
    backgroundColor: Colors.white, borderRadius: 16,
    padding: 14, marginBottom: 12,
    borderWidth: 1, borderColor: Colors.border,
  },
  cbTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  cbLeft: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  cbIconWrap: { width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center' },
  cbId: { fontSize: 15, fontWeight: '800', color: Colors.textMain },
  cbDate: { fontSize: 11, color: Colors.textMuted, marginTop: 1 },
  cbRight: { alignItems: 'flex-end' },
  cbAmount: { fontSize: 16, fontWeight: '900', color: Colors.textMain },
  statusPill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10, marginTop: 4 },
  statusPillText: { fontSize: 10, fontWeight: '800' },
  reasonRow: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 8 },
  reasonText: { fontSize: 12, color: Colors.textMuted },
  cbActions: { flexDirection: 'row', gap: 10, marginTop: 12 },
  actionBtnOutline: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    borderWidth: 1, borderColor: Colors.primary, borderRadius: 12, paddingVertical: 10,
  },
  actionBtnOutlineText: { fontSize: 13, fontWeight: '700', color: Colors.primary },
  actionBtnFilled: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    backgroundColor: Colors.primary, borderRadius: 12, paddingVertical: 10,
  },
  actionBtnFilledText: { fontSize: 13, fontWeight: '700', color: Colors.white },
  refundSectionLabel: {
    fontSize: 11, fontWeight: '700', color: Colors.textMuted,
    letterSpacing: 0.8, marginTop: 12, marginBottom: 10, paddingHorizontal: 2,
  },
  refundCard: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: Colors.white, borderRadius: 14, padding: 14, marginBottom: 8,
    borderWidth: 1, borderColor: Colors.border,
  },
  refundLeft: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  refundId: { fontSize: 14, fontWeight: '700', color: Colors.textMain },
  refundDate: { fontSize: 11, color: Colors.textMuted, marginTop: 1 },
  refundAmount: { fontSize: 15, fontWeight: '800', color: Colors.textMain },
  empty: { alignItems: 'center', paddingTop: 60, gap: 12 },
  emptyText: { fontSize: 15, color: Colors.textMuted, fontWeight: '600' },
});

// Evidence sheet styles
const ev = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.background },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 14,
    backgroundColor: Colors.white, borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  closeBtn: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { fontSize: 17, fontWeight: '800', color: Colors.textMain },
  body: { padding: 20, paddingBottom: 40 },
  contextCard: {
    backgroundColor: Colors.white, borderRadius: 16, padding: 16, marginBottom: 20,
    borderWidth: 1, borderColor: Colors.border,
  },
  contextCardOverdue: { borderColor: Colors.danger, borderWidth: 1.5 },
  contextRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  contextId: { fontSize: 16, fontWeight: '800', color: Colors.textMain },
  contextAmount: { fontSize: 26, fontWeight: '900', color: Colors.textMain, marginBottom: 4 },
  contextReason: { fontSize: 12, color: Colors.textMuted, marginBottom: 8 },
  duePill: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    backgroundColor: Colors.warningLight, borderRadius: 10,
    paddingHorizontal: 10, paddingVertical: 5, alignSelf: 'flex-start',
  },
  duePillOverdue: { backgroundColor: Colors.dangerLight },
  dueText: { fontSize: 12, fontWeight: '700', color: Colors.warning },
  sectionLabel: {
    fontSize: 11, fontWeight: '700', color: Colors.textMuted,
    letterSpacing: 0.8, marginBottom: 10, paddingHorizontal: 2,
  },
  guideCard: {
    backgroundColor: Colors.white, borderRadius: 14, padding: 16, marginBottom: 24,
    borderWidth: 1, borderColor: Colors.border, gap: 12,
  },
  guideRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  guideText: { fontSize: 13, color: Colors.textMain, flex: 1, lineHeight: 18 },
  uploadBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10,
    backgroundColor: Colors.primary, borderRadius: 14,
    paddingVertical: 16, marginBottom: 12,
  },
  uploadBtnOutline: {
    backgroundColor: Colors.white, borderWidth: 1.5, borderColor: Colors.primary,
  },
  uploadBtnText: { fontSize: 15, fontWeight: '700', color: Colors.white },
  uploadingWrap: { alignItems: 'center', paddingVertical: 32, gap: 14 },
  uploadingText: { fontSize: 14, color: Colors.textMuted },
  errorBox: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: Colors.dangerLight, borderRadius: 12, padding: 14, marginTop: 8,
  },
  errorText: { flex: 1, fontSize: 13, color: Colors.danger },
  retryLink: { fontSize: 13, fontWeight: '700', color: Colors.primary },
  successCard: {
    backgroundColor: Colors.white, borderRadius: 16, padding: 16,
    borderWidth: 1, borderColor: Colors.success,
  },
  successHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  successTitle: { fontSize: 16, fontWeight: '800', color: Colors.success },
  successSub: { fontSize: 13, color: Colors.textMuted, marginBottom: 14 },
  extractedRow: {
    flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  extractedKey: { fontSize: 10, fontWeight: '700', color: Colors.textMuted },
  extractedVal: { fontSize: 13, fontWeight: '700', color: Colors.textMain, maxWidth: '60%', textAlign: 'right' },
  uploadAnotherBtn: { marginTop: 16, alignItems: 'center' },
  uploadAnotherText: { fontSize: 13, fontWeight: '700', color: Colors.primary },
});
