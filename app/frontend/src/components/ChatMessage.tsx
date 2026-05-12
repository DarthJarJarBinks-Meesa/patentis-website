import ReactMarkdown from 'react-markdown'
import ThinkingBlock from './ThinkingBlock'
import type { ChatMessage as Msg } from '../types'

function parseThinking(text: string): { thinking: string; response: string } {
  const match = text.match(/<think>([\s\S]*?)<\/think>/i)
  const thinking = match ? match[1].trim() : ''
  const response = text.replace(/<think>[\s\S]*?<\/think>/gi, '').trim()
  return { thinking, response }
}

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
