import styles from './ExtractedFieldsPreview.module.css'

const FIELD_LABELS = {
  hcp_name:          'HCP Name',
  interaction_type:  'Type',
  interaction_date:  'Date',
  interaction_time:  'Time',
  topics_discussed:  'Topics',
  materials_shared:  'Materials',
  sentiment:         'Sentiment',
  followup_actions:  'Follow-ups',
  outcomes:          'Outcomes',
  samples_distributed: 'Samples',
}

export default function ExtractedFieldsPreview({ fields }) {
  // Only show non-empty fields
  const entries = Object.entries(FIELD_LABELS).filter(([key]) => {
    const v = fields[key]
    if (v === null || v === undefined) return false
    if (Array.isArray(v)) return v.length > 0
    return String(v).trim() !== ''
  })

  if (entries.length === 0) return null

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <span className={styles.icon}>⚡</span>
        <span className={styles.title}>Extracted fields auto-filled</span>
        <span className={styles.count}>{entries.length} field{entries.length !== 1 ? 's' : ''}</span>
      </div>
      <div className={styles.grid}>
        {entries.map(([key, label]) => {
          const val = fields[key]
          const display = Array.isArray(val) ? val.join(', ') : String(val)
          return (
            <div key={key} className={styles.row}>
              <span className={styles.fieldLabel}>{label}</span>
              <span className={styles.fieldValue}>{display}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
