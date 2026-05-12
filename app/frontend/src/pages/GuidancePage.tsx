import { useEffect, useRef, useState } from 'react'
import ChatMessage from '../components/ChatMessage'
import { useStore } from '../store'
import { streamChat } from '../api/client'

const STARTER_PROMPTS = [
  'What should be my first steps to develop this idea?',
  'What technical challenges should I anticipate?',
  'Which research labs or academic groups are working in this space?',
  'What does a realistic development roadmap look like?',
  'How should I structure the patent application?',
]

export default function GuidancePage() {
  const {
    sessionId,
    ideas,
    selectedIdeaIndex,
    messages,
    addMessage,
    appendLastAssistant,
    setStep,
    setError,
    error,
  } = useStore()

  const [input, setInput] = useState('')
  const [responding, setResponding] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const selectedIdea = selectedIdeaIndex !== null ? ideas[selectedIdeaIndex] : null

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async (text: string) => {
    if (!sessionId || !text.trim() || responding) return
    const trimmed = text.trim()
    setInput('')
    setError(null)
    addMessage({ role: 'user', content: trimmed })
    setResponding(true)

    try {
      for await (const event of streamChat(sessionId, trimmed)) {
        if (event.error) { setError(event.error); break }
        if (event.content) appendLastAssistant(event.content)
        if (event.done) break
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Chat failed')
    } finally {
      setResponding(false)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 flex flex-col h-[calc(100vh-10rem)]">
      {/* Header */}
      <div className="mb-4 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-white">Development Guide</h2>
            {selectedIdea && (
              <p className="text-indigo-300 text-sm mt-0.5 font-medium">{selectedIdea.title}</p>
            )}
          </div>
          <button
            onClick={() => setStep(4)}
            className="text-sm text-gray-400 hover:text-gray-200 transition-colors"
          >
            ← Back to ideas
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-3 rounded-xl bg-red-950/50 border border-red-700 px-4 py-3 text-sm text-red-300 flex-shrink-0">
          {error}
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 pb-4 min-h-0">
        {messages.length === 0 && (
          <div className="space-y-4">
            <div className="rounded-2xl bg-gray-800/50 border border-gray-700 p-4 text-sm text-gray-300">
              <p className="font-medium text-gray-100 mb-1">Ready to help you build.</p>
              <p className="text-gray-400">
                Ask me anything about developing <span className="text-indigo-300">{selectedIdea?.title}</span>. I have full context of the patent landscape and infringement analysis.
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-2">Suggested questions</p>
              <div className="flex flex-col gap-2">
                {STARTER_PROMPTS.map((p) => (
                  <button
                    key={p}
                    onClick={() => sendMessage(p)}
                    disabled={responding}
                    className="text-left text-sm px-4 py-2.5 rounded-xl bg-gray-800 border border-gray-700 text-gray-300 hover:border-indigo-500 hover:text-indigo-300 transition-colors disabled:opacity-40"
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <ChatMessage key={i} message={msg} />
        ))}

        {responding && messages[messages.length - 1]?.role === 'user' && (
          <div className="flex items-center gap-2 text-gray-500 text-sm pl-1">
            <span className="flex gap-1">
              <span className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce [animation-delay:0ms]" />
              <span className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce [animation-delay:150ms]" />
              <span className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce [animation-delay:300ms]" />
            </span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex-shrink-0 pt-3 border-t border-gray-800">
        <div className="relative">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                sendMessage(input)
              }
            }}
            placeholder="Ask anything about developing your idea…"
            rows={2}
            disabled={responding}
            className="w-full rounded-2xl bg-gray-800 border border-gray-600 px-4 py-3 pr-14 text-gray-100 placeholder-gray-500 text-sm resize-none focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 disabled:opacity-50 transition-colors"
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={responding || !input.trim()}
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
          Powered by llama3.2 · Patent context from your selected documents
        </p>
      </div>
    </div>
  )
}
