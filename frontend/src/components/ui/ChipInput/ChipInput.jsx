import { useState } from 'react'
import styles from './ChipInput.module.css'

export default function ChipInput({ chips = [], placeholder, onAdd, onRemove }) {
  const [value, setValue] = useState('')

  function handleKeyDown(e) {
    if ((e.key === 'Enter' || e.key === ',') && value.trim()) {
      e.preventDefault()
      onAdd(value.trim().replace(/,$/, ''))
      setValue('')
    } else if (e.key === 'Backspace' && !value && chips.length > 0) {
      onRemove(chips.length - 1)
    }
  }

  return (
    <div className={styles.container}>
      {chips.map((chip, i) => (
        <span key={i} className={styles.chip}>
          {chip}
          <button
            type="button"
            className={styles.chipRemove}
            onClick={() => onRemove(i)}
            aria-label={`Remove ${chip}`}
          >
            ×
          </button>
        </span>
      ))}
      <input
        type="text"
        className={styles.input}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={chips.length === 0 ? placeholder : 'Add more…'}
      />
    </div>
  )
}
