import { useEffect, useState } from 'react'
import StatBar from './StatBar'

const TRAINING_STATS = [
  ['firepower', 'Firepower'],
  ['entrying', 'Entrying'],
  ['opening', 'Opening'],
  ['clutching', 'Clutching'],
  ['sniping', 'Sniping'],
  ['trading', 'Trading'],
  ['utility', 'Utility'],
  ['impact', 'Impact'],
]

const DEVELOPMENT_STOP_AGE = 32

function getDisplayRating(player) {
  const value = player?.Rating ?? player?.rating ?? player?.overall_rating ?? 0
  return Number.isFinite(Number(value)) ? Math.round(Number(value)) : 0
}

function getTrainBlockReason(player, stat, gameDate) {
  if (Number(player?.age) >= DEVELOPMENT_STOP_AGE) return 'Age cap reached'
  const trainingPoints = getMonthlyTrainingPoints(player, gameDate)
  if (trainingPoints.limit - trainingPoints.used < 1 - 1e-9) return 'Monthly limit reached'
  return Number(player?.[stat] ?? 50) >= 100 ? 'Stat maxed' : null
}

function gameDateHasAdvanced(player, gameDate) {
  if (!gameDate || player?.last_trained_year == null || player?.last_trained_month == null) {
    return false
  }
  return player.last_trained_year !== gameDate.year
    || player.last_trained_month !== gameDate.month
}

function getMonthlyTrainingPoints(player, gameDate) {
  const form = Number(player?.form ?? 1)
  const limit = form < 0.8 ? 3 : form > 1 ? 10 : 5
  const used = gameDateHasAdvanced(player, gameDate)
    ? 0
    : Number(player?.training_points_used ?? 0)
  return { used, limit }
}

