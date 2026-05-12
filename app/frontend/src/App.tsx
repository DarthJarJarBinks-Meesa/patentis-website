import StepIndicator from './components/StepIndicator'
import SearchPage from './pages/SearchPage'
import ReviewPage from './pages/ReviewPage'
import AnalysisPage from './pages/AnalysisPage'
import IdeasPage from './pages/IdeasPage'
import GuidancePage from './pages/GuidancePage'
import { useStore } from './store'

export default function App() {
  const { step, reset } = useStore()

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="flex-shrink-0 border-b border-gray-800 bg-gray-950/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
          <button
            onClick={reset}
            className="flex items-center gap-2 font-bold text-lg text-white hover:text-indigo-300 transition-colors"
          >
            <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            Patentis
          </button>

          {step > 1 && (
            <StepIndicator current={step} />
          )}

          {step > 1 && (
            <button
              onClick={reset}
              className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              New search
            </button>
          )}
        </div>
      </header>

      {/* Page */}
      <main className="flex-1">
        {step === 1 && <SearchPage />}
        {step === 2 && <ReviewPage />}
        {step === 3 && <AnalysisPage />}
        {step === 4 && <IdeasPage />}
        {step === 5 && <GuidancePage />}
      </main>
    </div>
  )
}
