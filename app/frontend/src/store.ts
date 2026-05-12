import { create } from 'zustand'
import type { Patent, Paper, Idea, ChatMessage, Step } from './types'

interface AppState {
  step: Step
  sessionId: string | null
  groqApiKey: string
  query: string
  keywords: Record<string, unknown>
  patents: Patent[]
  papers: Paper[]
  selectedPatentIds: Set<string>
  selectedPaperIds: Set<string>
  analysis: string
  ideas: Idea[]
  selectedIdeaIndex: number | null
  infringementCheck: string
  messages: ChatMessage[]
  isLoading: boolean
  loadingMessage: string
  error: string | null

  setStep: (step: Step) => void
  setSessionId: (id: string) => void
  setGroqApiKey: (key: string) => void
  setQuery: (q: string) => void
  setKeywords: (k: Record<string, unknown>) => void
  setResults: (patents: Patent[], papers: Paper[]) => void
  togglePatent: (id: string) => void
  togglePaper: (id: string) => void
  setAnalysis: (text: string) => void
  appendAnalysis: (chunk: string) => void
  setIdeas: (ideas: Idea[]) => void
  selectIdea: (index: number) => void
  setInfringementCheck: (text: string) => void
  appendInfringementCheck: (chunk: string) => void
  addMessage: (msg: ChatMessage) => void
  appendLastAssistant: (chunk: string) => void
  setLoading: (loading: boolean, message?: string) => void
  setError: (error: string | null) => void
  reset: () => void
}

const initialState = {
  step: 1 as Step,
  sessionId: null,
  groqApiKey: '',
  query: '',
  keywords: {},
  patents: [],
  papers: [],
  selectedPatentIds: new Set<string>(),
  selectedPaperIds: new Set<string>(),
  analysis: '',
  ideas: [],
  selectedIdeaIndex: null,
  infringementCheck: '',
  messages: [],
  isLoading: false,
  loadingMessage: '',
  error: null,
}

export const useStore = create<AppState>((set) => ({
  ...initialState,

  setStep: (step) => set({ step }),
  setSessionId: (id) => set({ sessionId: id }),
  setGroqApiKey: (key) => set({ groqApiKey: key }),
  setQuery: (q) => set({ query: q }),
  setKeywords: (k) => set({ keywords: k }),

  setResults: (patents, papers) =>
    set({
      patents,
      papers,
      selectedPatentIds: new Set(patents.map((p) => p.id)),
      selectedPaperIds: new Set(papers.map((p) => p.id)),
    }),

  togglePatent: (id) =>
    set((state) => {
      const next = new Set(state.selectedPatentIds)
      next.has(id) ? next.delete(id) : next.add(id)
      return { selectedPatentIds: next }
    }),

  togglePaper: (id) =>
    set((state) => {
      const next = new Set(state.selectedPaperIds)
      next.has(id) ? next.delete(id) : next.add(id)
      return { selectedPaperIds: next }
    }),

  setAnalysis: (text) => set({ analysis: text }),
  appendAnalysis: (chunk) => set((s) => ({ analysis: s.analysis + chunk })),

  setIdeas: (ideas) => set({ ideas }),
  selectIdea: (index) => set({ selectedIdeaIndex: index }),

  setInfringementCheck: (text) => set({ infringementCheck: text }),
  appendInfringementCheck: (chunk) =>
    set((s) => ({ infringementCheck: s.infringementCheck + chunk })),

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),

  appendLastAssistant: (chunk) =>
    set((s) => {
      const msgs = [...s.messages]
      if (msgs.length > 0 && msgs[msgs.length - 1].role === 'assistant') {
        msgs[msgs.length - 1] = {
          ...msgs[msgs.length - 1],
          content: msgs[msgs.length - 1].content + chunk,
        }
      } else {
        msgs.push({ role: 'assistant', content: chunk })
      }
      return { messages: msgs }
    }),

  setLoading: (loading, message = '') => set({ isLoading: loading, loadingMessage: message }),
  setError: (error) => set({ error }),
  reset: () => set(initialState),
}))
