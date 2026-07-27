import PatentMarkdown from './PatentMarkdown'
import ThinkingBlock from './ThinkingBlock'
import type { ChatMessage as Msg, Patent, Paper } from '../types'
import { parseThinking } from '../utils/thinking'

export default function ChatMessage({
  message,
  patents,
  papers,
}: {
  message: Msg
  patents?: Patent[]
  papers?: Paper[]
}) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] rounded-2xl rounded-tr-sm bg-indigo-600 px-4 py-2.5 text-sm text-white">
          {message.content}
        </div>
      </div>
    )
  }

  const { thinking, response } = parseThinking(message.content)

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%]">
        <ThinkingBlock text={thinking} />
        <div className="rounded-2xl rounded-tl-sm bg-gray-800 px-4 py-3">
          <PatentMarkdown
            className="prose-patent text-sm"
            text={response || message.content}
            patents={patents}
            papers={papers}
          />
        </div>
      </div>
    </div>
  )
}
