import React, { useState, useRef, useEffect } from 'react';
import {
  View, Text, TouchableOpacity, Modal, ScrollView,
  StyleSheet, Dimensions, TextInput, KeyboardAvoidingView, Platform,
  ActivityIndicator,
} from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Colors } from '../constants/colors';
import { api, ContextObject, ChatHistoryItem } from '../services/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Settlement {
  id: number;
  amount: number;
  status: string;
  date: string | null;
}

interface Message {
  id: string;
  role: 'bot' | 'user' | 'system';
  content: string;
  msgType: 'text' | 'followups' | 'thinking' | 'resolution' | 'ticket_offer' | 'ticket_created' | 'rating' | 'ended';
  followUps?: string[];
}

interface DuxIQChatProps {
  visible: boolean;
  onClose: () => void;
  merchantId: string;
  settlement?: Settlement;    // if opened from a specific settlement row
  initialPrompt?: string;     // auto-send this prompt when chat opens
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtAmount(n: number) {
  return '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

function fmtDate(d: string | null) {
  if (!d) return '';
  try {
    return new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch { return d; }
}

const STATUS_COLOR: Record<string, string> = {
  PROCESSED: Colors.success,
  SETTLED: Colors.success,
  HELD: Colors.warning,
  PENDING: '#3B82F6',
  FAILED: Colors.danger,
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function DuxIQChat({ visible, onClose, merchantId, settlement, initialPrompt }: DuxIQChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [phase, setPhase] = useState<'chat' | 'resolution' | 'ticket_offer' | 'rating' | 'ended'>('chat');
  const [input, setInput] = useState('');
  const [thinking, setThinking] = useState(false);
  const [rating, setRating] = useState(0);
  const [chatHistory, setChatHistory] = useState<ChatHistoryItem[]>([]);
  const scrollRef = useRef<ScrollView>(null);

  // Reset and seed opening message when modal opens
  useEffect(() => {
    if (!visible) return;
    setInput('');
    setRating(0);
    setPhase('chat');
    setThinking(false);
    setChatHistory([]);

    if (settlement) {
      const greeting = `Settlement #${settlement.id} loaded — ${fmtAmount(settlement.amount)}, ${settlement.status}.${settlement.date ? ' Expected ' + fmtDate(settlement.date) + '.' : ''} What would you like to know?`;
      setMessages([{
        id: 'greeting',
        role: 'bot',
        content: greeting,
        msgType: 'followups',
        followUps: [
          'Why is this less than the gross amount?',
          'What fees were deducted?',
          'Is this settlement delayed?',
          'How does this compare to last month?',
        ],
      }]);
    } else {
      setMessages([{
        id: 'greeting',
        role: 'bot',
        content: 'Hi! I\'m DUX IQ. Ask me anything about your settlements, payouts, or transactions.',
        msgType: 'followups',
        followUps: [
          'Show my recent settlements',
          'Why did my payout drop this month?',
          'Are any settlements overdue?',
          'What fees were deducted recently?',
        ],
      }]);
    }
  }, [visible, settlement?.id]);

  // Auto-send initialPrompt after greeting renders
  useEffect(() => {
    if (visible && initialPrompt) {
      const timer = setTimeout(() => sendMessage(initialPrompt), 400);
      return () => clearTimeout(timer);
    }
  }, [visible, initialPrompt]); // eslint-disable-line react-hooks/exhaustive-deps

  const scrollToEnd = () =>
    setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 100);

  // ---------------------------------------------------------------------------
  // API send
  // ---------------------------------------------------------------------------

  const sendMessage = async (text: string) => {
    const prompt = text.trim();
    if (!prompt || thinking || phase !== 'chat') return;
    setInput('');

    const userMsg: Message = { id: `u-${Date.now()}`, role: 'user', content: prompt, msgType: 'text' };
    setMessages(prev => [...prev, userMsg]);
    setThinking(true);
    scrollToEnd();

    const contextObject: ContextObject | undefined = settlement
      ? {
          type: 'settlement',
          id: String(settlement.id),
          metadata: {
            amount: settlement.amount,
            status: settlement.status,
            date: settlement.date ?? undefined,
          },
        }
      : undefined;

    try {
      const data = settlement
        ? await api.askSettlement({ merchantId, prompt, contextObject, history: chatHistory })
        : await api.ask({ merchantId, prompt, history: chatHistory });

      const botMsg: Message = {
        id: `b-${Date.now()}`,
        role: 'bot',
        content: data.answer || 'I could not find an answer. Please try again.',
        msgType: data.follow_ups?.length ? 'followups' : 'text',
        followUps: data.follow_ups || [],
      };

      setMessages(prev => [...prev, botMsg]);
      setChatHistory(prev => [
        ...prev,
        { role: 'user', content: prompt },
        { role: 'assistant', content: data.answer || '' },
      ]);
    } catch (err) {
      setMessages(prev => [...prev, {
        id: `err-${Date.now()}`,
        role: 'bot',
        content: 'Something went wrong — please check your connection and try again.',
        msgType: 'text',
      }]);
    } finally {
      setThinking(false);
      scrollToEnd();
    }
  };

  // ---------------------------------------------------------------------------
  // Resolution / ticket / rating flow
  // ---------------------------------------------------------------------------

  const handleResolution = (resolved: boolean) => {
    if (resolved) {
      setMessages(prev => [...prev,
        { id: `u-${Date.now()}`, role: 'user', content: 'Yes', msgType: 'text' },
        { id: `b-${Date.now()}`, role: 'bot', content: "Great! I'm glad I could help.", msgType: 'text' },
        { id: `rt-${Date.now()}`, role: 'bot', content: 'Please rate your experience', msgType: 'rating' },
      ]);
      setPhase('rating');
    } else {
      setMessages(prev => [...prev,
        { id: `u-${Date.now()}`, role: 'user', content: 'No', msgType: 'text' },
        { id: `b-${Date.now()}`, role: 'bot', content: 'Got it — the issue is still not resolved.\n\nWould you like me to raise a support ticket?', msgType: 'ticket_offer' },
      ]);
      setPhase('ticket_offer');
    }
    scrollToEnd();
  };

  const handleTicketOffer = (raise: boolean) => {
    if (raise) {
      const now = new Date();
      const pad = (n: number) => String(n).padStart(2, '0');
      const ticketId = `ICICI${pad(now.getDate())}${pad(now.getMonth()+1)}${String(now.getFullYear()).slice(-2)}${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}00001`;
      setMessages(prev => [...prev,
        { id: `u-${Date.now()}`, role: 'user', content: 'Yes, raise a ticket', msgType: 'text' },
        { id: `b-${Date.now()}`, role: 'bot', content: `Your support ticket has been created.\n\nTicket ID: ${ticketId}\n\nOur team will update you shortly.`, msgType: 'ticket_created' },
        { id: `rt-${Date.now()}`, role: 'bot', content: 'Please rate your experience', msgType: 'rating' },
      ]);
      setPhase('rating');
    } else {
      setMessages(prev => [...prev,
        { id: `u-${Date.now()}`, role: 'user', content: 'No', msgType: 'text' },
        { id: `b-${Date.now()}`, role: 'bot', content: 'Alright. Is there anything else I can help with?', msgType: 'text' },
      ]);
      setPhase('chat');
    }
    scrollToEnd();
  };

  const handleRating = (stars: number) => {
    setRating(stars);
    setTimeout(() => {
      setMessages(prev => [...prev,
        { id: `end-${Date.now()}`, role: 'system', content: 'Chat has ended', msgType: 'ended' },
      ]);
      setPhase('ended');
      scrollToEnd();
    }, 400);
  };

  // ---------------------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------------------

  const isLastBotMsg = (id: string) => {
    const botMsgs = messages.filter(m => m.role === 'bot');
    return botMsgs.length > 0 && botMsgs[botMsgs.length - 1].id === id;
  };

  const renderMessage = (msg: Message) => {
    switch (msg.msgType) {
      case 'text':
      case 'ticket_created':
        return msg.role === 'user' ? (
          <View key={msg.id} style={ss.userRow}>
            <View style={ss.userBubble}><Text style={ss.userText}>{msg.content}</Text></View>
          </View>
        ) : (
          <View key={msg.id} style={ss.botRow}>
            <View style={ss.botBubble}><Text style={ss.botText}>{msg.content}</Text></View>
          </View>
        );

      case 'followups':
        return (
          <View key={msg.id} style={ss.botRow}>
            <View style={ss.botBubble}>
              <Text style={ss.botText}>{msg.content}</Text>
              {/* Show chips only on the last bot message and when not thinking */}
              {isLastBotMsg(msg.id) && !thinking && phase === 'chat' && (msg.followUps?.length ?? 0) > 0 && (
                <View style={ss.chipsWrap}>
                  {msg.followUps!.map((chip, i) => (
                    <TouchableOpacity key={i} style={ss.chip} onPress={() => sendMessage(chip)}>
                      <Text style={ss.chipText}>{chip}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              )}
            </View>
          </View>
        );

      case 'resolution':
        return (
          <View key={msg.id} style={ss.botRow}>
            <View style={ss.botBubble}>
              <Text style={ss.botText}>{msg.content}</Text>
              {phase === 'resolution' && (
                <View style={ss.actionRow}>
                  <TouchableOpacity style={ss.actionBtn} onPress={() => handleResolution(true)}>
                    <Text style={ss.actionBtnText}>Yes</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={ss.actionBtn} onPress={() => handleResolution(false)}>
                    <Text style={ss.actionBtnText}>No</Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
          </View>
        );

      case 'ticket_offer':
        return (
          <View key={msg.id} style={ss.botRow}>
            <View style={ss.botBubble}>
              <Text style={ss.botText}>{msg.content}</Text>
              {phase === 'ticket_offer' && (
                <View style={ss.actionRow}>
                  <TouchableOpacity style={ss.actionBtn} onPress={() => handleTicketOffer(true)}>
                    <Text style={ss.actionBtnText}>Yes</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={ss.actionBtn} onPress={() => handleTicketOffer(false)}>
                    <Text style={ss.actionBtnText}>No</Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
          </View>
        );

      case 'rating':
        return (
          <View key={msg.id} style={ss.botRow}>
            <View style={ss.botBubble}>
              <Text style={ss.botText}>{msg.content}</Text>
              <View style={ss.starsRow}>
                {[1,2,3,4,5].map(star => (
                  <TouchableOpacity key={star} testID={`star-rating-${star}`} onPress={() => phase === 'rating' && handleRating(star)} disabled={phase !== 'rating'}>
                    <MaterialCommunityIcons name={star <= rating ? 'star' : 'star-outline'} size={30} color={star <= rating ? '#D97706' : Colors.textLight} />
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          </View>
        );

      case 'ended':
        return (
          <View key={msg.id} style={ss.endedRow}>
            <Text style={ss.endedText}>{msg.content}</Text>
          </View>
        );

      default:
        return null;
    }
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <Modal visible={visible} transparent animationType="slide" testID="dux-iq-chat-modal">
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={ss.overlay}>
          <View style={ss.container}>

            {/* Header */}
            <View style={ss.header}>
              <View style={ss.headerLeft}>
                <View style={ss.logoRow}>
                  <Text style={ss.duxText}>DUX</Text>
                  <Text style={ss.iqSuperText}>®</Text>
                  <Text style={ss.iqText}>IQ</Text>
                </View>
                {settlement && (
                  <View style={ss.settlementPill}>
                    <Text style={ss.settlementPillText}>#{settlement.id}</Text>
                    <View style={[ss.statusDot, { backgroundColor: STATUS_COLOR[settlement.status] ?? Colors.textMuted }]} />
                    <Text style={[ss.settlementPillStatus, { color: STATUS_COLOR[settlement.status] ?? Colors.textMuted }]}>
                      {settlement.status}
                    </Text>
                  </View>
                )}
              </View>
              <TouchableOpacity onPress={onClose} testID="dux-iq-close" style={ss.closeBtn}>
                <MaterialCommunityIcons name="close" size={22} color={Colors.textMain} />
              </TouchableOpacity>
            </View>

            {/* Messages */}
            <ScrollView
              ref={scrollRef}
              style={ss.msgArea}
              contentContainerStyle={ss.msgContent}
              onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
              showsVerticalScrollIndicator={false}
              keyboardShouldPersistTaps="handled"
            >
              {messages.map(renderMessage)}

              {/* Thinking indicator */}
              {thinking && (
                <View style={ss.botRow}>
                  <View style={[ss.botBubble, ss.thinkingBubble]}>
                    <ActivityIndicator size="small" color={Colors.primary} />
                    <Text style={ss.thinkingText}>Thinking…</Text>
                  </View>
                </View>
              )}

              {/* "Did this resolve your issue?" — shown after last bot message in chat phase */}
              {!thinking && phase === 'chat' && messages.filter(m => m.role === 'user').length > 0 && messages.filter(m => m.role === 'bot').length > 1 && (
                <View style={ss.resolveRow}>
                  <Text style={ss.resolveText}>Did this resolve your issue?</Text>
                  <TouchableOpacity style={ss.resolveBtn} onPress={() => { setPhase('resolution'); handleResolution(true); }}>
                    <Text style={ss.resolveBtnText}>Yes</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={ss.resolveBtn} onPress={() => { setPhase('resolution'); handleResolution(false); }}>
                    <Text style={ss.resolveBtnText}>No</Text>
                  </TouchableOpacity>
                </View>
              )}
            </ScrollView>

            {/* Input row */}
            {phase === 'chat' && (
              <View style={ss.inputRow}>
                <TextInput
                  style={ss.input}
                  testID="dux-iq-chat-input"
                  value={input}
                  onChangeText={setInput}
                  placeholder="Ask about this settlement…"
                  placeholderTextColor={Colors.textLight}
                  editable={!thinking}
                  onSubmitEditing={() => sendMessage(input)}
                  returnKeyType="send"
                  multiline={false}
                />
                <TouchableOpacity
                  testID="dux-iq-chat-send"
                  style={[ss.sendBtn, (!input.trim() || thinking) && ss.sendBtnDisabled]}
                  onPress={() => sendMessage(input)}
                  disabled={!input.trim() || thinking}
                >
                  <MaterialCommunityIcons name="send" size={20} color={Colors.white} />
                </TouchableOpacity>
              </View>
            )}
          </View>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const { height: SCREEN_H } = Dimensions.get('window');

const ss = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: Colors.overlay,
    justifyContent: 'flex-end',
  },
  container: {
    height: SCREEN_H * 0.88,
    backgroundColor: Colors.white,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    overflow: 'hidden',
  },
  // Header
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
    backgroundColor: '#FFF7ED',
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    flex: 1,
  },
  logoRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  duxText: {
    fontSize: 20,
    fontWeight: '900',
    color: '#C2410C',
    letterSpacing: 1,
  },
  iqSuperText: {
    fontSize: 9,
    color: Colors.textMuted,
    marginTop: -1,
  },
  iqText: {
    fontSize: 20,
    fontWeight: '900',
    color: '#16A34A',
    letterSpacing: 1,
  },
  settlementPill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.white,
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: Colors.border,
    gap: 5,
  },
  settlementPillText: {
    fontSize: 12,
    fontWeight: '700',
    color: Colors.textMain,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  settlementPillStatus: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  closeBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#F5F5F4',
    alignItems: 'center',
    justifyContent: 'center',
  },
  // Messages
  msgArea: {
    flex: 1,
  },
  msgContent: {
    padding: 16,
    paddingBottom: 24,
  },
  botRow: {
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  botBubble: {
    backgroundColor: '#F5F5F4',
    borderRadius: 16,
    borderTopLeftRadius: 4,
    padding: 14,
    maxWidth: '85%',
    borderWidth: 1,
    borderColor: Colors.border,
  },
  botText: {
    fontSize: 14,
    color: Colors.textMain,
    lineHeight: 21,
  },
  userRow: {
    alignItems: 'flex-end',
    marginBottom: 12,
  },
  userBubble: {
    backgroundColor: '#FFF1E6',
    borderRadius: 16,
    borderTopRightRadius: 4,
    padding: 14,
    maxWidth: '80%',
    borderWidth: 1,
    borderColor: '#FDBA74',
  },
  userText: {
    fontSize: 14,
    color: Colors.textMain,
    lineHeight: 21,
  },
  // Thinking
  thinkingBubble: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 10,
  },
  thinkingText: {
    fontSize: 13,
    color: Colors.textMuted,
    fontStyle: 'italic',
  },
  // Follow-up chips
  chipsWrap: {
    marginTop: 10,
    gap: 7,
  },
  chip: {
    backgroundColor: Colors.white,
    borderWidth: 1,
    borderColor: '#FDBA74',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 9,
  },
  chipText: {
    fontSize: 13,
    color: '#9A3412',
    fontWeight: '500',
  },
  // Resolution row (inline, not a separate message)
  resolveRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 4,
    marginBottom: 8,
    paddingHorizontal: 4,
  },
  resolveText: {
    flex: 1,
    fontSize: 12,
    color: Colors.textMuted,
    fontStyle: 'italic',
  },
  resolveBtn: {
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 6,
    backgroundColor: Colors.white,
  },
  resolveBtnText: {
    fontSize: 13,
    color: Colors.textMain,
    fontWeight: '600',
  },
  // Action buttons (resolution / ticket)
  actionRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 12,
  },
  actionBtn: {
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: 10,
    paddingHorizontal: 20,
    paddingVertical: 8,
    backgroundColor: Colors.white,
  },
  actionBtnText: {
    fontSize: 14,
    color: Colors.textMain,
    fontWeight: '600',
  },
  // Stars
  starsRow: {
    flexDirection: 'row',
    gap: 4,
    marginTop: 12,
    justifyContent: 'center',
  },
  // Ended
  endedRow: {
    alignItems: 'center',
    marginTop: 16,
    marginBottom: 8,
  },
  endedText: {
    fontSize: 13,
    color: Colors.textMuted,
    fontStyle: 'italic',
  },
  // Input
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
    backgroundColor: Colors.white,
  },
  input: {
    flex: 1,
    height: 44,
    backgroundColor: '#F5F5F4',
    borderRadius: 22,
    paddingHorizontal: 16,
    fontSize: 14,
    color: Colors.textMain,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  sendBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendBtnDisabled: {
    opacity: 0.4,
  },
});
