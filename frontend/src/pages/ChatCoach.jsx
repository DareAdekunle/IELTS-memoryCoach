import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import { startChat, continueChat, getChatContext } from '../api/chat'
import { useAuth } from '../context/AuthContext'
import {
  Loader2, Send, MessageSquare,
  PenLine, BookOpen, Mic, Headphones, Zap
} from 'lucide-react'
import { Link } from 'react-router-dom'

const STATE_LABELS = {
  introduction:       { label: 'Getting started',       color: 'text-blue-400' },
  explaining:         { label: 'Learning the skill',     color: 'text-purple-400' },
  drilling:           { label: 'Practising with drills', color: 'text-yellow-400' },
  bridge_to_practice: { label: 'Ready to practise',      color: 'text-green-400' },
}

const SECTIONS = [
  {
    id: 'Writing',
    label: 'Writing',
    icon: PenLine,
    color: 'text-purple-400',
    bg: 'bg-purple-500/15',
    border: 'border-purple-500/40',
    description: 'Essay structure, task response, vocabulary',
    practiceLink: '/writing'
  },
  {
    id: 'Reading',
    label: 'Reading',
    icon: BookOpen,
    color: 'text-blue-400',
    bg: 'bg-blue-500/15',
    border: 'border-blue-500/40',
    description: 'Comprehension strategies, T/F/NG, inference',
    practiceLink: '/reading'
  },
  {
    id: 'Speaking',
    label: 'Speaking',
    icon: Mic,
    color: 'text-green-400',
    bg: 'bg-green-500/15',
    border: 'border-green-500/40',
    description: 'Fluency, answer extension, pronunciation',
    practiceLink: '/speaking'
  },
  {
    id: 'Listening',
    label: 'Listening',
    icon: Headphones,
    color: 'text-yellow-400',
    bg: 'bg-yellow-500/15',
    border: 'border-yellow-500/40',
    description: 'Prediction, distractor resistance, detail capture',
    practiceLink: '/listening'
  },
]

const PRACTICE_LINKS = {
  Writing: '/writing',
  Reading: '/reading',
  Speaking: '/speaking',
  Listening: '/listening',
}

const SESSION_CACHE_KEY = (section) => `chat_session_${section}`

