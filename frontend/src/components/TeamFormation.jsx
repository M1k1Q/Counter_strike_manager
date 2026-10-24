import { useState, useEffect } from 'react'
import StatBar from './StatBar'
import { CustomSelect } from './CustomSelect'

const SLOT_LABELS = ['Player 1', 'Player 2', 'Player 3', 'Player 4', 'Player 5']
const CS_MAPS = [
  { value: 'default', label: 'Default (All Maps)' },
  { value: 'mirage', label: 'Mirage' }, { value: 'inferno', label: 'Inferno' },
  { value: 'nuke', label: 'Nuke' }, { value: 'overpass', label: 'Overpass' },
  { value: 'ancient', label: 'Ancient' }, { value: 'anubis', label: 'Anubis' },
  { value: 'dust2', label: 'Dust II' },
]

function TeamFormation({ team, onSaved }) {
  const players = team?.players || []
  const [selectedMap, setSelectedMap] = useState('default')
  const [selectedSide, setSelectedSide] = useState('ct')
  const [selectedIds, setSelectedIds] = useState(() => players.filter(p => p.is_active_roster).map(p => p.id))
  const [saving, setSaving] = useState(false)
  const [appointingId, setAppointingId] = useState(null)
  const [message, setMessage] = useState(null)

  useEffect(() => {
    setSelectedIds(players.filter(p => p.is_active_roster).map(p => p.id))
    setMessage(null)
  }, [team?.id, players.length])

  const toggle = (playerId) => {
    setMessage(null)
    if (selectedIds.includes(playerId)) {
      setSelectedIds(selectedIds.filter(id => id !== playerId))
    } else if (selectedIds.length >= 5) {
      setMessage({ text: 'You can only select 5 players for the starting lineup.', type: 'error' })
    } else {
      setSelectedIds([...selectedIds, playerId])
    }
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
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active_player_ids: selectedIds }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || 'Failed to save formation.')
      }
      if (onSaved) await onSaved()
      setMessage({ text: 'Formation saved! Your starting 5 has been set.', type: 'success' })
    } catch (e) {
      setMessage({ text: e.message, type: 'error' })
    } finally { setSaving(false) }
  }

  const updateAssignment = async (player, payload) => {
    if (appointingId !== null) return
    setAppointingId(player.id)
    setMessage(null)
    try {
      const res = await fetch(`/players/${player.id}/role`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        const error = await res.json().catch(() => ({}))
        throw new Error(error.detail || 'Failed to update player assignment.')
      }
      if (onSaved) await onSaved()
      setMessage({ text: 'Player assignment saved.', type: 'success' })
    } catch (error) {
      setMessage({ text: error.message, type: 'error' })
    } finally { setAppointingId(null) }
  }

  const getDisplayRating = (p) => {
    const v = p?.Rating ?? p?.rating ?? p?.overall_rating ?? 0
    return Number.isFinite(Number(v)) ? Math.round(Number(v)) : 0
  }
  const getRoleFitBonus = (player) => {
    const selectedRole = (player.selected_role || '').trim().toLowerCase()
    if (!selectedRole) return 0
    return (player.role || '').toLowerCase().split(/\s+/).includes(selectedRole) ? 1 : -1
  }
  const slots = SLOT_LABELS.map((label, i) => ({ label, player: players.find(p => p.id === selectedIds[i]) }))
  const sortedPlayers = [...players].sort((a, b) =>
    Number(selectedIds.includes(b.id)) - Number(selectedIds.includes(a.id)) || getDisplayRating(b) - getDisplayRating(a))

  if (!team || players.length < 5) return (
    <div className="formation-container"><p style={{ color: 'var(--text-secondary)' }}>
      {!team ? 'Select a team first to set your formation.' : `You need at least 5 players on your roster to set a formation. Currently have ${players.length}.`}
    </p></div>
  )

  return (
    <div className="formation-container">
      <div className="formation-header">
        <h3>Assign Player Roles &amp; IGL</h3>
        <span className="formation-counter"><strong>{selectedIds.length}</strong> / 5 selected</span>
      </div>
      <p className="formation-igl-hint">Appoint one IGL from any playing role. IGL % shows calling suitability; the highlighted IGL is your appointed captain. Appointments save immediately.</p>
      <div className="map-formation-section">
        <div className="map-formation-label">Map-wise Formation</div>
        <div className="map-selector-row">{CS_MAPS.map(m => (
          <button key={m.value} className={`map-chip ${selectedMap === m.value ? 'active' : ''}`} onClick={() => setSelectedMap(m.value)}>{m.label}</button>
        ))}</div>
        <div className="side-toggle-row">
          <button className={`side-toggle ct ${selectedSide === 'ct' ? 'active' : ''}`} onClick={() => setSelectedSide('ct')}><span className="side-icon" aria-hidden="true">CT</span> CT Side</button>
          <button className={`side-toggle t ${selectedSide === 't' ? 'active' : ''}`} onClick={() => setSelectedSide('t')}><span className="side-icon" aria-hidden="true">T</span> T Side</button>
        </div>
        <div className="map-formation-hint">Configuring: <strong>{CS_MAPS.find(m => m.value === selectedMap)?.label}</strong> — <strong>{selectedSide === 'ct' ? 'CT Side' : 'T Side'}</strong></div>
      </div>
      <div className="formation-pitch">{slots.map(({ label, player }, i) => (
        <div key={i} className={`formation-slot ${player ? 'filled' : ''}`}>
          {player ? <>
            <div className="formation-slot-number">{label}</div>
            <div className="formation-slot-name">{player.player}</div>
            <CustomSelect value={player.selected_role || ''} onChange={val => updateAssignment(player, { role: val })}
              options={[{ value: '', label: 'Auto' }, ...['Lurker', 'Entry', 'AWPer', 'Support'].map(role => ({ value: role, label: role }))]}
              className="formation-role-select-wrapper" />
            <div className={`formation-role-fit ${getRoleFitBonus(player) > 0 ? 'positive' : getRoleFitBonus(player) < 0 ? 'negative' : 'neutral'}`}>
              {getRoleFitBonus(player) > 0 ? '+1' : getRoleFitBonus(player) < 0 ? '-1' : '0'} Firepower
            </div>
            <button type="button" className={`formation-igl-toggle ${player.is_igl ? 'appointed' : ''}`}
              aria-pressed={Boolean(player.is_igl)} aria-label={`${player.is_igl ? 'Remove' : 'Appoint'} ${player.player} as IGL`}
              disabled={appointingId !== null} onClick={() => updateAssignment(player, { is_igl: !player.is_igl })}>
              {appointingId === player.id ? 'Saving…' : player.is_igl ? '✓ Appointed IGL' : 'Appoint IGL'}
            </button>
            <div className="formation-pool-rating">{getDisplayRating(player)}</div>
            <div className="formation-slot-stats">
              <StatBar label="Fire" value={player.firepower} /><StatBar label="Snip" value={player.sniping} />
              <StatBar label="Open" value={player.opening} /><StatBar label="Clutch" value={player.clutching} />
              <StatBar label="Entry" value={player.entrying} /><StatBar label="Trade" value={player.trading} />
              <StatBar label="Util" value={player.utility} /><StatBar label="IGL %" value={player.igl_score} />
            </div>
          </> : <><div className="formation-slot-empty-icon">⬡</div><div className="formation-slot-number">{label}</div></>}
        </div>
      ))}</div>
      <div className="formation-pool-title">Select Players ({players.length} available)</div>
      <div className="formation-pool">{sortedPlayers.map(p => {
        const isSelected = selectedIds.includes(p.id)
        return <div key={p.id} className={`formation-pool-player ${isSelected ? 'selected' : ''}`} onClick={() => toggle(p.id)}
          role="checkbox" aria-checked={isSelected} tabIndex={0}
          onKeyDown={e => { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); toggle(p.id) } }}>
          <span className={`fp-check ${isSelected ? '' : 'empty'}`}>{isSelected ? '✓' : '○'}</span>
          <span className="formation-pool-name">{p.player}</span>
          <span className="formation-pool-role">{p.role || 'Unassigned'}{p.is_igl ? ' · IGL' : ''}</span>
          <span className="formation-pool-igl">IGL {Math.round(p.igl_score ?? 0)}%</span>
          <span className="formation-pool-rating">{getDisplayRating(p)}</span>
        </div>
      })}</div>
      <div className="formation-save-row">
        <button className="btn-primary" onClick={handleSave} disabled={saving || selectedIds.length !== 5} id="formation-save-btn">{saving ? 'Saving…' : 'Save Formation'}</button>
        {selectedIds.length !== 5 && <span className="formation-save-hint">Select exactly 5 players to save</span>}
      </div>
      {message && <div className={`formation-msg ${message.type}`}>{message.text}</div>}
    </div>
  )
}

export default TeamFormation
