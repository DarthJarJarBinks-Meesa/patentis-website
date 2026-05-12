import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import ThinkingBlock from '../components/ThinkingBlock'
import { useStore } from '../store'
import { streamAnalysis, generateIdeas } from '../api/client'

function parseThinking(text: string): { thinking: string; response: string } {
  const match = text.match(/<think>([\s\S]*?)<\/think>/i)
  const thinking = match ? match[1].trim() : ''
  const response = text.replace(/<think>[\s\S]*?<\/think>/gi, '').trim()
  return { thinking, response }
}

export default function AnalysisPage() {
  const { sessionId, analysis, appendAnalysis, setAnalysis, setIdeas, setStep, setError, error } =
    useStore()

  const [streaming, setStreaming] = useState(false)
  const [generatingIdeas, setGeneratingIdeas] = useState(false)
  const [done, setDone] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (analysis || !sessionId) return
    runAnalysis()
  }, [])

  useEffect(() => {
    if (analysis) setDone(true)
  }, [])

  const runAnalysis = async () => {
    if (!sessionId) return
    setStreaming(true)
    setDone(false)
    setAnalysis('')
    setError(null)
    try {
      for await (const event of streamAnalysis(sessionId)) {
        if (event.error) { setError(event.error); break }
        if (event.content) appendAnalysis(event.content)
        if (event.done) setDone(true)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed')
    } finally {
      setStreaming(false)
    }
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [analysis])

  const handleGenerateIdeas = async () => {
    if (!sessionId) return
    setGeneratingIdeas(true)
    setError(null)
    try {
      const data = await generateIdeas(sessionId)
      setIdeas(data.ideas)
      setStep(4)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Idea generation failed')
    } finally {
      setGeneratingIdeas(false)
    }
  }

  const { thinking, response } = parseThinking(analysis)

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Patent Landscape Analysis</h2>
          <p className="text-gray-400 text-sm mt-1">
            {streaming ? 'Analyzing with deepseek-r1…' : done ? 'Analysis complete' : ''}
          </p>
        </div>
        {done && !streaming && (
          <button
            onClick={runAnalysis}
            className="text-xs text-gray-400 hover:text-gray-200 transition-colors underline"
          >
            Re-run
          </button>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-xl bg-red-950/50 border border-red-700 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="rounded-2xl bg-gray-900 border border-gray-700 p-6 min-h-[300px]">
        {streaming && !analysis && (
          <div className="flex items-center gap-3 text-gray-400">
            <svg className="animate-spin w-5 h-5 text-indigo-400" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span className="text-sm">Reading patents and papers…</span>
          </div>
        )}

        {analysis && (
          <>
            <ThinkingBlock text={thinking} />
            <ReactMarkdown className="prose-patent">{response || analysis}</ReactMarkdown>
            {streaming && (
              <span className="inline-block w-1.5 h-4 bg-indigo-400 animate-pulse ml-0.5 align-text-bottom" />
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="mt-6 flex items-center justify-between">
        <button
          onClick={() => setStep(2)}
          className="text-sm text-gray-400 hover:text-gray-200 transition-colors"
        >
          ← Back to review
        </button>
        <button
          onClick={handleGenerateIdeas}
          disabled={!done || streaming || generatingIdeas}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-xl px-6 py-2.5 text-sm font-semibold transition-colors flex items-center gap-2"
        >
          {generatingIdeas ? (
            <>
              <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Generating ideas…
            </>
          ) : (
            'Generate Ideas →'
          )}
        </button>
      </div>
    </div>
  )
}
