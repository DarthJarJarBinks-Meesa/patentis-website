import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import ThinkingBlock from '../components/ThinkingBlock'
import { startConversation, streamChat } from '../api/client'
import { parseThinking } from '../utils/thinking'
import type { Idea } from '../types'

type MsgType = 'status' | 'analysis' | 'ideas' | 'text'

interface ConvMessage {
  id: string
  role: 'user' | 'assistant'
  type: MsgType
  content: string
  ideas?: Idea[]
  streaming?: boolean
}

const EXAMPLES = [
  'Resorbable interbody spinal cage with antibiotic elution',
  'Drug-eluting coronary stent with biodegradable polymer coating',
  'Continuous glucose monitor using interstitial fluid optical sensing',
  'Pedicle screw with variable-angle locking mechanism',
]

let _msgCounter = 0
function nextId() { return String(++_msgCounter) }

export default function ConversationPage() {
  // Phases: landing → setup → chat
  const [phase, setPhase] = useState<'landing' | 'setup' | 'chat'>('landing')
  const [queryInput, setQueryInput] = useState('')
  const [domain, setDomain] = useState('')

  // Session (set once search_done event arrives)
  const [sessionId, setSessionId] = useState<string | null>(null)

  // Unified message thread
  const [messages, setMessages] = useState<ConvMessage[]>([])
  // Which analysis messages are expanded
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  // Chat input
  const [chatInput, setChatInput] = useState('')
  const [responding, setResponding] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const bottomRef = useRef<HTMLDivElement>(null)
  const chatInputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ── helpers ────────────────────────────────────────────────────────────────

  function addMsg(msg: ConvMessage) {
    setMessages(prev => [...prev, msg])
    return msg.id
  }

  function appendToMsg(id: string, content: string) {
    setMessages(prev => prev.map(m =>
      m.id === id ? { ...m, content: m.content + content } : m
    ))
  }

  function finaliseMsg(id: string) {
    setMessages(prev => prev.map(m =>
      m.id === id ? { ...m, streaming: false } : m
    ))
  }

  function replaceLastStatus(text: string) {
    setMessages(prev => {
      const last = [...prev].reverse().find(m => m.type === 'status')
      if (!last) return [...prev, { id: nextId(), role: 'assistant', type: 'status', content: text }]
      return prev.map(m => m.id === last.id ? { ...m, content: text } : m)
    })
  }

  // ── setup pipeline ─────────────────────────────────────────────────────────

  async function handleStart(q: string) {
    if (!q.trim()) return
    setDomain(q.trim())
    setPhase('setup')
    setError(null)
    setMessages([])

    let analysisId = ''

    try {
      for await (const event of startConversation(q.trim())) {
        const type = event.type as string

        if (type === 'status') {
          replaceLastStatus(event.message as string)

        } else if (type === 'search_done') {
          setSessionId(event.session_id as string)
          replaceLastStatus(
            `Found ${event.patent_count} patents and ${event.paper_count} papers. Building knowledge base…`
          )

        } else if (type === 'analysis_start') {
          analysisId = nextId()
          addMsg({ id: analysisId, role: 'assistant', type: 'analysis', content: '', streaming: true })

        } else if (type === 'analysis_chunk') {
          appendToMsg(analysisId, event.content as string)

        } else if (type === 'analysis_done') {
          finaliseMsg(analysisId)

        } else if (type === 'ideas_status') {
          replaceLastStatus(event.message as string)

        } else if (type === 'ideas_done') {
          const ideas = event.ideas as Idea[]
          addMsg({ id: nextId(), role: 'assistant', type: 'ideas', content: '', ideas })
          addMsg({
            id: nextId(),
            role: 'assistant',
            type: 'text',
            content:
              `I found **${ideas.length} innovation gaps** in the ${q.trim()} patent landscape.\n\n` +
              'Which of these interests you? Or describe your own concept and I\'ll check it against the existing patents.',
          })

        } else if (type === 'ready') {
          setPhase('chat')
          setTimeout(() => chatInputRef.current?.focus(), 100)

        } else if (type === 'error') {
          setError(event.message as string)
          setPhase('landing')
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Setup failed')
      setPhase('landing')
    }
  }

  // ── chat ───────────────────────────────────────────────────────────────────

  async function sendMessage(text: string) {
    if (!sessionId || !text.trim() || responding) return
    const trimmed = text.trim()
    setChatInput('')
    setError(null)
    addMsg({ id: nextId(), role: 'user', type: 'text', content: trimmed })

    const replyId = nextId()
    addMsg({ id: replyId, role: 'assistant', type: 'text', content: '', streaming: true })
    setResponding(true)

    try {
      for await (const event of streamChat(sessionId, trimmed)) {
        if (event.error) { setError(event.error as string); break }
        if (event.content) appendToMsg(replyId, event.content as string)
        if (event.done) finaliseMsg(replyId)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Chat failed')
    } finally {
      setResponding(false)
      setTimeout(() => chatInputRef.current?.focus(), 50)
    }
  }

  function handleReset() {
    setPhase('landing')
    setMessages([])
    setSessionId(null)
    setDomain('')
    setQueryInput('')
    setError(null)
    setChatInput('')
  }

  // ── rendering helpers ──────────────────────────────────────────────────────

  function toggleExpand(id: string) {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function renderMessage(msg: ConvMessage) {
    if (msg.role === 'user') {
      return (
        <div key={msg.id} className="flex justify-end">
          <div className="max-w-[75%] rounded-2xl rounded-tr-sm bg-indigo-600 px-4 py-2.5 text-sm text-white">
            {msg.content}
          </div>
        </div>
      )
    }

    if (msg.type === 'status') {
      return (
        <div key={msg.id} className="flex items-center gap-2 text-gray-500 text-xs pl-1 py-0.5">
          <span className="flex gap-1">
            <span className="w-1 h-1 bg-gray-600 rounded-full animate-bounce [animation-delay:0ms]" />
            <span className="w-1 h-1 bg-gray-600 rounded-full animate-bounce [animation-delay:150ms]" />
            <span className="w-1 h-1 bg-gray-600 rounded-full animate-bounce [animation-delay:300ms]" />
          </span>
          {msg.content}
        </div>
      )
    }

    if (msg.type === 'analysis') {
      const isOpen = expanded.has(msg.id)
      const { thinking, response } = parseThinking(msg.content)
      return (
        <div key={msg.id} className="rounded-2xl bg-gray-900 border border-gray-700 overflow-hidden">
          <button
            onClick={() => toggleExpand(msg.id)}
            className="w-full flex items-center justify-between px-4 py-3 text-sm text-gray-300 hover:bg-gray-800/50 transition-colors"
          >
            <span className="flex items-center gap-2 font-medium">
              <svg className="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
              </svg>
              Patent Landscape Map
              {msg.streaming && <span className="text-xs text-indigo-400 font-normal">analyzing…</span>}
            </span>
            <svg
              className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {isOpen && (
            <div className="px-4 pb-4">
              <ThinkingBlock text={thinking} />
              <div className="prose-patent text-sm">
                <ReactMarkdown>{response || msg.content}</ReactMarkdown>
                {msg.streaming && (
                  <span className="inline-block w-1.5 h-4 bg-indigo-400 animate-pulse ml-0.5 align-text-bottom" />
                )}
              </div>
            </div>
          )}
        </div>
      )
    }

    if (msg.type === 'ideas') {
      return (
        <div key={msg.id} className="space-y-2">
          {(msg.ideas ?? []).map((idea, i) => (
            <div
              key={i}
              className="rounded-xl bg-gray-900 border border-gray-700 hover:border-gray-600 p-4 transition-colors"
            >
              <div className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-900 border border-indigo-700 text-indigo-300 text-xs flex items-center justify-center font-bold mt-0.5">
                  {i + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-white">{idea.title}</p>
                  <p className="text-xs text-gray-400 mt-0.5">{idea.tagline}</p>
                  {idea.key_innovation && (
                    <p className="text-xs text-gray-500 mt-1.5">
                      <span className="text-gray-400 font-medium">Novel: </span>
                      {idea.key_innovation}
                    </p>
                  )}
                  <button
                    onClick={() => sendMessage(`Tell me more about idea ${i + 1}: ${idea.title}`)}
                    disabled={responding}
                    className="mt-2 text-xs text-indigo-400 hover:text-indigo-300 disabled:opacity-40 transition-colors"
                  >
                    Explore this →
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )
    }

    // type === 'text' (regular assistant message)
    const { thinking, response } = parseThinking(msg.content)
    return (
      <div key={msg.id} className="flex justify-start">
        <div className="max-w-[85%]">
          <ThinkingBlock text={thinking} />
          <div className="rounded-2xl rounded-tl-sm bg-gray-800 px-4 py-3">
            <ReactMarkdown className="prose-patent text-sm">
              {response || msg.content}
            </ReactMarkdown>
            {msg.streaming && !msg.content && (
              <span className="flex gap-1">
                <span className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce [animation-delay:300ms]" />
              </span>
            )}
            {msg.streaming && msg.content && (
              <span className="inline-block w-1.5 h-4 bg-gray-400 animate-pulse ml-0.5 align-text-bottom" />
            )}
          </div>
        </div>
      </div>
    )
  }

  // ── landing ────────────────────────────────────────────────────────────────

  if (phase === 'landing') {
    return (
      <div className="flex flex-col items-center justify-center min-h-[70vh] px-4">
        <div className="w-full max-w-2xl">
          <div className="text-center mb-10">
            <h1 className="text-4xl font-bold text-white mb-3">
              FTO & Patent Landscape Scout
            </h1>
            <p className="text-gray-400 text-lg">
              Describe a device concept or technology area. I'll search US and EPO/PCT patents, map what's covered, and generate a structured FTO brief you can hand to counsel.
            </p>
          </div>

          {/* Concept input */}
          <div className="relative">
            <textarea
              value={queryInput}
              onChange={e => setQueryInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleStart(queryInput)
                }
              }}
              placeholder="Describe your design concept or technology area — e.g. resorbable spinal cage with antibiotic elution…"
              rows={3}
              className="w-full rounded-2xl bg-gray-800 border border-gray-600 px-5 py-4 text-gray-100 placeholder-gray-500 text-base resize-none focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors"
            />
            <button
              onClick={() => handleStart(queryInput)}
              disabled={!queryInput.trim()}
              className="absolute bottom-3 right-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-xl px-4 py-2 text-sm font-semibold transition-colors flex items-center gap-2"
            >
              Start
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </button>
          </div>

          {error && (
            <div className="mt-3 rounded-xl bg-red-950/50 border border-red-700 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

          <div className="mt-6">
            <p className="text-xs text-gray-500 mb-3 text-center">Try an example</p>
            <div className="flex flex-wrap gap-2 justify-center">
              {EXAMPLES.map(ex => (
                <button
                  key={ex}
                  onClick={() => { setQueryInput(ex); handleStart(ex) }}
                  className="text-xs px-3 py-1.5 rounded-full bg-gray-800 border border-gray-600 text-gray-300 hover:border-indigo-500 hover:text-indigo-300 transition-colors"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    )
  }

  // ── setup + chat (shared conversation view) ────────────────────────────────

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 flex flex-col" style={{ height: 'calc(100vh - 3.5rem)' }}>
      {/* Domain header */}
      <div className="flex-shrink-0 mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white">{domain}</h2>
          {phase === 'setup' && (
            <p className="text-xs text-indigo-400 mt-0.5">Setting up your patent advisor…</p>
          )}
          {phase === 'chat' && (
            <p className="text-xs text-gray-500 mt-0.5">
              {sessionId ? `Session ready · ${messages.filter(m => m.type === 'ideas').flatMap(m => m.ideas ?? []).length} opportunities found` : ''}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          {phase === 'chat' && (
            <button
              onClick={() => window.print()}
              className="text-xs text-gray-500 hover:text-gray-300 transition-colors flex items-center gap-1"
              title="Print / export as PDF"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
              </svg>
              Export
            </button>
          )}
          <button
            onClick={handleReset}
            className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
          >
            New search
          </button>
        </div>
      </div>

      {error && (
        <div className="flex-shrink-0 mb-3 rounded-xl bg-red-950/50 border border-red-700 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Message thread */}
      <div className="flex-1 overflow-y-auto space-y-4 pb-4 min-h-0">
        {messages.map(renderMessage)}
        <div ref={bottomRef} />
      </div>

      {/* Chat input — shown once setup is done */}
      {phase === 'chat' && (
        <div className="flex-shrink-0 pt-3 border-t border-gray-800">
          <div className="relative">
            <textarea
              ref={chatInputRef}
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  sendMessage(chatInput)
                }
              }}
              placeholder="Describe your design concept for an FTO check, or ask about the patent landscape…"
              rows={2}
              disabled={responding}
              className="w-full rounded-2xl bg-gray-800 border border-gray-600 px-4 py-3 pr-14 text-gray-100 placeholder-gray-500 text-sm resize-none focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 disabled:opacity-50 transition-colors"
            />
            <button
              onClick={() => sendMessage(chatInput)}
              disabled={responding || !chatInput.trim()}
              className="absolute right-3 bottom-3 w-8 h-8 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 text-white flex items-center justify-center transition-colors"
            >
              {responding ? (
                <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
                </svg>
              )}
            </button>
          </div>
          <p className="mt-1.5 text-xs text-gray-600 text-center">
            Describe a concept for an FTO check with citations and confidence levels · US + EPO/PCT patents loaded
          </p>
        </div>
      )}
    </div>
  )
}
