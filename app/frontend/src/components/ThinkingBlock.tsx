import { useState } from 'react'

interface Props {
  text: string
}

export default function ThinkingBlock({ text }: Props) {
  const [open, setOpen] = useState(false)

  if (!text.trim()) return null

  return (
    <div className="mb-3 rounded-lg border border-gray-700 bg-gray-800/50 overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-gray-400 hover:text-gray-300 transition-colors"
      >
        <svg
          className={`w-3 h-3 transition-transform ${open ? 'rotate-90' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        <span className="font-medium">Model reasoning</span>
        <span className="ml-auto text-gray-500">{open ? 'hide' : 'show'}</span>
      </button>
      {open && (
        <div className="px-3 pb-3 text-xs text-gray-500 font-mono leading-relaxed border-t border-gray-700 pt-2 whitespace-pre-wrap max-h-64 overflow-y-auto">
          {text}
        </div>
      )}
    </div>
  )
}
