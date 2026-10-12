import { useState, useEffect } from 'react'
import StatBar from './StatBar'
import { CustomSelect } from './CustomSelect'

const SLOT_LABELS = ['Player 1', 'Player 2', 'Player 3', 'Player 4', 'Player 5']

const CS_MAPS = [
  { value: 'default', label: 'Default (All Maps)' },
  { value: 'mirage', label: 'Mirage' },
  { value: 'inferno', label: 'Inferno' },
  { value: 'nuke', label: 'Nuke' },
  { value: 'overpass', label: 'Overpass' },
  { value: 'ancient', label: 'Ancient' },
  { value: 'anubis', label: 'Anubis' },
  { value: 'dust2', label: 'Dust II' },
]

function TeamFormation({ team, onSaved }) {
  const players = team?.players || []

  const [selectedMap, setSelectedMap] = useState('default')
  const [selectedSide, setSelectedSide] = useState('ct')

  // Pre-select currently active players
  const [selectedIds, setSelectedIds] = useState(
    () => players.filter(p => p.is_active_roster).map(p => p.id)
  )
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null) // { text, type }

  // Re-sync when team prop changes (e.g. after a refresh)
  useEffect(() => {
    setSelectedIds(players.filter(p => p.is_active_roster).map(p => p.id))
    setMessage(null)
  }, [team?.id, players.length])

  const toggle = (playerId) => {
    setMessage(null)
    setSelectedIds(prev => {
      if (prev.includes(playerId)) {
        return prev.filter(id => id !== playerId)
      }
      if (prev.length >= 5) {
        setMessage({ text: 'You can only select 5 players for the starting lineup.', type: 'error' })
        return prev
      }
      return [...prev, playerId]
    })
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
        throw new Error(err.detail || 'Failed to save formation.')
      }

      setMessage({ text: '✓ Formation saved! Your starting 5 has been set.', type: 'success' })
      if (onSaved) onSaved()
    } catch (e) {
      setMessage({ text: e.message, type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const handleRoleChange = async (playerId, newRole) => {
    try {
      const res = await fetch(`/players/${playerId}/role`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: newRole }),
      })
      if (res.ok && onSaved) {
        onSaved()
      }
    } catch (e) {
      console.error('Failed to update role', e)
    }
  }

  const getDisplayRating = (p) => {
    const v = p?.Rating ?? p?.rating ?? p?.overall_rating ?? 0
    return Number.isFinite(Number(v)) ? Math.round(Number(v)) : 0
  }

  // Build the 5 slots from selected IDs in order
  const slots = SLOT_LABELS.map((label, i) => {
    const pid = selectedIds[i]
    const player = pid != null ? players.find(p => p.id === pid) : null
    return { label, player }
  })

  // Sort pool: active first, then by rating desc
  const sortedPlayers = [...players].sort((a, b) => {
    const aActive = selectedIds.includes(a.id) ? 1 : 0
    const bActive = selectedIds.includes(b.id) ? 1 : 0
    if (bActive !== aActive) return bActive - aActive
    return getDisplayRating(b) - getDisplayRating(a)
  })

  if (!team) {
    return (
      <div className="formation-container">
        <p style={{ color: 'var(--text-secondary)' }}>Select a team first to set your formation.</p>
      </div>
    )
  }

  if (players.length < 5) {
    return (
      <div className="formation-container">
        <p style={{ color: 'var(--text-secondary)' }}>
          You need at least 5 players on your roster to set a formation. Currently have {players.length}.
        </p>
      </div>
    )
  }

  return (
    <div className="formation-container">
      <div className="formation-header">
        <h3>Assign Player Roles</h3>
        <span className="formation-counter">
          <strong>{selectedIds.length}</strong> / 5 selected
        </span>
      </div>

      {/* Map-wise Formation Selector */}
      <div className="map-formation-section">
        <div className="map-formation-label">Map-wise Formation</div>
        <div className="map-selector-row">
          {CS_MAPS.map(m => (
            <button
              key={m.value}
              className={`map-chip ${selectedMap === m.value ? 'active' : ''}`}
              onClick={() => setSelectedMap(m.value)}
            >
              {m.label}
            </button>
          ))}
        </div>
        <div className="side-toggle-row">
          <button
            className={`side-toggle ct ${selectedSide === 'ct' ? 'active' : ''}`}
            onClick={() => setSelectedSide('ct')}
          >
            <span className="side-icon">🛡</span> CT Side
          </button>
          <button
            className={`side-toggle t ${selectedSide === 't' ? 'active' : ''}`}
            onClick={() => setSelectedSide('t')}
          >
            <span className="side-icon">💥</span> T Side
          </button>
        </div>
        <div className="map-formation-hint">
          Configuring: <strong>{CS_MAPS.find(m => m.value === selectedMap)?.label}</strong> — <strong>{selectedSide === 'ct' ? 'CT Side' : 'T Side'}</strong>
        </div>
      </div>

      {/* Visual 5-slot pitch */}
      <div className="formation-pitch">
        {slots.map(({ label, player }, i) => (
          <div key={i} className={`formation-slot ${player ? 'filled' : ''}`}>
            {player ? (
              <>
                <div className="formation-slot-number">{label}</div>
                <div className="formation-slot-name">{player.player}</div>
                <CustomSelect 
                  value={player.selected_role || (player.role ? player.role.split(' ')[0] : '')}
                  onChange={(val) => handleRoleChange(player.id, val)}
                  options={[
                    { value: "", label: "Auto" },
                    { value: "Lurker", label: "Lurker" },
                    { value: "Entry", label: "Entry" },
                    { value: "AWPer", label: "AWPer" },
                    { value: "Support", label: "Support" },
                    { value: "IGL", label: "IGL" }
                  ]}
                  className="formation-role-select-wrapper"
                />
                <div className="formation-pool-rating">{getDisplayRating(player)}</div>
                <div className="formation-slot-stats">
                  <StatBar label="Fire" value={player.firepower} />
                  <StatBar label="Snip" value={player.sniping} />
                  <StatBar label="Open" value={player.opening} />
                  <StatBar label="Clutch" value={player.clutching} />
                  <StatBar label="Entry" value={player.entrying} />
                  <StatBar label="Trade" value={player.trading} />
                  <StatBar label="Util" value={player.utility} />
                </div>
              </>
            ) : (
              <>
                <div className="formation-slot-empty-icon">⬡</div>
                <div className="formation-slot-number">{label}</div>
              </>
            )}
          </div>
        ))}
      </div>

      {/* Player pool */}
      <div className="formation-pool-title">Select Players ({players.length} available)</div>
      <div className="formation-pool">
        {sortedPlayers.map(p => {
          const isSelected = selectedIds.includes(p.id)
          return (
            <div
              key={p.id}
              className={`formation-pool-player ${isSelected ? 'selected' : ''}`}
              onClick={() => toggle(p.id)}
              role="checkbox"
              aria-checked={isSelected}
              tabIndex={0}
              onKeyDown={e => e.key === ' ' && toggle(p.id)}
            >
              <span className={`fp-check ${isSelected ? '' : 'empty'}`}>
                {isSelected ? '✓' : '○'}
              </span>
              <span className="formation-pool-name">{p.player}</span>
              <span className="formation-pool-role">{p.role || 'Unassigned'}</span>
              <span className="formation-pool-rating">{getDisplayRating(p)}</span>
            </div>
          )
        })}
      </div>

      {/* Save row */}
      <div className="formation-save-row">
        <button
          className="btn-primary"
          onClick={handleSave}
          disabled={saving || selectedIds.length !== 5}
          id="formation-save-btn"
        >
          {saving ? 'Saving…' : 'Save Formation'}
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

export default TeamFormation
