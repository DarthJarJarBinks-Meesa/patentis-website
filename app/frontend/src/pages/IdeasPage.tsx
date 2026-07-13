import { useState } from 'react'
import IdeaCard from '../components/IdeaCard'
import ThinkingBlock from '../components/ThinkingBlock'
import { useStore } from '../store'
import { streamSelectIdea, streamEvaluateIdea } from '../api/client'
import { parseThinking } from '../utils/thinking'

export default function IdeasPage() {
  const {
    sessionId,
    ideas,
    selectedIdeaIndex,
    selectIdea,
    userIdea,
    setUserIdea,
    ideaMode,
    setIdeaMode,
    infringementCheck,
    appendInfringementCheck,
    setInfringementCheck,
    setStep,
    setError,
    error,
  } = useStore()

  const [checkStreaming, setCheckStreaming] = useState(false)
  const [checkDone, setCheckDone] = useState(!!infringementCheck)

  // "Evaluate My Idea" form state
  const [myTitle, setMyTitle] = useState(userIdea?.title ?? '')
  const [myDescription, setMyDescription] = useState(userIdea?.description ?? '')

  const handleSelectAiIdea = async (index: number) => {
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

  const handleEvaluateMyIdea = async () => {
    if (!sessionId || !myTitle.trim() || !myDescription.trim()) return
    setUserIdea({ title: myTitle.trim(), description: myDescription.trim() })
    setInfringementCheck('')
    setCheckDone(false)
    setCheckStreaming(true)
    setError(null)

    try {
      for await (const event of streamEvaluateIdea(sessionId, myTitle.trim(), myDescription.trim())) {
        if (event.error) { setError(event.error); break }
        if (event.content) appendInfringementCheck(event.content)
        if (event.done) setCheckDone(true)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Evaluation failed')
    } finally {
      setCheckStreaming(false)
    }
  }

  const { thinking, response } = parseThinking(infringementCheck)

  const canProceed =
    checkDone &&
    (ideaMode === 'generate' ? selectedIdeaIndex !== null : !!userIdea)

  return (
    <div className="max-w-4xl mx-auto px-4 py-6">

      {/* Mode tabs */}
      <div className="mb-6 flex items-center gap-1 bg-gray-900 border border-gray-700 rounded-xl p-1 w-fit">
        <button
          onClick={() => { setIdeaMode('generate'); setCheckDone(false) }}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            ideaMode === 'generate'
              ? 'bg-indigo-600 text-white'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          AI-Generated Ideas
        </button>
        <button
          onClick={() => { setIdeaMode('evaluate'); setCheckDone(false) }}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            ideaMode === 'evaluate'
              ? 'bg-indigo-600 text-white'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          Evaluate My Idea
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-xl bg-red-950/50 border border-red-700 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* AI-generated ideas panel */}
      {ideaMode === 'generate' && (
        <>
          <div className="mb-2">
            <h2 className="text-2xl font-bold text-white">Innovation Ideas</h2>
            <p className="text-gray-400 text-sm mt-1">
              Select an idea to run a patent conflict check, then continue to development guidance.
            </p>
          </div>
          {ideas.length === 0 ? (
            <div className="rounded-2xl bg-gray-900 border border-gray-700 p-8 text-center text-gray-500 text-sm mb-6">
              No ideas generated yet. Go back to analysis and click "Generate Ideas".
            </div>
          ) : (
            <div className="space-y-4 mb-6">
              {ideas.map((idea, i) => (
                <IdeaCard
                  key={i}
                  idea={idea}
                  index={i}
                  selected={selectedIdeaIndex === i}
                  onSelect={() => handleSelectAiIdea(i)}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* Evaluate my idea panel */}
      {ideaMode === 'evaluate' && (
        <>
          <div className="mb-4">
            <h2 className="text-2xl font-bold text-white">Evaluate My Idea</h2>
            <p className="text-gray-400 text-sm mt-1">
              Describe your concept. We'll check it against the loaded patent corpus and flag any conflicts.
            </p>
          </div>
          <div className="rounded-2xl bg-gray-900 border border-gray-700 p-6 mb-6 space-y-4">
            <div>
              <label className="block text-xs text-gray-400 mb-1.5 font-medium">Idea title</label>
              <input
                type="text"
                value={myTitle}
                onChange={(e) => setMyTitle(e.target.value)}
                placeholder="e.g. Dynamic pedicle screw with strain-sensing feedback"
                disabled={checkStreaming}
                className="w-full rounded-xl bg-gray-800 border border-gray-600 px-4 py-2.5 text-gray-100 placeholder-gray-500 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 disabled:opacity-50 transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5 font-medium">Technical description</label>
              <textarea
                value={myDescription}
                onChange={(e) => setMyDescription(e.target.value)}
                placeholder="Describe the mechanism, materials, and how it works. The more detail you provide, the more accurate the conflict assessment."
                rows={5}
                disabled={checkStreaming}
                className="w-full rounded-xl bg-gray-800 border border-gray-600 px-4 py-3 text-gray-100 placeholder-gray-500 text-sm resize-none focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 disabled:opacity-50 transition-colors"
              />
            </div>
            <button
              onClick={handleEvaluateMyIdea}
              disabled={!myTitle.trim() || !myDescription.trim() || checkStreaming}
              className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-xl px-5 py-2.5 text-sm font-semibold transition-colors flex items-center gap-2"
            >
              {checkStreaming ? (
                <>
                  <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Checking patents…
                </>
              ) : (
                <>
                  Check for conflicts
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                  </svg>
                </>
              )}
            </button>
          </div>
        </>
      )}

      {/* Conflict check result — shared between both modes */}
      {(infringementCheck || (checkStreaming && ideaMode === 'generate' && selectedIdeaIndex !== null) || (checkStreaming && ideaMode === 'evaluate')) && (
        <div className="rounded-2xl bg-gray-900 border border-gray-700 p-6 mb-6">
          <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wide mb-4 flex items-center gap-2">
            <svg className="w-4 h-4 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            Patent Conflict Assessment
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
          disabled={!canProceed}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-xl px-6 py-2.5 text-sm font-semibold transition-colors"
        >
          Start Development Guide →
        </button>
      </div>
    </div>
  )
}
