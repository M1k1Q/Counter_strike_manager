import { useEffect, useState } from 'react'
import './YearEndTop20.css'
import SeasonRecap from './SeasonRecap.jsx'

function YearEndTop20() {
  const [seasons, setSeasons] = useState([])
  const [selectedYear, setSelectedYear] = useState('')
  const [selectedPlayer, setSelectedPlayer] = useState(null)
  const [recapSeason, setRecapSeason] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function loadRankings() {
      try {
        const response = await fetch('/tournaments/yearly-top-20')
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const data = await response.json()
        if (!cancelled) setSeasons(data)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Unable to load year-end rankings.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    loadRankings()
    return () => {
      cancelled = true
    }
  }, [])

  const activeYear = selectedYear || String(seasons[0]?.year || '')
  const activeSeason = seasons.find((season) => String(season.year) === activeYear)

  useEffect(() => {
    if (!selectedPlayer) return undefined

    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setSelectedPlayer(null)
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [selectedPlayer])

  return (
    <section className="year-end-rankings">
      {recapSeason && <SeasonRecap season={recapSeason} onClose={() => setRecapSeason(null)} />}
      <header className="year-end-header">
        <div>
          <p className="year-end-eyebrow">Season honors</p>
          <h1>Year-End Top 20</h1>
          <p>Annual tournament performance, with MVP and EVP honors tracked by season.</p>
        </div>
        {seasons.length > 0 && (
          <label className="year-select">
            <span>Season</span>
            <select
              aria-label="Select year-end ranking season"
              value={activeYear}
              onChange={(event) => setSelectedYear(event.target.value)}
            >
              {seasons.map((season) => (
                <option key={season.year} value={season.year}>{season.year}</option>
              ))}
            </select>
          </label>
        )}
      </header>

      {activeSeason?.players?.length > 0 && <button type="button" className="btn-secondary" style={{ marginBottom: '1rem' }} onClick={() => setRecapSeason(activeSeason)}>Play season countdown ↗</button>}
      {loading && <p className="year-end-message">Loading year-end rankings…</p>}
      {error && <p className="year-end-message year-end-error">Could not load rankings: {error}</p>}
      {!loading && !error && !activeSeason && (
        <div className="year-end-empty">
          <h2>No season rankings yet</h2>
          <p>The Top 20 is archived when you advance from December into the next year.</p>
        </div>
      )}
      {activeSeason && (
        <div className="year-end-table-wrap">
          <table className="year-end-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Player</th>
                <th>Team</th>
                <th>Rating</th>
                <th>Maps</th>
                <th>K / D / A</th>
                <th>ADR</th>
                <th>MVP</th>
                <th>EVP</th>
              </tr>
            </thead>
            <tbody>
              {activeSeason.players.map((player) => (
                <tr
                  key={player.player_id}
                  className="year-end-player-row"
                  onClick={() => setSelectedPlayer(player)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      setSelectedPlayer(player)
                    }
                  }}
                  tabIndex={0}
                  aria-label={`View ${player.player_name}'s ${activeYear} season details`}
                >
                  <td className="year-end-rank">{player.rank}</td>
                  <td>
                    <button
                      className="year-end-player-trigger"
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation()
                        setSelectedPlayer(player)
                      }}
                    >
                      {player.player_name}
                    </button>
                    {player.role && <span className="year-end-role">{player.role}</span>}
                  </td>
                  <td>{player.team_name}</td>
                  <td className="year-end-rating">{Number(player.rating).toFixed(2)}</td>
                  <td>{player.maps_played}</td>
                  <td>{player.kills} / {player.deaths} / {player.assists}</td>
                  <td>{Number(player.adr).toFixed(1)}</td>
                  <td>{player.mvp_count}</td>
                  <td>{player.evp_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {selectedPlayer && (
        <div
          className="year-player-modal-backdrop"
          onClick={(event) => {
            if (event.target === event.currentTarget) setSelectedPlayer(null)
          }}
        >
          <section
            className="year-player-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="year-player-modal-title"
          >
            <button
              className="year-player-modal-close"
              type="button"
              aria-label="Close player details"
              onClick={() => setSelectedPlayer(null)}
            >
              ×
            </button>
            <header className="year-player-modal-header">
              <span className="year-player-modal-rank">#{selectedPlayer.rank} · {activeYear}</span>
              <h2 id="year-player-modal-title">{selectedPlayer.player_name}</h2>
              <p>
                {selectedPlayer.team_name}
                {selectedPlayer.role ? ` · ${selectedPlayer.role}` : ''}
              </p>
            </header>

            <div className="year-player-stat-grid">
              <div className="year-player-stat-card year-player-stat-highlight">
                <span>Rating</span>
                <strong>{Number(selectedPlayer.rating).toFixed(2)}</strong>
              </div>
              <div className="year-player-stat-card">
                <span>Maps played</span>
                <strong>{selectedPlayer.maps_played}</strong>
              </div>
              <div className="year-player-stat-card">
                <span>K / D / A</span>
                <strong>{selectedPlayer.kills} / {selectedPlayer.deaths} / {selectedPlayer.assists}</strong>
              </div>
              <div className="year-player-stat-card">
                <span>K/D ratio</span>
                <strong>{Number(selectedPlayer.kd_ratio).toFixed(2)}</strong>
              </div>
              <div className="year-player-stat-card">
                <span>K/D difference</span>
                <strong>{selectedPlayer.kd_diff > 0 ? '+' : ''}{selectedPlayer.kd_diff}</strong>
              </div>
              <div className="year-player-stat-card">
                <span>Average ADR</span>
                <strong>{Number(selectedPlayer.adr).toFixed(1)}</strong>
              </div>
            </div>

            <section className="year-player-honors">
              <div className="year-player-honors-heading">
                <div>
                  <p className="year-end-eyebrow">Season honors</p>
                  <h3>Event awards</h3>
                </div>
                <div className="year-player-honor-counts">
                  <span className="year-player-award-badge mvp">MVP · {selectedPlayer.mvp_count}</span>
                  <span className="year-player-award-badge evp">EVP · {selectedPlayer.evp_count}</span>
                </div>
              </div>
              {selectedPlayer.honors?.length ? (
                <ul className="year-player-honor-list">
                  {selectedPlayer.honors.map((honor) => (
                    <li key={`${honor.month}-${honor.event_name}-${honor.award}`}>
                      <div>
                        <strong>{honor.event_name}</strong>
                        <span>
                          {new Date(Number(activeYear), honor.month - 1).toLocaleString(undefined, { month: 'long' })}
                          {honor.placement ? ` · ${honor.placement}` : ''}
                          {` · ${Number(honor.event_rating).toFixed(2)} rating`}
                        </span>
                      </div>
                      <span className={`year-player-award-badge ${honor.award === 'MVP' ? 'mvp' : 'evp'}`}>
                        {honor.award}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="year-player-no-honors">No MVP or EVP awards this season.</p>
              )}
            </section>
          </section>
        </div>
      )}
    </section>
  )
}

export default YearEndTop20
