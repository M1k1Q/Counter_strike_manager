import { useRef, useState } from 'react'
import PlayerAvatar from './PlayerAvatar'

const MAX_FORM_BONUS = 2

function getDisplayRating(player) {
  const value = player?.Rating ?? player?.rating ?? player?.overall_rating ?? 0
  return Number.isFinite(Number(value)) ? Number(value) : 0
}

function PlayerFormTraining({ team, onSaved }) {
  const players = team?.players || []
  const [training, setTraining] = useState(false)
  const trainingInFlight = useRef(false)
  const [message, setMessage] = useState(null)
  const needsTraining = players.some(player => Number(player.training_form_bonus || 0) < MAX_FORM_BONUS)

  const handleTrainSquad = async () => {
    if (trainingInFlight.current || !needsTraining) return
    trainingInFlight.current = true
    setTraining(true)
    setMessage(null)

    try {
      const response = await fetch('/players/form-train-squad', { method: 'POST' })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.detail || 'Unable to train squad')

      setMessage({
        text: `${data.length} squad players refilled to +${MAX_FORM_BONUS} match Rating.`,
        type: 'success',
      })
      if (onSaved) await onSaved()
    } catch (err) {
      setMessage({
        text: err.message || 'Training failed. Please try again.',
        type: 'error',
      })
    } finally {
      trainingInFlight.current = false
      setTraining(false)
    }
  }

  if (!team) {
    return (
      <div className="player-training">
        <p className="player-training-empty">Select a team first to train players.</p>
      </div>
    )
  }

  if (players.length === 0) {
    return (
      <div className="player-training">
        <p className="player-training-empty">No players on this roster yet.</p>
      </div>
    )
  }

  return (
    <div className="player-training">
      <div className="player-training-header">
        <div>
          <h3>Form Training</h3>
          <p className="player-training-hint">
            Refill your whole squad, including the bench, to +2 match Rating. The bonus decays by 35% after each
            completed series and never changes saved overall Rating.
          </p>
        </div>
        <button className="btn-primary" type="button" disabled={training || !needsTraining}
          onClick={handleTrainSquad}>
          {training ? 'Training squad…' : needsTraining ? 'Train Entire Squad' : 'Squad Fully Charged'}
        </button>
      </div>

      {message && (
        <div className={`formation-msg ${message.type}`} role="status">{message.text}</div>
      )}

      <div className="player-training-list">
        {players.map((player) => {
          const bonus = Number(player.training_form_bonus || 0)
          const capped = bonus >= MAX_FORM_BONUS
          const baseRating = getDisplayRating(player)
          const effectiveRating = baseRating * Number(player.form || 1) + bonus

          return (
            <article key={player.id} className="player-training-card">
              <div className="player-training-card-top">
                <div className="player-profile-identity">
                  <PlayerAvatar player={player} />
                  <div className="player-training-identity">
                  <span className="player-training-name">{player.player}</span>
                  <span className="player-training-meta">
                    {player.selected_role || player.role || 'Unassigned'}
                    {' · '}
                    Match Rating {effectiveRating.toFixed(1)}
                    {' · '}
                    OVR {baseRating.toFixed(0)}
                  </span>
                  </div>
                </div>
                <span className={`player-training-status ${capped ? 'blocked' : 'ready'}`}>
                  {capped ? 'Fully charged' : 'Ready to refill'}
                </span>
              </div>

              <div className="form-bonus-meter" aria-label={`Form training bonus: ${bonus.toFixed(1)} of 2`}>
                <div className="form-bonus-meter-fill" style={{ width: `${Math.min(100, (bonus / MAX_FORM_BONUS) * 100)}%` }} />
              </div>

              <div className="player-training-controls-row form-training-controls">
                <span className="form-bonus-value">+{bonus.toFixed(1)} / +{MAX_FORM_BONUS} match Rating</span>
              </div>
            </article>
          )
        })}
      </div>
    </div>
  )
}

export default PlayerFormTraining
