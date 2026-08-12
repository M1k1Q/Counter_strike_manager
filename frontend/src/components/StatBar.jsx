import React from 'react'

function StatBar({ label, value }) {
  const pct = Math.min(100, Math.max(0, value ?? 0))
  const colorClass = pct >= 75 ? 'bar-high' : pct >= 50 ? 'bar-mid' : 'bar-low'
  return (
    <div className="stat-bar-row">
      <div className="stat-bar-label">
        <span>{label}</span>
        <span>{Math.round(pct)}</span>
      </div>
      <div className="stat-bar-container">
        <div className={`stat-bar-fill ${colorClass}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default StatBar
