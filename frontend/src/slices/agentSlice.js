import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import { v4 as uuidv4 } from 'uuid'
import { sendChatMessage as apiSendChat } from '../services/agentService'
import { patchFromAI } from './interactionSlice'

// ─────────────────────────────────────────────────────────────────
// Async thunk: send a chat message and auto-fill the form
//
// Dispatches patchFromAI automatically when the backend returns
// extracted_fields — components don't need to do it manually.
// ─────────────────────────────────────────────────────────────────
export const sendMessage = createAsyncThunk(
  'agent/sendMessage',
  async ({ text, sessionId }, { dispatch, rejectWithValue }) => {
    try {
      const data = await apiSendChat(text, sessionId)

      // Auto-fill the interaction form whenever fields are extracted
      if (data.extracted_fields && Object.keys(data.extracted_fields).length > 0) {
        dispatch(patchFromAI(data.extracted_fields))
      }

      return {
        reply: data.reply || data.message || 'Done.',
        extractedFields: data.extracted_fields || null,
        intent: data.intent || null,
        actionTaken: data.action_taken || null,
      }
    } catch (err) {
      const detail =
        err.response?.data?.detail ||
        err.message ||
        'Could not reach the AI assistant.'
      return rejectWithValue(detail)
    }
  }
)

// ─────────────────────────────────────────────────────────────────
// Slice
// ─────────────────────────────────────────────────────────────────
const agentSlice = createSlice({
  name: 'agent',
  initialState: {
    // Persistent session UUID — survives re-renders, resets on page reload
    sessionId: uuidv4(),

    // Full conversation history
    // Shape: { id, role: 'user'|'assistant', content, timestamp, extractedFields? }
    messages: [],

    // Last successfully extracted field set (used for field-highlight state)
    lastExtracted: null,

    // Most recent classified intent from the backend
    lastIntent: null,

    // Async state
    loading: false,
    error: null,
  },
  reducers: {
    // Allow the user to manually add an assistant message (e.g. welcome message)
    addSystemMessage(state, action) {
      state.messages.push({
        id: uuidv4(),
        role: 'assistant',
        content: action.payload,
        timestamp: new Date().toISOString(),
        extractedFields: null,
      })
    },
    clearError(state) {
      state.error = null
    },
    clearChat(state) {
      state.messages = []
      state.lastExtracted = null
      state.lastIntent = null
      state.error = null
    },
    // Reset session (new conversation, new UUID)
    newSession(state) {
      state.sessionId = uuidv4()
      state.messages = []
      state.lastExtracted = null
      state.lastIntent = null
      state.error = null
    },
  },

  // ── sendMessage async thunk lifecycle ─────────────────────────
  extraReducers: (builder) => {
    builder
      .addCase(sendMessage.pending, (state, action) => {
        state.loading = true
        state.error = null
        // Add the user message optimistically
        state.messages.push({
          id: uuidv4(),
          role: 'user',
          content: action.meta.arg.text,
          timestamp: new Date().toISOString(),
          extractedFields: null,
        })
      })
      .addCase(sendMessage.fulfilled, (state, action) => {
        state.loading = false
        const { reply, extractedFields, intent, actionTaken } = action.payload

        // Add assistant reply
        state.messages.push({
          id: uuidv4(),
          role: 'assistant',
          content: reply,
          timestamp: new Date().toISOString(),
          extractedFields,
          intent,
          actionTaken,
        })

        if (extractedFields) state.lastExtracted = extractedFields
        if (intent) state.lastIntent = intent
      })
      .addCase(sendMessage.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload

        // Add an error message to the chat so the user sees it inline
        state.messages.push({
          id: uuidv4(),
          role: 'assistant',
          content: `⚠️ ${action.payload}`,
          timestamp: new Date().toISOString(),
          extractedFields: null,
          isError: true,
        })
      })
  },
})

export const { addSystemMessage, clearError, clearChat, newSession } = agentSlice.actions
export default agentSlice.reducer
