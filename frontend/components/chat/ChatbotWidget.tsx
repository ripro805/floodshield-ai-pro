'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  MessageCircle,
  X,
  Send,
  MapPin,
  ShieldAlert,
  HeartPulse,
  Hospital,
  Droplets,
  Languages,
  Sparkles,
  ChevronRight,
  Bot,
  User as UserIcon,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { useChatMessage, useReportIncident } from '@/hooks';
import { useAuth } from '@/lib/auth';
import DistrictName from '@/components/common/DistrictName';
import type { ChatSuggestedAction, ChatUiAction } from '@/lib/types';

interface LocalMessage {
  role: 'user' | 'assistant';
  content: string;
  intent?: string;
  actions?: ChatSuggestedAction[];
  ui_actions?: ChatUiAction[];
  tools_used?: string[];
  data_sources?: string[];
  ts: number;
}

/* ─── Markdown-ish mini renderer for chat bubbles ─────────────────────── */
function renderInline(text: string): JSX.Element[] {
  const lines = text.split('\n');
  const out: JSX.Element[] = [];
  lines.forEach((line, idx) => {
    const trimmed = line.trim();
    if (/^\d+\.\s/.test(trimmed)) {
      const body = trimmed.replace(/^\d+\.\s/, '');
      out.push(
        <div key={`l${idx}`} className="flex gap-2 mt-1.5 first:mt-0">
          <span className="text-sky-300/80 font-mono text-xs pt-0.5 shrink-0 w-5">
            {trimmed.split('.')[0]}.
          </span>
          <span className="flex-1">{parseInlineMarkdown(body)}</span>
        </div>
      );
    } else if (trimmed.startsWith('- ')) {
      out.push(
        <div key={`l${idx}`} className="flex gap-2 mt-1.5 first:mt-0">
          <span className="text-sky-300/70 shrink-0 leading-snug">•</span>
          <span className="flex-1">{parseInlineMarkdown(trimmed.slice(2))}</span>
        </div>
      );
    } else if (trimmed === '') {
      out.push(<div key={`l${idx}`} className="h-1.5" />);
    } else {
      out.push(
        <div key={`l${idx}`} className={idx > 0 ? 'mt-1.5' : ''}>
          {parseInlineMarkdown(line)}
        </div>
      );
    }
  });
  return out;
}