export default function ChatCoach() {
  const { user } = useAuth()
  const [selectedSection, setSelectedSection] = useState(null)
  const [messages, setMessages]               = useState([])
  const [systemPrompt, setSystemPrompt]       = useState('')
  const [state, setState]                     = useState(null)
  const [hasHistory, setHasHistory]           = useState(null)
  const [tutorContext, setTutorContext]        = useState(null)
  const [sessionId, setSessionId]             = useState(null)
  const [pedagogy, setPedagogy]               = useState(null)
  const [input, setInput]                     = useState('')
  const [loading, setLoading]                 = useState(false)
  const [sending, setSending]                 = useState(false)
  const [error, setError]                     = useState('')
  const bottomRef = useRef(null)
  const inputRef  = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSelectSection = async (sectionId) => {
    setSelectedSection(sectionId)
    setTutorContext(null)
    setError('')

    // Check session cache first
    const cached = sessionStorage.getItem(SESSION_CACHE_KEY(sectionId))
    if (cached) {
      try {
        const parsed = JSON.parse(cached)
        setMessages(parsed.messages)
        setSystemPrompt(parsed.systemPrompt)
        setState(parsed.state)
        setHasHistory(parsed.hasHistory)
        setSessionId(parsed.sessionId || null)
        setPedagogy(parsed.pedagogy || null)
        return
      } catch {
        sessionStorage.removeItem(SESSION_CACHE_KEY(sectionId))
      }
    }

    setMessages([])
    setSystemPrompt('')
    setState(null)
    setHasHistory(null)
    setSessionId(null)
    setPedagogy(null)
    setLoading(true)

    // Phase 1 — fetch context instantly (DB only, no Qwen call)
    // Shows the learner what the tutor will focus on while AI loads
    try {
      const ctxRes = await getChatContext(sectionId)
      setTutorContext(ctxRes.data)
    } catch {
      // Non-blocking — context preview is optional
    }

    // Phase 2 — start the AI tutor session
    try {
      const res = await startChat(sectionId)
      const data = res.data
      const newMessages = [{ role: 'assistant', content: data.message }]

      setMessages(newMessages)
      setState(data.state)
      setHasHistory(data.has_history)
      setSystemPrompt(data.system_prompt || '')
      setSessionId(data.session_id || null)
      setPedagogy(data.pedagogy || null)

      sessionStorage.setItem(SESSION_CACHE_KEY(sectionId), JSON.stringify({
        messages: newMessages,
        systemPrompt: data.system_prompt || '',
        state: data.state,
        hasHistory: data.has_history,
        sessionId: data.session_id || null,
        pedagogy: data.pedagogy || null
      }))

    } catch (err) {
      setError(err.response?.data?.detail || 'Could not start tutor session.')
    } finally {
      setLoading(false)
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }

  const handleSend = async () => {
    const text = input.trim()
    if (!text || sending) return

    const userMessage = { role: 'user', content: text }
    const newMessages = [...messages, userMessage]
    setMessages(newMessages)
    setInput('')
    setSending(true)
    setError('')

    try {
      if (!hasHistory) {
        const replyMessage = {
          role: 'assistant',
          content: `I'll be able to help much more once you've tried the ${selectedSection} Coach! Head over there to complete a session, then come back and I'll give you personalised coaching 😊`
        }
        const updatedMessages = [...newMessages, replyMessage]
        setMessages(updatedMessages)
        sessionStorage.setItem(SESSION_CACHE_KEY(selectedSection), JSON.stringify({
          messages: updatedMessages,
          systemPrompt,
          state,
          hasHistory
        }))
        setSending(false)
        return
      }

      const historyForCall = newMessages.slice(0, -1)
      const res = await continueChat({
        system_prompt: systemPrompt,
        history: historyForCall,
        message: text,
        section: selectedSection,
        session_id: sessionId
      })

      const replyText = (res.data.message || '').trim() ||
        "Hmm, my reply didn't come through properly — could you say that again?"
      const assistantMessage = { role: 'assistant', content: replyText }
      const updatedMessages = [...newMessages, assistantMessage]

      setMessages(updatedMessages)
      setState(res.data.state)

      sessionStorage.setItem(SESSION_CACHE_KEY(selectedSection), JSON.stringify({
        messages: updatedMessages,
        systemPrompt,
        state: res.data.state,
        hasHistory,
        sessionId,
        pedagogy
      }))

    } catch (err) {
      const isTimeout = err.code === 'ECONNABORTED'
      setError(isTimeout
        ? 'The tutor took too long to respond. Please try sending your message again.'
        : (err.response?.data?.detail || 'Something went wrong.'))
      // Roll the unanswered message back into the input so it isn't lost
      setMessages(messages)
      setInput(text)
    } finally {
      setSending(false)
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const resetSession = () => {
    if (selectedSection) {
      sessionStorage.removeItem(SESSION_CACHE_KEY(selectedSection))
    }
    setSelectedSection(null)
    setMessages([])
    setSystemPrompt('')
    setState(null)
    setHasHistory(null)
    setTutorContext(null)
    setSessionId(null)
    setPedagogy(null)
    setError('')
    setInput('')
  }

  const stateInfo      = state ? STATE_LABELS[state] : null
  const firstName      = user?.full_name?.split(' ')[0] || user?.username || 'there'
  const currentSection = SECTIONS.find(s => s.id === selectedSection)

  // ── Section selector ───────────────────────────────────────────────────────
  if (!selectedSection) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <MessageSquare className="w-6 h-6 text-brand-600" />
            IELTS Tutor
          </h1>
          <p className="text-gray-500 mt-1">
            Choose your specialist — each tutor knows your history and targets your weaknesses
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          {SECTIONS.map(({ id, label, icon: Icon, color, bg, border, description }) => (
            <button
              key={id}
              onClick={() => handleSelectSection(id)}
              className={
                'text-left p-5 rounded-2xl border transition-all hover:scale-[1.02] ' +
                bg + ' ' + border
              }
            >
              <div className="flex items-center gap-3 mb-3">
                <div className={'w-10 h-10 rounded-xl flex items-center justify-center ' + bg}>
                  <Icon className={'w-5 h-5 ' + color} />
                </div>
                <div>
                  <p className="text-gray-900 font-semibold">{label} Tutor</p>
                  <p className={'text-xs ' + color}>Specialist AI coach</p>
                </div>
              </div>
              <p className="text-gray-500 text-sm">{description}</p>
            </button>
          ))}
        </div>

        <p className="text-center text-gray-600 text-sm mt-6">
          Each tutor analyses your practice history and targets your specific weaknesses
        </p>
      </div>
    )
  }

  // ── Chat interface ─────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-[calc(100vh-0px)] max-h-screen">

      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-gray-200 bg-slate-50">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            {currentSection && (
              <div className={'w-10 h-10 rounded-xl flex items-center justify-center ' + currentSection.bg}>
                <currentSection.icon className={'w-5 h-5 ' + currentSection.color} />
              </div>
            )}
            <div>
              <h1 className="text-gray-900 font-semibold">{selectedSection} Tutor</h1>
              <p className="text-gray-500 text-xs">Specialist AI coach</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {stateInfo && (
              <span className={'text-xs font-medium ' + stateInfo.color}>
                {stateInfo.label}
              </span>
            )}
            <button
              onClick={resetSession}
              className="text-xs text-gray-500 hover:text-gray-600 px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
            >
              Change section
            </button>
          </div>
        </div>

        {/* Pedagogy strip — how the tutor is teaching this session */}
        {pedagogy && (
          <div className="max-w-3xl mx-auto mt-3 flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-brand-50 text-brand-700 border border-brand-100">
              {(pedagogy.learner_stage || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
            </span>
            <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-violet-50 text-violet-700 border border-violet-100">
              {(pedagogy.dominant_framework || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
            </span>
            <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 border border-amber-100">
              Support: {pedagogy.support_level}
            </span>
            {pedagogy.target_descriptor && (
              <span className="text-xs text-gray-500 truncate flex-1 min-w-0" title={pedagogy.target_descriptor}>
                🎯 Band {pedagogy.target_band?.toFixed(1)}: {pedagogy.target_descriptor}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="max-w-3xl mx-auto space-y-4">

          {/* Context preview card — shown instantly while AI loads */}
          {loading && tutorContext?.has_history && (
            <div className="bg-white border border-brand-500/30 rounded-2xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Loader2 className="w-4 h-4 animate-spin text-brand-500" />
                <span className="text-gray-500 text-sm">
                  Your {selectedSection} Tutor is preparing your session...
                </span>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <Zap className="w-4 h-4 text-brand-600 flex-shrink-0" />
                <div>
                  <p className="text-gray-900 text-sm font-medium">
                    Focusing on: {tutorContext.weakest_skill_name}
                  </p>
                  <p className="text-gray-500 text-xs mt-0.5">
                    {tutorContext.rank_name} ·{' '}
                    {tutorContext.sessions_to_rank_up > 0
                      ? `${tutorContext.sessions_to_rank_up} session${tutorContext.sessions_to_rank_up > 1 ? 's' : ''} to next rank`
                      : 'At maximum rank'}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* No history loading state */}
          {loading && !tutorContext?.has_history && (
            <div className="flex items-center gap-3 text-gray-500">
              <Loader2 className="w-5 h-5 animate-spin text-brand-500" />
              <span className="text-sm">
                Your {selectedSection} tutor is preparing...
              </span>
            </div>
          )}

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={'flex gap-3 ' + (msg.role === 'user' ? 'justify-end' : 'justify-start')}
            >
              {msg.role === 'assistant' && currentSection && (
                <div className={'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-1 ' + currentSection.bg}>
                  <currentSection.icon className={'w-4 h-4 ' + currentSection.color} />
                </div>
              )}

              <div className={
                'max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ' +
                (msg.role === 'user'
                  ? 'bg-brand-600 text-white rounded-br-sm'
                  : 'bg-white border border-gray-200 text-gray-600 rounded-bl-sm')
              }>
                {msg.role === 'user' ? (
                  msg.content
                ) : (
                  <ReactMarkdown
                    components={{
                      p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                      strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
                      em: ({ children }) => <em className="italic">{children}</em>,
                      ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>,
                      ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-1">{children}</ol>,
                      li: ({ children }) => <li className="text-sm">{children}</li>,
                      code: ({ children }) => <code className="bg-gray-100 text-gray-800 px-1.5 py-0.5 rounded text-xs font-mono">{children}</code>,
                      blockquote: ({ children }) => <blockquote className="border-l-2 border-brand-300 pl-3 text-gray-500 italic my-2">{children}</blockquote>,
                      h3: ({ children }) => <h3 className="font-semibold text-gray-900 mt-3 mb-1">{children}</h3>,
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                )}
              </div>

              {msg.role === 'user' && (
                <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center flex-shrink-0 mt-1 text-sm font-bold text-gray-600">
                  {firstName[0].toUpperCase()}
                </div>
              )}
            </div>
          ))}

          {sending && (
            <div className="flex gap-3 justify-start">
              {currentSection && (
                <div className={'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ' + currentSection.bg}>
                  <currentSection.icon className={'w-4 h-4 ' + currentSection.color} />
                </div>
              )}
              <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-3">
                <div className="flex gap-1">
                  {[0, 150, 300].map(delay => (
                    <div
                      key={delay}
                      className="w-2 h-2 rounded-full bg-gray-600 animate-bounce"
                      style={{ animationDelay: delay + 'ms' }}
                    />
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Bridge to practice */}
          {state === 'bridge_to_practice' && !sending && selectedSection && (
            <div className="flex justify-center py-2">
              <Link
                to={PRACTICE_LINKS[selectedSection]}
                className="flex items-center gap-2 px-6 py-3 bg-brand-600 hover:bg-brand-700 text-white font-semibold rounded-xl transition-colors"
              >
                {currentSection && <currentSection.icon className="w-4 h-4" />}
                Go to {selectedSection} Coach to practise →
              </Link>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input */}
      <div className="flex-shrink-0 px-6 py-4 border-t border-gray-200 bg-slate-50">
        <div className="max-w-3xl mx-auto">
          <div className="flex gap-3 items-end">
            <div className="flex-1 bg-white border border-gray-200 rounded-2xl px-4 py-3 focus-within:border-brand-500 transition-colors">
              <textarea
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={loading ? 'Waiting for your tutor...' : 'Type your message... (Enter to send)'}
                disabled={loading || sending}
                rows={1}
                className="w-full bg-transparent text-gray-900 placeholder-gray-400 text-sm resize-none focus:outline-none disabled:opacity-50"
                style={{ maxHeight: '120px' }}
                onInput={e => {
                  e.target.style.height = 'auto'
                  e.target.style.height = e.target.scrollHeight + 'px'
                }}
              />
            </div>
            <button
              onClick={handleSend}
              disabled={!input.trim() || loading || sending}
              className="w-12 h-12 flex items-center justify-center bg-brand-500 hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed text-gray-900 rounded-2xl transition-colors flex-shrink-0"
            >
              {sending
                ? <Loader2 className="w-5 h-5 animate-spin" />
                : <Send className="w-5 h-5" />
              }
            </button>
          </div>
          <p className="text-gray-600 text-xs mt-2 text-center">
            {selectedSection} Specialist · Targets your weakest skill · Enter to send
          </p>
        </div>
      </div>
    </div>
  )
}
