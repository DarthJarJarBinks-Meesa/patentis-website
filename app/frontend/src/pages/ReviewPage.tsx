import { useStore } from '../store'
import PatentCard from '../components/PatentCard'
import PaperCard from '../components/PaperCard'
import { updateSelection } from '../api/client'

export default function ReviewPage() {
  const {
    sessionId,
    query,
    patents,
    papers,
    selectedPatentIds,
    selectedPaperIds,
    keywords,
    togglePatent,
    togglePaper,
    setStep,
    setLoading,
    setError,
    error,
    isLoading,
  } = useStore()

  const kw = keywords as { keywords?: string[]; cpc_hints?: string[] }

  const handleProceed = async () => {
    if (!sessionId) return
    setLoading(true, 'Saving selection…')
    setError(null)
    try {
      await updateSelection(sessionId, [...selectedPatentIds], [...selectedPaperIds])
      setStep(3)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save selection')
    } finally {
      setLoading(false)
    }
  }

  const totalSelected = selectedPatentIds.size + selectedPaperIds.size

  return (
    <div className="max-w-5xl mx-auto px-4 py-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-white mb-1">Review Sources</h2>
        <p className="text-gray-400 text-sm">
          Query: <span className="text-gray-200 italic">"{query}"</span>
        </p>
        {kw.keywords && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {kw.keywords.map((k: string) => (
              <span key={k} className="text-xs px-2 py-0.5 rounded-full bg-gray-800 border border-gray-600 text-gray-400">
                {k}
              </span>
            ))}
          </div>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-xl bg-red-950/50 border border-red-700 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Patents */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">
              Patents ({patents.length})
            </h3>
            <span className="text-xs text-gray-500">{selectedPatentIds.size} selected</span>
          </div>
          <div className="space-y-3 max-h-[60vh] overflow-y-auto pr-1">
            {patents.length === 0 ? (
              <p className="text-sm text-gray-500 italic">No patents found.</p>
            ) : (
              patents.map((p) => (
                <PatentCard
                  key={p.id}
                  patent={p}
                  selected={selectedPatentIds.has(p.id)}
                  onToggle={() => togglePatent(p.id)}
                />
              ))
            )}
          </div>
        </div>

        {/* Papers */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">
              Research Papers ({papers.length})
            </h3>
            <span className="text-xs text-gray-500">{selectedPaperIds.size} selected</span>
          </div>
          <div className="space-y-3 max-h-[60vh] overflow-y-auto pr-1">
            {papers.length === 0 ? (
              <p className="text-sm text-gray-500 italic">No papers found.</p>
            ) : (
              papers.map((p) => (
                <PaperCard
                  key={p.id}
                  paper={p}
                  selected={selectedPaperIds.has(p.id)}
                  onToggle={() => togglePaper(p.id)}
                />
              ))
            )}
          </div>
        </div>
      </div>

      <div className="mt-6 flex items-center justify-between">
        <button
          onClick={() => setStep(1)}
          className="text-sm text-gray-400 hover:text-gray-200 transition-colors"
        >
          ← Back to search
        </button>
        <button
          onClick={handleProceed}
          disabled={isLoading || totalSelected === 0}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-xl px-6 py-2.5 text-sm font-semibold transition-colors flex items-center gap-2"
        >
          {isLoading ? 'Saving…' : `Analyze ${totalSelected} documents →`}
        </button>
      </div>
    </div>
  )
}
