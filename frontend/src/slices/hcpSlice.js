import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import { searchHcps as apiSearchHcps, fetchHcpHistory as apiFetchHistory } from '../services/hcpService'

// ─────────────────────────────────────────────────────────────────
// Async thunks
// ─────────────────────────────────────────────────────────────────

/** Search the HCP directory by name / specialty / hospital */
export const searchHcps = createAsyncThunk(
  'hcp/search',
  async (query, { rejectWithValue }) => {
    try {
      const data = await apiSearchHcps(query)
      return data
    } catch (err) {
      return rejectWithValue(
        err.response?.data?.detail || err.message || 'HCP search failed.'
      )
    }
  }
)

/**
 * Fetch paginated interaction history for a specific HCP.
 * @param {{ hcpId: string|number, page?: number, fromDate?: string, toDate?: string }} params
 */
export const fetchHcpHistory = createAsyncThunk(
  'hcp/fetchHistory',
  async ({ hcpId, page = 1, fromDate, toDate } = {}, { rejectWithValue }) => {
    try {
      const data = await apiFetchHistory(hcpId, { page, fromDate, toDate })
      return { ...data, hcpId, page }
    } catch (err) {
      return rejectWithValue(
        err.response?.data?.detail || err.message || 'Could not load HCP history.'
      )
    }
  }
)

// ─────────────────────────────────────────────────────────────────
// Slice
// ─────────────────────────────────────────────────────────────────
const hcpSlice = createSlice({
  name: 'hcp',
  initialState: {
    // ── HCP directory search ────────────────────────────────────
    list: [],           // HCP search results
    searchQuery: '',    // last query string (drives the search input)
    listLoading: false,
    listError: null,

    // ── Selected HCP ────────────────────────────────────────────
    // Shape: { id, name, specialty, hospital, territory, ... }
    selected: null,

    // ── Interaction history for the selected HCP ────────────────
    history: [],        // array of interaction objects
    historyMeta: {
      total: 0,
      page: 1,
      pageSize: 20,
      hasMore: false,
    },
    historyLoading: false,
    historyError: null,
    currentPage: 1,
  },

  reducers: {
    /** Select an HCP from the list — clears previous history */
    selectHcp(state, action) {
      state.selected = action.payload
      state.history = []
      state.historyMeta = { total: 0, page: 1, pageSize: 20, hasMore: false }
      state.currentPage = 1
      state.historyError = null
    },
    /** Update the controlled search-input value */
    setSearchQuery(state, action) {
      state.searchQuery = action.payload
    },
    /** Clear history + metadata without deselecting the HCP */
    clearHistory(state) {
      state.history = []
      state.historyMeta = { total: 0, page: 1, pageSize: 20, hasMore: false }
      state.currentPage = 1
      state.historyError = null
    },
    /** Completely reset the HCP state (e.g. on logout or new form) */
    resetHcp(state) {
      state.list = []
      state.searchQuery = ''
      state.listLoading = false
      state.listError = null
      state.selected = null
      state.history = []
      state.historyMeta = { total: 0, page: 1, pageSize: 20, hasMore: false }
      state.historyLoading = false
      state.historyError = null
      state.currentPage = 1
    },
    clearListError(state) {
      state.listError = null
    },
    clearHistoryError(state) {
      state.historyError = null
    },
  },

  // ── Async thunk lifecycle ─────────────────────────────────────
  extraReducers: (builder) => {
    // ── searchHcps ──────────────────────────────────────────────
    builder
      .addCase(searchHcps.pending, (state) => {
        state.listLoading = true
        state.listError = null
      })
      .addCase(searchHcps.fulfilled, (state, action) => {
        state.listLoading = false
        // Supports both { results: [] } and plain array responses
        state.list = Array.isArray(action.payload)
          ? action.payload
          : action.payload.results ?? action.payload.hcps ?? []
      })
      .addCase(searchHcps.rejected, (state, action) => {
        state.listLoading = false
        state.listError = action.payload
        state.list = []
      })

    // ── fetchHcpHistory ─────────────────────────────────────────
    builder
      .addCase(fetchHcpHistory.pending, (state) => {
        state.historyLoading = true
        state.historyError = null
      })
      .addCase(fetchHcpHistory.fulfilled, (state, action) => {
        state.historyLoading = false
        const { interactions, total, page, page_size, has_more } = action.payload

        // If loading page 1, replace; otherwise append (infinite scroll)
        if (page === 1) {
          state.history = interactions ?? []
        } else {
          state.history = [...state.history, ...(interactions ?? [])]
        }
        state.historyMeta = {
          total: total ?? state.history.length,
          page: page ?? 1,
          pageSize: page_size ?? 20,
          hasMore: has_more ?? false,
        }
        state.currentPage = page ?? 1
      })
      .addCase(fetchHcpHistory.rejected, (state, action) => {
        state.historyLoading = false
        state.historyError = action.payload
      })
  },
})

export const {
  selectHcp,
  setSearchQuery,
  clearHistory,
  resetHcp,
  clearListError,
  clearHistoryError,
} = hcpSlice.actions

export default hcpSlice.reducer