function PlayerTraining({ team, gameDate, onSaved }) {
  const players = team?.players || []
  const [selectedStats, setSelectedStats] = useState({})
  const [trainingId, setTrainingId] = useState(null)
  const [message, setMessage] = useState(null)
  const [yearlyRatings, setYearlyRatings] = useState([])
  const [yearlyRatingsError, setYearlyRatingsError] = useState(null)

  useEffect(() => {
    let cancelled = false
    async function loadYearlyRatings() {
      try {
        const response = await fetch('/players/development/yearly-ratings')
        const data = await response.json()
        if (!response.ok) throw new Error(data.detail || 'Unable to load yearly ratings')
        if (!cancelled) {
          setYearlyRatings(data)
          setYearlyRatingsError(null)
        }
      } catch (err) {
        if (!cancelled) setYearlyRatingsError(err.message || 'Unable to load yearly ratings')
      }
    }

    loadYearlyRatings()
    return () => { cancelled = true }
  }, [team?.id])

  const setStatForPlayer = (playerId, stat) => {
    setSelectedStats((prev) => ({ ...prev, [playerId]: stat }))
  }

  const handleTrain = async (player) => {
    const stat = selectedStats[player.id] || 'firepower'
    setTrainingId(player.id)
    setMessage(null)

    try {
      const response = await fetch(`/players/${player.id}/train`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stat }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.detail || 'Unable to train player')

      setMessage({
        text: `${data.player || player.player} improved ${TRAINING_STATS.find(([value]) => value === stat)?.[1] || stat}.`,
        type: 'success',
      })
      if (onSaved) onSaved()
    } catch (err) {
      setMessage({
        text: err.message || 'Training failed. Please try again.',
        type: 'error',
      })
    } finally {
      setTrainingId(null)
    }
  }

  if (!team) {
    return (
      <div className="player-training">
        <p className="player-training-empty">Select a team first to train players.</p>
      </div>
    )
  }

  return (
    <div className="player-training">
      <div className="player-training-header">
        <div>
          <h3>Develop Players</h3>
          <p className="player-training-hint">
            Each click adds +1 to the selected attribute and costs 1 point (capped at 100). Form sets the monthly budget until age 32: 10 points above 1.00 form, 5 points from 0.80 to 1.00, or 3 points below 0.80. Attributes cap at 100; potential only limits overall rating.
          </p>
        </div>
      </div>

      {message && (
        <div className={`formation-msg ${message.type}`}>{message.text}</div>
      )}

      <div className="player-training-list">
        {players.length === 0 ? (
          <p className="player-training-empty">No players on this roster yet.</p>
        ) : players.map((player) => {
          const selectedStat = selectedStats[player.id] || 'firepower'
          const blockReason = getTrainBlockReason(player, selectedStat, gameDate)
          const isTraining = trainingId === player.id
          const trainingPoints = getMonthlyTrainingPoints(player, gameDate)

          return (
            <article key={player.id} className="player-training-card">
              <div className="player-training-card-top">
                <div className="player-training-identity">
                  <span className="player-training-name">{player.player}</span>
                  <span className="player-training-meta">
                    {player.selected_role || player.role || 'Unassigned'}
                    {' · '}
                    Age {player.age ?? 'N/A'}
                    {' · '}
                    OVR {getDisplayRating(player)}
                    {player.potential != null ? ` / POT ${player.potential}` : ''}
                  </span>
                </div>
                <span className={`player-training-status ${blockReason ? 'blocked' : 'ready'}`}>
                  {blockReason === 'Monthly limit reached'
                    ? `${trainingPoints.used.toFixed(2)} / ${trainingPoints.limit} points · Limit reached`
                    : blockReason || `${trainingPoints.used.toFixed(2)} / ${trainingPoints.limit} points · Form ${Number(player.form || 1).toFixed(2)}×`}
                </span>
              </div>

              <div className="player-training-stats">
                <StatBar label="Firepower" value={player.firepower} />
                <StatBar label="Entrying" value={player.entrying} />
                <StatBar label="Opening" value={player.opening} />
                <StatBar label="Clutching" value={player.clutching} />
                <StatBar label="Sniping" value={player.sniping} />
                <StatBar label="Trading" value={player.trading} />
                <StatBar label="Utility" value={player.utility} />
                <StatBar label="Impact" value={player.impact} />
              </div>

              <div className="player-training-controls">
                <label className="offer-label" htmlFor={`train-stat-${player.id}`}>
                  Attribute to train
                </label>
                <div className="player-training-controls-row">
                  <select
                    id={`train-stat-${player.id}`}
                    className="offer-input"
                    value={selectedStat}
                    disabled={isTraining}
                    onChange={(event) => setStatForPlayer(player.id, event.target.value)}
                  >
                    {TRAINING_STATS.map(([value, label]) => (
                      <option
                        key={value}
                        value={value}
                        disabled={Number(player[value] ?? 50) >= 100}
                      >
                        {label}{Number(player[value] ?? 50) >= 100 ? ' (max)' : ''}
                      </option>
                    ))}
                  </select>
                  <button
                    className="btn-primary"
                    type="button"
                    disabled={Boolean(blockReason) || isTraining}
                    onClick={() => handleTrain(player)}
                  >
                    {isTraining ? 'Training…' : 'Train'}
                  </button>
                </div>
              </div>
            </article>
          )
        })}
      </div>

      <section className="yearly-player-ratings">
        <div className="player-training-header">
          <div>
            <h3>Yearly player ratings</h3>
            <p className="player-training-hint">
              Average match ratings for players while they played on your team. Ratings above 1.09 can increase potential at season end.
            </p>
          </div>
        </div>
        {yearlyRatingsError ? (
          <p className="player-training-empty error">{yearlyRatingsError}</p>
        ) : yearlyRatings.length === 0 ? (
          <p className="player-training-empty">Yearly ratings will appear here after the first season is completed.</p>
        ) : (
          <div className="yearly-player-ratings-table-wrap">
            <table className="roster-table">
              <thead>
                <tr>
                  <th>Season</th>
                  <th>Team</th>
                  <th>Player</th>
                  <th>Avg. rating</th>
                  <th>Maps</th>
                  <th>Potential</th>
                </tr>
              </thead>
              <tbody>
                {yearlyRatings.map((entry) => (
                  <tr key={`${entry.year}-${entry.team_id}-${entry.player_id}`}>
                    <td>{entry.year}</td>
                    <td>{entry.team_name}</td>
                    <td>{entry.player_name}</td>
                    <td className={entry.rating > 1.09 ? 'yearly-rating-growth' : ''}>
                      {Number(entry.rating).toFixed(2)}
                    </td>
                    <td>{entry.maps_played}</td>
                    <td>{entry.potential}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}

export default PlayerTraining
