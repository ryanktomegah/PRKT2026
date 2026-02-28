import { create } from 'zustand'
import type { HealthResponse, ScoreResponse, PriceResponse, ExecuteResponse } from './api'

export interface PortfolioItem {
  id: string
  timestamp: Date
  scoreResult: ScoreResponse
  priceResult?: PriceResponse
  executeResult?: ExecuteResponse
}

interface ALBSStore {
  health: HealthResponse | null
  setHealth: (health: HealthResponse | null) => void
  portfolio: PortfolioItem[]
  addPortfolioItem: (item: PortfolioItem) => void
  clearPortfolio: () => void
}

export const useALBSStore = create<ALBSStore>((set) => ({
  health: null,
  setHealth: (health) => set({ health }),
  portfolio: [],
  addPortfolioItem: (item) =>
    set((state) => ({ portfolio: [...state.portfolio, item] })),
  clearPortfolio: () => set({ portfolio: [] }),
}))
