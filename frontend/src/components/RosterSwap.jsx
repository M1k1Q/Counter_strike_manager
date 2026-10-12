import { useState, useEffect } from 'react'
import StatBar from './StatBar'

function RosterSwap({ team, onSaved }) {
  const players = team?.players || []
  const [selectedIds, setSelectedIds] = useState(
    () => players.filter(p => p.is_active_roster).map(p => p.id)
  )
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)

  useEffect(() => {
    setSelectedIds(players.filter(p => p.is_active_roster).map(p => p.id))
    setMessage(null)
  }, [team?.id, players.length])

  const activeRoster = players.filter(p => selectedIds.includes(p.id))
  const benchPlayers = players.filter(p => !selectedIds.includes(p.id))

  const getDisplayRating = (p) => {
    const v = p?.Rating ?? p?.rating ?? p?.overall_rating ?? 0
    return Number.isFinite(Number(v)) ? Math.round(Number(v)) : 0
  }

  const promote = (playerId) => {
    setMessage(null)
    if (selectedIds.length >= 5) {
      setMessage({ text: 'Starting lineup is full (5/5). Demote a player first.', type: 'error' })
      return
    }
    setSelectedIds(prev => [...prev, playerId])
  }

  const demote = (playerId) => {
    setMessage(null)
    setSelectedIds(prev => prev.filter(id => id !== playerId))
  }

  const handleSave = async () => {
    if (selectedIds.length !== 5) {
      setMessage({ text: `Select exactly 5 players (currently ${selectedIds.length} selected).`, type: 'error' })
      return
    }

    setSaving(true)
    setMessage(null)

    try {
      const res = await fetch(`/teams/${team.id}/roster`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active_player_ids: selectedIds }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || 'Failed to save roster.')
      }

      setMessage({ text: '✓ Roster updated! Starting lineup saved.', type: 'success' })
      if (onSaved) onSaved()
    } catch (e) {
      setMessage({ text: e.message, type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const hasChanges = (() => {
    const original = new Set(players.filter(p => p.is_active_roster).map(p => p.id))
    const current = new Set(selectedIds)
    if (original.size !== current.size) return true
    for (const id of original) {
      if (!current.has(id)) return true
    }
    return false
  })()

  if (!team) {
    return (
      <div className="roster-swap-container">
        <p style={{ color: 'var(--text-secondary)' }}>Select a team first.</p>
      </div>
    )
  }

  if (players.length < 5) {
    return (
      <div className="roster-swap-container">
        <p style={{ color: 'var(--text-secondary)' }}>
          You need at least 5 players to set a roster. Currently have {players.length}.
        </p>
      </div>
    )
  }

  const renderPlayerCard = (p, isActive) => (
    <div key={p.id} className={`roster-swap-player ${isActive ? 'active-player' : 'bench-player'}`}>
      <div className="rsp-top-row">
        <div className="rsp-info">
          <span className="rsp-name">{p.player}</span>
          <span className={`role-badge ${(p.selected_role || p.role || 'default').toLowerCase().split(' ')[0]}`}>
            {p.selected_role || p.role || 'Unassigned'}
          </span>
        </div>
        <div className="rsp-rating">{getDisplayRating(p)}</div>
      </div>
      <div className="rsp-stats">
        <StatBar label="Fire" value={p.firepower} />
        <StatBar label="Util" value={p.utility} />
        <StatBar label="Impact" value={p.impact} />
        <StatBar label="Clutch" value={p.clutching} />
      </div>
      <button
        className={`rsp-swap-btn ${isActive ? 'demote' : 'promote'}`}
        onClick={() => isActive ? demote(p.id) : promote(p.id)}
        title={isActive ? 'Move to Bench' : 'Promote to Starting'}
      >
        {isActive ? '↓ Move to Bench' : '↑ Promote to Starting'}
      </button>
    </div>
  )

  return (
    <div className="roster-swap-container">
      <div className="roster-swap-header">
        <h3>Swap Roster Players</h3>
        <span className="roster-swap-counter">
          <strong>{selectedIds.length}</strong> / 5 starting
        </span>
      </div>

      <div className="roster-swap-columns">
        {/* Starting Lineup */}
        <div className="roster-swap-column starting-col">
          <div className="rsc-header">
            <span className="rsc-icon">▶</span>
            <span className="rsc-title">Starting Lineup</span>
            <span className="rsc-count">{activeRoster.length}/5</span>
          </div>
          <div className="rsc-list">
            {activeRoster.length === 0 ? (
              <div className="rsc-empty">No starters selected. Promote players from the bench.</div>
            ) : (
              activeRoster.map(p => renderPlayerCard(p, true))
            )}
          </div>
        </div>

        {/* Swap Arrow Column */}
        <div className="roster-swap-divider">
          <span className="swap-arrows">⇄</span>
        </div>

        {/* Bench */}
        <div className="roster-swap-column bench-col">
          <div className="rsc-header">
            <span className="rsc-icon bench-icon">◆</span>
            <span className="rsc-title">Bench</span>
            <span className="rsc-count">{benchPlayers.length}</span>
          </div>
          <div className="rsc-list">
            {benchPlayers.length === 0 ? (
              <div className="rsc-empty">All players are in the starting lineup.</div>
            ) : (
              benchPlayers.map(p => renderPlayerCard(p, false))
            )}
          </div>
        </div>
      </div>

      {/* Save */}
      <div className="roster-swap-save-row">
        <button
          className="btn-primary"
          onClick={handleSave}
          disabled={saving || selectedIds.length !== 5 || !hasChanges}
          id="roster-swap-save-btn"
        >
          {saving ? 'Saving…' : hasChanges ? 'Save Roster Changes' : 'No Changes'}
        </button>
        {selectedIds.length !== 5 && (
          <span className="formation-save-hint">
            Select exactly 5 players to save
          </span>
        )}
      </div>

      {message && (
        <div className={`formation-msg ${message.type}`}>{message.text}</div>
      )}
    </div>
  )
}

export default RosterSwap
