import type { Step } from '../types'

const STEPS = [
  { n: 1, label: 'Search' },
  { n: 2, label: 'Review' },
  { n: 3, label: 'Analyze' },
  { n: 4, label: 'Ideas' },
  { n: 5, label: 'Develop' },
]

export default function StepIndicator({ current }: { current: Step }) {
  return (
    <div className="flex items-center gap-0">
      {STEPS.map((s, i) => {
        const done = s.n < current
        const active = s.n === current
        return (
          <div key={s.n} className="flex items-center">
            <div className="flex flex-col items-center">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-colors ${
                  done
                    ? 'bg-indigo-600 text-white'
                    : active
                      ? 'bg-indigo-500 text-white ring-2 ring-indigo-300'
                      : 'bg-gray-700 text-gray-400'
                }`}
              >
                {done ? (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  s.n
                )}
              </div>
              <span
                className={`mt-1 text-xs font-medium ${
                  active ? 'text-indigo-300' : done ? 'text-indigo-400' : 'text-gray-500'
                }`}
              >
                {s.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                className={`h-0.5 w-12 mx-1 mb-4 transition-colors ${
                  s.n < current ? 'bg-indigo-600' : 'bg-gray-700'
                }`}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