function parseInlineMarkdown(s: string): JSX.Element[] {
  const parts: JSX.Element[] = [];
  const regex = /(\*\*([^*]+)\*\*|`([^`]+)`)/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let i = 0;
  while ((match = regex.exec(s)) !== null) {
    if (match.index > last) parts.push(<span key={i++}>{s.slice(last, match.index)}</span>);
    if (match[2]) {
      parts.push(<strong key={i++} className="font-bold text-white">{match[2]}</strong>);
    } else if (match[3]) {
      parts.push(
        <code key={i++} className="px-1 py-0.5 rounded bg-white/10 text-sky-200 font-mono text-[0.85em]">
          {match[3]}
        </code>
      );
    }
    last = match.index + match[0].length;
  }
  if (last < s.length) parts.push(<span key={i++}>{s.slice(last)}</span>);
  return parts.length ? parts : [<span key={0}>{s}</span>];
}

function formatTime(ts: number): string {
  const d = new Date(ts);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

const QUICK_FAQS = [
  {
    label: 'Flood Safety',
    description: 'Stay safe during a flood',
    icon: ShieldAlert,
    gradient: 'from-sky-500 to-cyan-500',
    prompt: 'What should I do to stay safe from floods?',
  },
  {
    label: 'Disease Info',
    description: 'Cholera, dengue, leptospirosis',
    icon: HeartPulse,
    gradient: 'from-rose-500 to-pink-500',
    prompt: 'Tell me about waterborne disease prevention during floods',
  },
  {
    label: 'Hospital Resources',
    description: 'Find ORS, beds, doctors nearby',
    icon: Hospital,
    gradient: 'from-emerald-500 to-teal-500',
    prompt: 'Where can I find hospital resources?',
  },
  {
    label: 'Safe Water',
    description: 'ORS, chlorination, hand-washing',
    icon: Droplets,
    gradient: 'from-blue-500 to-indigo-500',
    prompt: 'How do I make water safe to drink at home?',
  },
];

const RISK_PALETTE: Record<
  string,
  { bg: string; text: string; dot: string; label: string }
> = {
  low:      { bg: 'bg-emerald-500/15',  text: 'text-emerald-300', dot: 'bg-emerald-400', label: 'Low'      },
  medium:   { bg: 'bg-amber-500/15',    text: 'text-amber-300',   dot: 'bg-amber-400',   label: 'Moderate' },
  high:     { bg: 'bg-orange-500/15',   text: 'text-orange-300',  dot: 'bg-orange-400',  label: 'High'     },
  critical: { bg: 'bg-rose-500/15',     text: 'text-rose-300',    dot: 'bg-rose-400',    label: 'Critical' },
};

export default function ChatbotWidget() {
  const router = useRouter();
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [language, setLanguage] = useState<'bn' | 'en'>('en');
  const [showIncidentForm, setShowIncidentForm] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [chatRiskLevel, setChatRiskLevel] = useState<{
    level: 'low' | 'medium' | 'high' | 'critical';
    value: number;
  } | null>(null);
  const [messages, setMessages] = useState<LocalMessage[]>([
    {
      role: 'assistant',
      content:
        "Hi! I'm the FloodShield AI Assistant. I can help with flood safety, disease prevention, hospital resources, and more. What would you like to know?",
      ts: Date.now(),
    },
  ]);
  const [input, setInput] = useState('');
  const [incidentText, setIncidentText] = useState('');
  const [selectedDistrict, setSelectedDistrict] = useState(user?.district || null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const chatMutation = useChatMessage();
  const incidentMutation = useReportIncident();

  const scrollToBottom = () => {
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 30);
  };

  useEffect(() => { scrollToBottom(); }, [messages, chatMutation.isPending]);
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 250);
  }, [open]);

  const sendMessage = useCallback(
    async (textOverride?: string) => {
      const text = (textOverride ?? input).trim();
      if (!text || chatMutation.isPending) return;

      const userMsg: LocalMessage = { role: 'user', content: text, ts: Date.now() };
      setMessages((prev) => [...prev, userMsg]);
      setInput('');

      try {
        const response = await chatMutation.mutateAsync({
          message: text,
          conversation_id: conversationId,
          language: language,
        });

        if (!conversationId) setConversationId(response.conversation_id);

        const assistantMsg: LocalMessage = {
          role: 'assistant',
          content: response.reply,
          intent: response.detected_intent,
          actions: response.suggested_actions,
          ui_actions: response.ui_actions ?? [],
          tools_used: response.tools_used ?? [],
          data_sources: response.data_sources ?? [],
          ts: Date.now(),
        };
        setMessages((prev) => [...prev, assistantMsg]);

        // Execute any UI actions the agent emitted (whitelisted by type).
        if (response.ui_actions && response.ui_actions.length) {
          for (const a of response.ui_actions) {
            try {
              handleUiAction(a);
            } catch (err) {
              console.warn('ui_action failed', a, err);
            }
          }
        }

        const replyLower = response.reply.toLowerCase();
        if (replyLower.includes('critical')) {
          setChatRiskLevel({ level: 'critical', value: 0.92 });
        } else if (replyLower.includes('high risk') || replyLower.includes('high flood')) {
          setChatRiskLevel({ level: 'high', value: 0.72 });
        } else if (replyLower.includes('medium risk') || replyLower.includes('moderate')) {
          setChatRiskLevel({ level: 'medium', value: 0.48 });
        } else if (replyLower.includes('low risk') || replyLower.includes('low flood')) {
          setChatRiskLevel({ level: 'low', value: 0.18 });
        }
      } catch (error) {
        const errorMsg: LocalMessage = {
          role: 'assistant',
          content:
            "Sorry, I hit a snag processing that. Please try again or call **999** for emergencies.",
          ts: Date.now(),
        };
        setMessages((prev) => [...prev, errorMsg]);
      }
    },
    [input, conversationId, language, chatMutation]
  );

  const reportIncident = useCallback(async () => {
    const text = incidentText.trim();
    if (!text || incidentMutation.isPending) return;
    try {
      const response = await incidentMutation.mutateAsync({
        text,
        district: selectedDistrict,
        latitude: null,
        longitude: null,
      });
      setIncidentText('');
      setShowIncidentForm(false);

      const severityToGauge: Record<
        string,
        { level: 'low' | 'medium' | 'high' | 'critical'; value: number }
      > = {
        Low:      { level: 'low',      value: 0.18 },
        Medium:   { level: 'medium',   value: 0.48 },
        High:     { level: 'high',     value: 0.72 },
        Critical: { level: 'critical', value: 0.92 },
      };
      if (severityToGauge[response.severity]) {
        setChatRiskLevel(severityToGauge[response.severity]);
      }

      const resultMsg: LocalMessage = {
        role: 'assistant',
        content:
          `**Incident Report Classified**\n\nSeverity: **${response.severity}**\nCategory: ${response.label}\n\nRecommended Action: ${response.recommended_action}` +
          (response.alert_created ? '\n\n**Alert created** and routed for review.' : ''),
        ts: Date.now(),
      };
      setMessages((prev) => [...prev, resultMsg]);
    } catch (error) {
      const errorMsg: LocalMessage = {
        role: 'assistant',
        content: 'Sorry, I could not process your incident report. Please try again.',
        ts: Date.now(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    }
  }, [incidentText, selectedDistrict, incidentMutation]);

  const handleQuickFAQ = (faq: (typeof QUICK_FAQS)[number]) => {
    sendMessage(faq.prompt);
  };

  const handleAction = (action: ChatSuggestedAction) => {
    if (action.action_type === 'navigate') {
      router.push(action.target);
      setOpen(false);
    } else if (action.action_type === 'call_endpoint') {
      router.push('/dashboard/resources');
      setOpen(false);
    } else if (action.action_type === 'emergency_call') {
      window.location.href = action.target;
    }
  };

  // Server-validated UI action execution.  The agent can only emit types
  // from this whitelist; the server also enforces role-based permissions
  // before they reach us.
  const handleUiAction = (action: ChatUiAction) => {
    const t = action.type;
    const p = (action.params ?? {}) as Record<string, any>;
    switch (t) {
      case 'navigate': {
        if (typeof p.route === 'string' && /^\/dashboard\/.+/.test(p.route)) {
          router.push(p.route);
          setOpen(false);
        } else if (typeof p.route === 'string' && (p.route.startsWith('/alerts') || p.route.startsWith('/admin'))) {
          router.push(p.route);
          setOpen(false);
        } else {
          console.warn('ui_action navigate: route not whitelisted', p.route);
        }
        break;
      }
      case 'select_district': {
        // The dashboard picks a district via URL -- this is the only place
        // map state and district selection happen today.
        if (typeof p.district === 'string' && p.district) {
          router.push(`/dashboard/${encodeURIComponent(p.district)}`);
          setOpen(false);
        }
        break;
      }
      case 'run_flood_check': {
        if (typeof p.district === 'string' && p.district) {
          router.push(`/dashboard/${encodeURIComponent(p.district)}`);
          setOpen(false);
        }
        break;
      }
      case 'run_full_assessment': {
        if (typeof p.district === 'string' && p.district) {
          router.push(`/dashboard/${encodeURIComponent(p.district)}?full_assessment=1`);
          setOpen(false);
        }
        break;
      }
      case 'open_satellite_view': {
        router.push('/dashboard?view=satellite');
        setOpen(false);
        break;
      }
      case 'open_alerts': {
        router.push('/alerts');
        setOpen(false);
        break;
      }
      case 'open_reports': {
        router.push('/dashboard?view=reports');
        setOpen(false);
        break;
      }
      case 'open_hospital_resources': {
        router.push('/dashboard/resources?tab=inventory');
        setOpen(false);
        break;
      }
      case 'open_hospital_directory': {
        // Public directory tab -- works for citizens and operational
        // users.  The optional district param deep-links into a
        // specific district view.
        const d = typeof p.district === 'string' && p.district ? p.district : '';
        router.push(`/dashboard/resources?tab=directory${d ? `&district=${encodeURIComponent(d)}` : ''}`);
        setOpen(false);
        break;
      }
      case 'open_hospital': {
        // Deep-link into a single hospital's detail modal.  We
        // dispatch a window event so HospitalDirectoryView (which
        // owns the modal) can open the right card without a router
        // round-trip.  We still navigate to the directory tab in
        // case the user is on a different page.
        const hid = p.hospital_id;
        if (!hid) {
          console.warn('open_hospital: missing hospital_id');
          break;
        }
        const dd = p.district || '';
        router.push(`/dashboard/resources?tab=directory${dd ? `&district=${encodeURIComponent(dd)}` : ''}`);
        // Fire the event after the route change so the listener
        // is mounted by the time it fires.  A 200ms delay is the
        // pragmatic middle ground; the modal opens as soon as the
        // directory view's mount effect wires up the listener.
        if (typeof window !== 'undefined') {
          window.setTimeout(() => {
            window.dispatchEvent(
              new CustomEvent('fs:open-hospital', { detail: { hospital_id: hid } })
            );
          }, 200);
        }
        setOpen(false);
        break;
      }
      default:
        console.warn('ui_action: unknown type', t);
    }
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const canSend = input.trim().length > 0 && !chatMutation.isPending;
  const isFirstAssistant = messages.filter((m) => m.role === 'assistant').length === 1;
  const risk = chatRiskLevel ? RISK_PALETTE[chatRiskLevel.level] : null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3 no-print">
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 30, scale: 0.92 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 30, scale: 0.92 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="w-[420px] max-w-[calc(100vw-2rem)] rounded-3xl overflow-hidden flex flex-col relative"
            style={{
              background:
                'linear-gradient(180deg, rgba(10,18,32,0.96) 0%, rgba(6,11,20,0.96) 100%)',
              backdropFilter: 'blur(28px)',
              border: '1px solid rgba(255,255,255,0.10)',
              boxShadow:
                '0 24px 80px rgba(2,6,16,0.55), 0 8px 32px rgba(56,189,248,0.18), inset 0 1px 0 rgba(255,255,255,0.06)',
              maxHeight: 'min(720px, calc(100vh - 8rem))',
              height: 'min(720px, calc(100vh - 8rem))',
            }}
          >
            {/* Gradient halo on top edge */}
            <div
              aria-hidden
              className="absolute inset-x-0 top-0 h-px"
              style={{
                background:
                  'linear-gradient(90deg, transparent, rgba(56,189,248,0.7), rgba(45,212,191,0.7), transparent)'
              }}
            />

            {/* ── Header ─────────────────────────────────────────── */}
            <div className="relative px-5 pt-5 pb-4 border-b border-white/[0.07]">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="relative">
                    <div
                      className="w-11 h-11 rounded-2xl flex items-center justify-center shadow-lg"
                      style={{
                        background:
                          'linear-gradient(135deg, #38BDF8 0%, #2DD4BF 60%, #A78BFA 100%)',
                      }}
                    >
                      <Bot size={22} className="text-white drop-shadow" />
                    </div>
                    <span className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full bg-emerald-400 border-2 border-[#0a1220]">
                      <span className="absolute inset-0 rounded-full bg-emerald-400 animate-ping opacity-75" />
                    </span>
                  </div>
                  <div>
                    <div className="flex items-center gap-1.5">
                      <h3 className="text-white font-bold text-base leading-none">
                        FloodShield AI
                      </h3>
                      <Sparkles size={13} className="text-amber-300" />
                    </div>
                    <p className="text-[11px] text-white/45 mt-1 leading-none">
                      WHO · DGHS · RAG-powered
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setLanguage(language === 'en' ? 'bn' : 'en')}
                    className="flex items-center gap-1 text-[11px] px-2.5 py-1.5 rounded-full border border-white/10 text-white/60 hover:text-white hover:border-white/20 transition"
                    aria-label="Toggle language"
                  >
                    <Languages size={12} />
                    <span className="font-semibold">
                      {language === 'en' ? 'EN' : 'বাং'}
                    </span>
                  </button>
                  <button
                    onClick={() => setOpen(false)}
                    className="text-white/40 hover:text-white hover:bg-white/5 transition p-1.5 rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
                    aria-label="Close chat"
                  >
                    <X size={16} />
                  </button>
                </div>
              </div>

              {risk && (
                <motion.div
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-full ${risk.bg} ${risk.text} text-xs font-semibold border border-white/[0.06]`}
                >
                  <span className={`w-2 h-2 rounded-full ${risk.dot} animate-pulse`} />
                  Current risk: {risk.label}
                </motion.div>
              )}
            </div>

            {/* ── Content area ─────────────────────────────────────── */}
            {!showIncidentForm ? (
              <>
                {isFirstAssistant && !chatMutation.isPending && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                    className="px-5 pt-4 pb-1"
                  >
                    <p className="text-[11px] uppercase tracking-wider text-white/40 font-semibold mb-2.5">
                      Quick topics
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      {QUICK_FAQS.map((faq, i) => {
                        const Icon = faq.icon;
                        return (
                          <motion.button
                            key={i}
                            whileHover={{ y: -2 }}
                            whileTap={{ scale: 0.97 }}
                            onClick={() => handleQuickFAQ(faq)}
                            className="group relative text-left p-3 rounded-2xl border border-white/[0.07] bg-white/[0.03] hover:bg-white/[0.06] hover:border-white/15 transition-all overflow-hidden"
                          >
                            <div
                              className={`absolute -top-6 -right-6 w-16 h-16 rounded-full bg-gradient-to-br ${faq.gradient} opacity-20 blur-xl group-hover:opacity-40 transition-opacity`}
                            />
                            <div
                              className={`w-8 h-8 rounded-xl mb-2 flex items-center justify-center bg-gradient-to-br ${faq.gradient}`}
                            >
                              <Icon size={16} className="text-white drop-shadow" />
                            </div>
                            <div className="text-xs font-bold text-white leading-tight">
                              {faq.label}
                            </div>
                            <div className="text-[10px] text-white/45 mt-0.5 leading-tight">
                              {faq.description}
                            </div>
                          </motion.button>
                        );
                      })}
                    </div>
                  </motion.div>
                )}

                <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 chat-scroll">
                  {messages.map((m, i) => {
                    const isUser = m.role === 'user';
                    return (
                      <motion.div
                        key={i}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.25 }}
                        className={`flex gap-2 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
                      >
                        {!isUser && (
                          <div
                            className="shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5"
                            style={{
                              background:
                                'linear-gradient(135deg, #38BDF8 0%, #2DD4BF 100%)',
                            }}
                          >
                            <Bot size={14} className="text-white" />
                          </div>
                        )}
                        {isUser && (
                          <div className="shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center mt-0.5">
                            <UserIcon size={14} className="text-white" />
                          </div>
                        )}

                        <div
                          className={`flex flex-col max-w-[78%] ${
                            isUser ? 'items-end' : 'items-start'
                          }`}
                        >
                          <div
                            className={`relative px-3.5 py-2.5 text-[13.5px] leading-relaxed shadow-sm ${
                              isUser
                                ? 'rounded-2xl rounded-tr-md text-white'
                                : 'rounded-2xl rounded-tl-md text-white/90 border border-white/[0.07]'
                            }`}
                            style={
                              isUser
                                ? {
                                    background:
                                      'linear-gradient(135deg, #4F46E5 0%, #2563EB 100%)',
                                  }
                                : {
                                    background:
                                      'linear-gradient(180deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.03) 100%)',
                                  }
                            }
                          >
                            <div className="break-words">
                              {renderInline(m.content)}
                            </div>
                          </div>

                          {m.tools_used && m.tools_used.length > 0 && (
                            <div className="flex flex-wrap items-center gap-1.5 mt-2 text-[10.5px] text-emerald-300/70">
                              <span className="inline-flex items-center gap-1 font-mono uppercase tracking-wide text-emerald-300/80">
                                <Sparkles size={10} className="text-emerald-300/70" />
                                Used
                              </span>
                              {m.tools_used.map((t, j) => (
                                <span
                                  key={j}
                                  className="inline-flex items-center px-1.5 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-400/20 text-emerald-200/90 font-mono"
                                >
                                  {t}
                                </span>
                              ))}
                              {m.data_sources && m.data_sources.length > 0 && (
                                <span className="ml-1 text-[10px] text-white/35">
                                  ({Array.from(new Set(m.data_sources)).join(', ')})
                                </span>
                              )}
                            </div>
                          )}

                          {m.actions && m.actions.length > 0 && (
                            <div className="flex flex-wrap gap-1.5 mt-2">
                              {m.actions.map((action, j) => {
                                const isEmergency = action.action_type === 'emergency_call';
                                return (
                                  <motion.button
                                    key={j}
                                    whileHover={{ scale: 1.04 }}
                                    whileTap={{ scale: 0.96 }}
                                    onClick={() => handleAction(action)}
                                    className={`inline-flex items-center gap-1.5 text-[11.5px] font-semibold px-2.5 py-1.5 rounded-full transition border ${
                                      isEmergency
                                        ? 'bg-rose-500/15 border-rose-400/40 text-rose-200 hover:bg-rose-500/25'
                                        : 'bg-sky-500/10 border-sky-400/30 text-sky-200 hover:bg-sky-500/20'
                                    }`}
                                  >
                                    {action.label}
                                    {isEmergency ? <ChevronRight size={11} /> : <ChevronRight size={11} />}
                                  </motion.button>
                                );
                              })}
                            </div>
                          )}

                          <span className="text-[10px] text-white/30 mt-1 px-1">
                            {formatTime(m.ts)}
                          </span>
                        </div>
                      </motion.div>
                    );
                  })}

                  {chatMutation.isPending && (
                    <motion.div
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="flex gap-2"
                    >
                      <div
                        className="shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5"
                        style={{
                          background:
                            'linear-gradient(135deg, #38BDF8 0%, #2DD4BF 100%)',
                        }}
                      >
                        <Bot size={14} className="text-white" />
                      </div>
                      <div className="rounded-2xl rounded-tl-md border border-white/[0.07] px-4 py-3 flex items-center gap-1.5"
                        style={{
                          background:
                            'linear-gradient(180deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.03) 100%)',
                        }}
                      >
                        <motion.span
                          animate={{ y: [0, -4, 0] }}
                          transition={{ repeat: Infinity, duration: 0.9, delay: 0 }}
                          className="w-1.5 h-1.5 rounded-full bg-sky-400"
                        />
                        <motion.span
                          animate={{ y: [0, -4, 0] }}
                          transition={{ repeat: Infinity, duration: 0.9, delay: 0.15 }}
                          className="w-1.5 h-1.5 rounded-full bg-sky-400"
                        />
                        <motion.span
                          animate={{ y: [0, -4, 0] }}
                          transition={{ repeat: Infinity, duration: 0.9, delay: 0.3 }}
                          className="w-1.5 h-1.5 rounded-full bg-sky-400"
                        />
                      </div>
                    </motion.div>
                  )}
                  <div ref={bottomRef} />
                </div>

                {/* Input bar */}
                <div className="px-4 pb-4 pt-2 border-t border-white/[0.07] bg-gradient-to-t from-black/20 to-transparent">
                  <div className="flex items-center gap-2 rounded-2xl bg-slate-900/70 border border-white/10 focus-within:border-sky-400/60 focus-within:bg-slate-900/90 transition px-3 py-2 shadow-inner">
                    <input
                      ref={inputRef}
                      type="text"
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={handleKey}
                      placeholder={
                        chatMutation.isPending
                          ? 'Thinking...'
                          : 'Ask about flood safety, diseases, hospitals...'
                      }
                      disabled={chatMutation.isPending}
                      autoComplete="off"
                      spellCheck={false}
                      className="flex-1 bg-slate-950/70 text-white placeholder:text-slate-400 text-sm focus:outline-none caret-sky-400"
                    />
                    <button
                      onClick={() => sendMessage()}
                      disabled={!canSend}
                      className={`shrink-0 w-9 h-9 rounded-xl flex items-center justify-center transition shadow-md ${
                        canSend
                          ? 'bg-gradient-to-br from-sky-500 to-blue-600 text-white hover:scale-105'
                          : 'bg-white/5 text-white/30'
                      }`}
                      aria-label="Send message"
                    >
                      <Send size={15} />
                    </button>
                  </div>

                  <div className="flex items-center justify-between mt-2 px-1">
                    <button
                      onClick={() => setShowIncidentForm(true)}
                      className="text-[10.5px] text-white/40 hover:text-sky-300 transition flex items-center gap-1"
                    >
                      <MapPin size={10} /> Report an incident
                    </button>
                    <span className="text-[10px] text-white/30">
                      Not medical advice · For emergencies dial <strong className="text-rose-300">999</strong>
                    </span>
                  </div>
                </div>
              </>
            ) : (

              <div className="flex-1 overflow-y-auto p-5">
                <div className="flex items-center gap-2 mb-4">
                  <button
                    onClick={() => setShowIncidentForm(false)}
                    className="text-white/60 hover:text-white text-sm"
                  >
                    ← Back to chat
                  </button>
                </div>

                <div className="text-center mb-5">
                  <div
                    className="w-14 h-14 rounded-2xl mx-auto mb-3 flex items-center justify-center shadow-lg"
                    style={{
                      background:
                        'linear-gradient(135deg, #F43F5E 0%, #F59E0B 100%)',
                    }}
                  >
                    <MapPin size={26} className="text-white" />
                  </div>
                  <h4 className="text-white font-bold text-lg">Report an Incident</h4>
                  <p className="text-white/50 text-xs mt-1">
                    Tell me what you're seeing — flood, water contamination, disease, sanitation.
                  </p>
                </div>

                <div className="space-y-3">
                  <label className="block">
                    <span className="text-xs text-white/60 font-semibold uppercase tracking-wider">
                      District (optional)
                    </span>
                    <input
                      type="text"
                      value={selectedDistrict || ''}
                      onChange={(e) => setSelectedDistrict(e.target.value || null)}
                      placeholder="e.g. Feni"
                      autoComplete="off"
                      className="mt-1 w-full bg-slate-950/60 border border-white/10 rounded-xl px-3 py-2 text-white placeholder:text-slate-400 text-sm focus:outline-none focus:border-sky-400/50 caret-sky-400"
                    />
                    {selectedDistrict && selectedDistrict.trim().length > 1 && (
                      <div className="mt-1.5 ml-1">
                        <DistrictName en={selectedDistrict} size="sm" />
                      </div>
                    )}
                  </label>

                  <label className="block">
                    <span className="text-xs text-white/60 font-semibold uppercase tracking-wider">
                      What happened?
                    </span>
                    <textarea
                      value={incidentText}
                      onChange={(e) => setIncidentText(e.target.value)}
                      placeholder="e.g. Our tube-well water smells of kerosene"
                      rows={5}
                      autoComplete="off"
                      className="mt-1 w-full bg-slate-950/60 border border-white/10 rounded-xl px-3 py-2 text-white placeholder:text-slate-400 text-sm focus:outline-none focus:border-sky-400/50 caret-sky-400 resize-none"
                    />
                  </label>

                  <button
                    onClick={reportIncident}
                    disabled={!incidentText.trim() || incidentMutation.isPending}
                    className="w-full py-3 rounded-xl bg-gradient-to-r from-rose-500 to-amber-500 text-white font-semibold text-sm disabled:opacity-40 disabled:cursor-not-allowed hover:scale-[1.02] active:scale-95 transition shadow-lg"
                  >
                    {incidentMutation.isPending ? 'Submitting...' : 'Submit Report'}
                  </button>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* FAB */}
      <motion.button
        whileHover={{ scale: 1.06 }}
        whileTap={{ scale: 0.94 }}
        onClick={() => setOpen((o) => !o)}
        className="relative w-16 h-16 rounded-full shadow-2xl flex items-center justify-center group focus:outline-none focus-visible:ring-4 focus-visible:ring-sky-400/50"
        style={{
          background: open
            ? 'linear-gradient(135deg, #1E293B 0%, #0F172A 100%)'
            : 'linear-gradient(135deg, #38BDF8 0%, #2563EB 50%, #7C3AED 100%)',
        }}
        aria-label={open ? 'Close chat' : 'Open chat'}
      >
        {/* Animated ring */}
        {!open && (
          <span className="absolute inset-0 rounded-full">
            <span className="absolute inset-0 rounded-full bg-sky-400 opacity-30 animate-ping" />
          </span>
        )}

        <AnimatePresence mode="wait">
          {open ? (
            <motion.span
              key="x"
              initial={{ rotate: -90, opacity: 0 }}
              animate={{ rotate: 0, opacity: 1 }}
              exit={{ rotate: 90, opacity: 0 }}
              transition={{ duration: 0.15 }}
            >
              <X size={26} className="text-white" />
            </motion.span>
          ) : (
            <motion.span
              key="msg"
              initial={{ rotate: 90, opacity: 0 }}
              animate={{ rotate: 0, opacity: 1 }}
              exit={{ rotate: -90, opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="relative"
            >
              <MessageCircle size={26} className="text-white drop-shadow" />
              <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-amber-400 border-2 border-[#0a1220]" />
            </motion.span>
          )}
        </AnimatePresence>
      </motion.button>

      <style jsx global>{`
        .chat-scroll::-webkit-scrollbar { width: 6px; }
        .chat-scroll::-webkit-scrollbar-track { background: transparent; }
        .chat-scroll::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
        .chat-scroll::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
      `}</style>
    </div>
  );
}
