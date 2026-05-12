import { useState } from 'react'
import { useStore } from '../store'
import { searchPatents, setGroqApiKey } from '../api/client'

const EXAMPLES = [
  'battery technology for electric vehicles',
  'AI-powered drug discovery methods',
  'carbon capture and storage materials',
  'flexible wearable biosensors',
]

export default function SearchPage() {
  const { query, setQuery, setStep, setSessionId, setResults, setKeywords, setLoading, setError, groqApiKey, setGroqApiKey: storeSetGroqApiKey } =
    useStore()
  const [inputVal, setInputVal] = useState(query)
  const [keyVisible, setKeyVisible] = useState(false)

  const handleKeyChange = (val: string) => {
    storeSetGroqApiKey(val)
    setGroqApiKey(val)
  }

  const handleSearch = async (q: string) => {
    if (!q.trim()) return
    if (!groqApiKey.trim()) {
      setError('Please enter your Groq API key above before searching.')
      return
    }
    setQuery(q)
    setLoading(true, 'Extracting keywords and searching patents…')
    setError(null)
    try {
      const data = await searchPatents(q)
      setSessionId(data.session_id)
      setResults(data.patents, data.papers)
      setKeywords(data.keywords)
      setStep(2)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed')
    } finally {
      setLoading(false)
    }
  }

  const { isLoading, loadingMessage, error } = useStore()

  return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] px-4">
      <div className="w-full max-w-2xl">
        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold text-white mb-3">
            Discover what hasn't been
            <span className="text-indigo-400"> patented yet</span>
          </h1>
          <p className="text-gray-400 text-lg">
            Describe a technology area. Patentis maps the existing patent landscape and surfaces genuine innovation gaps.
          </p>
        </div>

        <div className="mb-4">
          <label className="block text-xs text-gray-400 mb-1.5 font-medium">
            Groq API Key
            <a
              href="https://console.groq.com/keys"
              target="_blank"
              rel="noopener noreferrer"
              className="ml-2 text-indigo-400 hover:text-indigo-300 transition-colors"
            >
              Get a free key →
            </a>
          </label>
          <div className="relative">
            <input
              type={keyVisible ? 'text' : 'password'}
              value={groqApiKey}
              onChange={(e) => handleKeyChange(e.target.value)}
              placeholder="gsk_..."
              disabled={isLoading}
              className="w-full rounded-xl bg-gray-800 border border-gray-600 px-4 py-2.5 text-gray-100 placeholder-gray-600 text-sm font-mono focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 disabled:opacity-50 transition-colors pr-10"
            />
            <button
              type="button"
              onClick={() => setKeyVisible((v) => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors"
              tabIndex={-1}
            >
              {keyVisible ? (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-5 0-9-4-9-7a9.77 9.77 0 012.169-5.831M6.343 6.343A8.014 8.014 0 0112 5c5 0 9 4 9 7a9.77 9.77 0 01-1.585 3.185M15 12a3 3 0 11-6 0 3 3 0 016 0zM3 3l18 18" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
              )}
            </button>
          </div>
        </div>

        <div className="relative">
          <textarea
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSearch(inputVal)
              }
            }}
            placeholder="e.g. novel approaches to solid-state battery electrolytes…"
            rows={3}
            disabled={isLoading}
            className="w-full rounded-2xl bg-gray-800 border border-gray-600 px-5 py-4 text-gray-100 placeholder-gray-500 text-base resize-none focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 disabled:opacity-50 transition-colors"
          />
          <button
            onClick={() => handleSearch(inputVal)}
            disabled={isLoading || !inputVal.trim()}
            className="absolute bottom-3 right-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-xl px-4 py-2 text-sm font-semibold transition-colors flex items-center gap-2"
          >
            {isLoading ? (
              <>
                <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Searching
              </>
            ) : (
              <>
                Search
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </>
            )}
          </button>
        </div>

        {isLoading && loadingMessage && (
          <p className="mt-3 text-sm text-indigo-400 text-center">{loadingMessage}</p>
        )}

        {error && (
          <div className="mt-3 rounded-xl bg-red-950/50 border border-red-700 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        <div className="mt-6">
          <p className="text-xs text-gray-500 mb-3 text-center">Try an example</p>
          <div className="flex flex-wrap gap-2 justify-center">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                onClick={() => {
                  setInputVal(ex)
                  handleSearch(ex)
                }}
                disabled={isLoading}
                className="text-xs px-3 py-1.5 rounded-full bg-gray-800 border border-gray-600 text-gray-300 hover:border-indigo-500 hover:text-indigo-300 transition-colors disabled:opacity-40"
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
