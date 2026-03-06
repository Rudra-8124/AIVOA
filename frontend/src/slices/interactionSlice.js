import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import { logInteraction as apiLogInteraction } from '../services/agentService'

// ─────────────────────────────────────────────────────────────────
// Form shape — mirrors the backend LogInteractionInput schema
// ─────────────────────────────────────────────────────────────────
export const emptyForm = {
  hcp_name: '',
  interaction_type: 'in_person',
  interaction_date: '',
  interaction_time: '',
  attendees: '',
  topics_discussed: [],          // string[]
  materials_shared: [],          // string[]
  samples_distributed: [],       // { product_name: string, quantity: number }[]
  sentiment: 'neutral',
  outcomes: '',
  followup_actions: [],          // string[]
}

// ─────────────────────────────────────────────────────────────────
// Async thunk: submit the structured form to POST /api/interactions/log
// ─────────────────────────────────────────────────────────────────
export const submitInteraction = createAsyncThunk(
  'interaction/submit',
  async (formData, { rejectWithValue }) => {
    try {
      return await apiLogInteraction(formData)
    } catch (err) {
      const detail =
        err.response?.data?.detail ||
        err.message ||
        'Failed to save interaction.'
      return rejectWithValue(detail)
    }
  }
)

// ─────────────────────────────────────────────────────────────────
// Slice
// ─────────────────────────────────────────────────────────────────
const interactionSlice = createSlice({
  name: 'interaction',
  initialState: {
    form: { ...emptyForm },

    // Submit lifecycle
    submitting: false,
    submitError: null,
    submitSuccess: false,
    lastSavedId: null,

    // Tracks which fields were last patched by the AI (for highlight ring)
    aiPatchedFields: [],
  },
  reducers: {
    // ── Manual field edits ──────────────────────────────────────
    updateField(state, action) {
      const { field, value } = action.payload
      state.form[field] = value
      // Remove the AI highlight once the user manually edits a field
      state.aiPatchedFields = state.aiPatchedFields.filter((f) => f !== field)
    },

    // ── AI auto-fill ────────────────────────────────────────────
    // Bulk-patches the form with extracted entities from the AI.
    // Rules:
    //   • null / undefined values are skipped (never overwrite with nothing)
    //   • Array fields are only written if the array is non-empty
    //   • String fields are only written if the trimmed value is non-empty
    //   • Unknown keys (not in emptyForm) are silently ignored
    patchFromAI(state, action) {
      const extracted = action.payload
      const patched = []

      const arrayFields = ['topics_discussed', 'materials_shared', 'followup_actions']

      Object.entries(extracted).forEach(([key, value]) => {
        if (!(key in emptyForm)) return
        if (value === null || value === undefined) return

        if (arrayFields.includes(key)) {
          if (Array.isArray(value) && value.length > 0) {
            state.form[key] = value
            patched.push(key)
          }
        } else if (key === 'samples_distributed') {
          if (Array.isArray(value) && value.length > 0) {
            state.form.samples_distributed = value
            patched.push(key)
          }
        } else if (typeof value === 'string' && value.trim() !== '') {
          state.form[key] = value.trim()
          patched.push(key)
        }
      })

      state.aiPatchedFields = patched
    },

    // ── Chip (tag) list fields ──────────────────────────────────
    addChip(state, action) {
      const { field, value } = action.payload
      const trimmed = typeof value === 'string' ? value.trim() : value
      if (trimmed && !state.form[field].includes(trimmed)) {
        state.form[field].push(trimmed)
      }
    },
    removeChip(state, action) {
      const { field, index } = action.payload
      state.form[field].splice(index, 1)
    },

    // ── Samples ─────────────────────────────────────────────────
    addSample(state, action) {
      state.form.samples_distributed.push(action.payload)
    },
    removeSample(state, action) {
      state.form.samples_distributed.splice(action.payload, 1)
    },

    // ── Reset ────────────────────────────────────────────────────
    resetForm(state) {
      state.form = { ...emptyForm }
      state.submitSuccess = false
      state.submitError = null
      state.lastSavedId = null
      state.aiPatchedFields = []
    },
  },

  // ── submitInteraction async thunk lifecycle ────────────────────
  extraReducers: (builder) => {
    builder
      .addCase(submitInteraction.pending, (state) => {
        state.submitting = true
        state.submitError = null
        state.submitSuccess = false
      })
      .addCase(submitInteraction.fulfilled, (state, action) => {
        state.submitting = false
        state.submitSuccess = true
        state.lastSavedId =
          action.payload?.interaction_id ||
          action.payload?.id ||
          null
        state.aiPatchedFields = []
      })
      .addCase(submitInteraction.rejected, (state, action) => {
        state.submitting = false
        state.submitError = action.payload
      })
  },
})

export const {
  updateField,
  patchFromAI,
  addChip,
  removeChip,
  addSample,
  removeSample,
  resetForm,
} = interactionSlice.actions

export default interactionSlice.reducer
