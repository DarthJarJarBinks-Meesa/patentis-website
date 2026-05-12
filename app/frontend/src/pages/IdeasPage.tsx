import { useState } from 'react'
import IdeaCard from '../components/IdeaCard'
import ThinkingBlock from '../components/ThinkingBlock'
import { useStore } from '../store'
import { streamSelectIdea } from '../api/client'

function parseThinking(text: string): { thinking: string; response: string } {
  const match = text.match(/<think>([\s\S]*?)<\/think>/i)
  const thinking = match ? match[1].trim() : ''
  const response = text.replace(/<think>[\s\S]*?<\/think>/gi, '').trim()
  return { thinking, response }
}

export default function IdeasPage() {
  const {
    sessionId,
    ideas,
    selectedIdeaIndex,
    selectIdea,
    infringementCheck,
    appendInfringementCheck,
    setInfringementCheck,
    setStep,
    setError,
    error,
  } = useStore()

  const [checkStreaming, setCheckStreaming] = useState(false)
  const [checkDone, setCheckDone] = useState(!!infringementCheck)

  const handleSelect = async (index: number) => {
    if (!sessionId || index === selectedIdeaIndex) return
    selectIdea(index)
    setInfringementCheck('')
    setCheckDone(false)
    setCheckStreaming(true)
    setError(null)

    try {
      for await (const event of streamSelectIdea(sessionId, index)) {
        if (event.error) { setError(event.error); break }
        if (event.content) appendInfringementCheck(event.content)
        if (event.done) setCheckDone(true)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Infringement check failed')
    } finally {
      setCheckStreaming(false)
    }
  }

  const { thinking, response } = parseThinking(infringementCheck)

  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-white">Innovation Ideas</h2>
        <p className="text-gray-400 text-sm mt-1">
          Select an idea to run a patent infringement check and begin development guidance.
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-xl bg-red-950/50 border border-red-700 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="space-y-4 mb-6">
        {ideas.map((idea, i) => (
          <IdeaCard
            key={i}
            idea={idea}
            index={i}
            selected={selectedIdeaIndex === i}
            onSelect={() => handleSelect(i)}
          />
        ))}
      </div>

      {(infringementCheck || checkStreaming) && (
        <div className="rounded-2xl bg-gray-900 border border-gray-700 p-6 mb-6">
          <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wide mb-4 flex items-center gap-2">
            <svg className="w-4 h-4 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            Infringement Assessment
          </h3>
          {checkStreaming && !infringementCheck && (
            <div className="flex items-center gap-3 text-gray-400 text-sm">
              <svg className="animate-spin w-4 h-4 text-yellow-400" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Reviewing patents for conflicts…
            </div>
          )}
          {infringementCheck && (
            <>
              <ThinkingBlock text={thinking} />
              <div className="prose-patent text-sm whitespace-pre-wrap">
                {response || infringementCheck}
                {checkStreaming && (
                  <span className="inline-block w-1.5 h-4 bg-yellow-400 animate-pulse ml-0.5 align-text-bottom" />
                )}
              </div>
            </>
          )}
        </div>
      )}

      <div className="flex items-center justify-between">
        <button
          onClick={() => setStep(3)}
          className="text-sm text-gray-400 hover:text-gray-200 transition-colors"
        >
          ← Back to analysis
        </button>
        <button
          onClick={() => setStep(5)}
          disabled={!checkDone || selectedIdeaIndex === null}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-xl px-6 py-2.5 text-sm font-semibold transition-colors"
        >
          Start Development Guide →
        </button>
      </div>
    </div>
  )
}
