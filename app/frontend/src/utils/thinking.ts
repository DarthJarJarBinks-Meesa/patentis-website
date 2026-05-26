export function parseThinking(text: string): { thinking: string; response: string } {
  const match = text.match(/<think>([\s\S]*?)<\/think>/i)
  const thinking = match ? match[1].trim() : ''
  const response = text.replace(/<think>[\s\S]*?<\/think>/gi, '').trim()
  return { thinking, response }
}
