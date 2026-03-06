import { configureStore } from '@reduxjs/toolkit'
import interactionReducer from '../slices/interactionSlice'
import agentReducer from '../slices/agentSlice'
import hcpReducer from '../slices/hcpSlice'

export const store = configureStore({
  reducer: {
    interaction: interactionReducer,
    agent: agentReducer,
    hcp: hcpReducer,
  },
})
