import { useState } from 'react'
import styles from './SampleInput.module.css'

export default function SampleInput({ samples = [], onAdd, onRemove }) {
  const [product, setProduct] = useState('')
  const [qty, setQty] = useState('')

  function handleAdd() {
    if (!product.trim()) return
    onAdd({ product_name: product.trim(), quantity: parseInt(qty, 10) || 1 })
    setProduct('')
    setQty('')
  }

  return (
    <div className={styles.wrapper}>
      {/* Existing samples */}
      {samples.length > 0 && (
        <div className={styles.list}>
          {samples.map((s, i) => (
            <span key={i} className={styles.sample}>
              <span className={styles.sampleName}>{s.product_name}</span>
              <span className={styles.sampleQty}>×{s.quantity}</span>
              <button
                type="button"
                className={styles.remove}
                onClick={() => onRemove(i)}
                aria-label={`Remove ${s.product_name}`}
              >×</button>
            </span>
          ))}
        </div>
      )}

      {/* Add row */}
      <div className={styles.addRow}>
        <input
          type="text"
          className={styles.nameInput}
          value={product}
          onChange={(e) => setProduct(e.target.value)}
          placeholder="Product name"
          onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
        />
        <input
          type="number"
          className={styles.qtyInput}
          value={qty}
          onChange={(e) => setQty(e.target.value)}
          placeholder="Qty"
          min={1}
          onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
        />
        <button type="button" className={styles.addBtn} onClick={handleAdd}>
          + Add
        </button>
      </div>
    </div>
  )
}
