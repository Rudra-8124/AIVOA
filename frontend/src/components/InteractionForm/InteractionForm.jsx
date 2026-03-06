import { useDispatch, useSelector } from 'react-redux'
import {
  updateField, addChip, removeChip,
  addSample, removeSample, resetForm,
  submitInteraction,
} from '../../slices/interactionSlice'
import ChipInput from '../ui/ChipInput/ChipInput'
import SampleInput from '../ui/SampleInput/SampleInput'
import SentimentBadge from '../ui/SentimentBadge/SentimentBadge'
import FieldHighlight from '../ui/FieldHighlight/FieldHighlight'
import styles from './InteractionForm.module.css'

const INTERACTION_TYPES = [
  { value: 'in_person',  label: '🤝 In Person' },
  { value: 'phone',      label: '📞 Phone' },
  { value: 'email',      label: '✉️ Email' },
  { value: 'virtual',   label: '💻 Virtual' },
]

const SENTIMENTS = [
  { value: 'positive', label: 'Positive' },
  { value: 'neutral',  label: 'Neutral'  },
  { value: 'negative', label: 'Negative' },
]

export default function InteractionForm() {
  const dispatch = useDispatch()
  const { form, submitting, submitSuccess, submitError, aiPatchedFields } = useSelector(
    (s) => s.interaction
  )

  // Fields highlighted by the AI — stored directly in Redux by patchFromAI
  const aiFilledFields = new Set(aiPatchedFields)

  const field = (name) => ({
    value: form[name],
    onChange: (e) => dispatch(updateField({ field: name, value: e.target.value })),
    aiHighlighted: aiFilledFields.has(name),
  })

  async function handleSubmit(e) {
    e.preventDefault()
    dispatch(submitInteraction(form))
  }

  return (
    <div className={styles.card}>
      {/* Card header */}
      <div className={styles.cardHeader}>
        <h2 className={styles.cardTitle}>Interaction Details</h2>
        <p className={styles.cardSubtitle}>
          Fill in the form manually or use the AI assistant to auto-fill fields.
        </p>
      </div>

      {/* Success banner */}
      {submitSuccess && (
        <div className={styles.successBanner}>
          <span>✅</span>
          <span>Interaction saved successfully!</span>
          <button className={styles.bannerClose} onClick={() => dispatch(resetForm())}>
            Log another
          </button>
        </div>
      )}

      {/* Error banner */}
      {submitError && (
        <div className={styles.errorBanner}>
          <span>❌</span>
          <span>{submitError}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className={styles.form} noValidate>
        {/* ── Row 1: HCP Name + Interaction Type ── */}
        <div className={styles.row}>
          <div className={`${styles.fieldGroup} ${styles.grow}`}>
            <label className={styles.label} htmlFor="hcp_name">
              HCP Name <span className={styles.required}>*</span>
            </label>
            <FieldHighlight active={aiFilledFields.has('hcp_name')}>
              <input
                id="hcp_name"
                type="text"
                className={styles.input}
                placeholder="e.g. Dr. Sarah Kim"
                required
                {...field('hcp_name')}
              />
            </FieldHighlight>
          </div>

          <div className={styles.fieldGroup}>
            <label className={styles.label} htmlFor="interaction_type">
              Type <span className={styles.required}>*</span>
            </label>
            <FieldHighlight active={aiFilledFields.has('interaction_type')}>
              <select
                id="interaction_type"
                className={styles.select}
                value={form.interaction_type}
                onChange={(e) => dispatch(updateField({ field: 'interaction_type', value: e.target.value }))}
              >
                {INTERACTION_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </FieldHighlight>
          </div>
        </div>

        {/* ── Row 2: Date + Time ── */}
        <div className={styles.row}>
          <div className={`${styles.fieldGroup} ${styles.grow}`}>
            <label className={styles.label} htmlFor="interaction_date">
              Date <span className={styles.required}>*</span>
            </label>
            <FieldHighlight active={aiFilledFields.has('interaction_date')}>
              <input
                id="interaction_date"
                type="date"
                className={styles.input}
                required
                {...field('interaction_date')}
              />
            </FieldHighlight>
          </div>

          <div className={`${styles.fieldGroup} ${styles.grow}`}>
            <label className={styles.label} htmlFor="interaction_time">
              Time
            </label>
            <FieldHighlight active={aiFilledFields.has('interaction_time')}>
              <input
                id="interaction_time"
                type="time"
                className={styles.input}
                {...field('interaction_time')}
              />
            </FieldHighlight>
          </div>

          <div className={`${styles.fieldGroup} ${styles.grow}`}>
            <label className={styles.label} htmlFor="attendees">
              Attendees
            </label>
            <input
              id="attendees"
              type="text"
              className={styles.input}
              placeholder="e.g. Rep, KAM"
              {...field('attendees')}
            />
          </div>
        </div>

        {/* ── Topics Discussed ── */}
        <div className={styles.fieldGroup}>
          <label className={styles.label}>Topics Discussed</label>
          <FieldHighlight active={aiFilledFields.has('topics_discussed')}>
            <ChipInput
              chips={form.topics_discussed}
              placeholder="Type a topic and press Enter…"
              onAdd={(v) => dispatch(addChip({ field: 'topics_discussed', value: v }))}
              onRemove={(i) => dispatch(removeChip({ field: 'topics_discussed', index: i }))}
            />
          </FieldHighlight>
        </div>

        {/* ── Materials Shared ── */}
        <div className={styles.fieldGroup}>
          <label className={styles.label}>Materials Shared</label>
          <FieldHighlight active={aiFilledFields.has('materials_shared')}>
            <ChipInput
              chips={form.materials_shared}
              placeholder="e.g. Cardivex brochure, clinical reprint…"
              onAdd={(v) => dispatch(addChip({ field: 'materials_shared', value: v }))}
              onRemove={(i) => dispatch(removeChip({ field: 'materials_shared', index: i }))}
            />
          </FieldHighlight>
        </div>

        {/* ── Samples Distributed ── */}
        <div className={styles.fieldGroup}>
          <label className={styles.label}>Samples Distributed</label>
          <SampleInput
            samples={form.samples_distributed}
            onAdd={(s) => dispatch(addSample(s))}
            onRemove={(i) => dispatch(removeSample(i))}
          />
        </div>

        {/* ── Sentiment ── */}
        <div className={styles.fieldGroup}>
          <label className={styles.label}>Sentiment</label>
          <FieldHighlight active={aiFilledFields.has('sentiment')}>
            <div className={styles.sentimentRow}>
              {SENTIMENTS.map((s) => (
                <button
                  key={s.value}
                  type="button"
                  className={`${styles.sentimentBtn} ${form.sentiment === s.value ? styles.sentimentActive : ''} ${styles[`sentiment_${s.value}`]}`}
                  onClick={() => dispatch(updateField({ field: 'sentiment', value: s.value }))}
                >
                  <SentimentBadge sentiment={s.value} />
                </button>
              ))}
            </div>
          </FieldHighlight>
        </div>

        {/* ── Outcomes ── */}
        <div className={styles.fieldGroup}>
          <label className={styles.label} htmlFor="outcomes">Outcomes</label>
          <FieldHighlight active={aiFilledFields.has('outcomes')}>
            <textarea
              id="outcomes"
              className={styles.textarea}
              rows={3}
              placeholder="What was agreed or accomplished?"
              value={form.outcomes}
              onChange={(e) => dispatch(updateField({ field: 'outcomes', value: e.target.value }))}
            />
          </FieldHighlight>
        </div>

        {/* ── Follow-up Actions ── */}
        <div className={styles.fieldGroup}>
          <label className={styles.label}>Follow-up Actions</label>
          <FieldHighlight active={aiFilledFields.has('followup_actions')}>
            <ChipInput
              chips={form.followup_actions}
              placeholder="e.g. Send clinical data by Friday…"
              onAdd={(v) => dispatch(addChip({ field: 'followup_actions', value: v }))}
              onRemove={(i) => dispatch(removeChip({ field: 'followup_actions', index: i }))}
            />
          </FieldHighlight>
        </div>

        {/* ── Actions ── */}
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.btnSecondary}
            onClick={() => dispatch(resetForm())}
            disabled={submitting}
          >
            Clear
          </button>
          <button
            type="submit"
            className={styles.btnPrimary}
            disabled={submitting || !form.hcp_name || !form.interaction_date}
          >
            {submitting ? (
              <span className={styles.spinner} aria-hidden="true" />
            ) : null}
            {submitting ? 'Saving…' : 'Save Interaction'}
          </button>
        </div>
      </form>
    </div>
  )
}
