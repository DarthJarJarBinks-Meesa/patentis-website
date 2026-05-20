import ReactMarkdown from 'react-markdown'
import ThinkingBlock from './ThinkingBlock'
import type { ChatMessage as Msg } from '../types'
import { parseThinking } from '../utils/thinking'

export default function ChatMessage({ message }: { message: Msg }) {
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
          <ReactMarkdown className="prose-patent text-sm">{response || message.content}</ReactMarkdown>
        </div>
      </div>
    </div>
  )
}
