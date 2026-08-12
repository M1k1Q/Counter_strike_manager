import React from 'react'
import StatBar from './StatBar'

function TeamRoster({ team, searchQuery }) {
  const allPlayers = team.players || []

  const players = allPlayers.filter(p =>
    (p.player && p.player.toLowerCase().includes((searchQuery || '').toLowerCase())) ||
    (p.role && p.role.toLowerCase().includes((searchQuery || '').toLowerCase()))
  )

  if (searchQuery && players.length === 0) return null

  const formatPrice = (price) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(price || 0)

  const getDisplayRating = (player) => {
    const value = player?.Rating ?? player?.rating ?? player?.overall_rating ?? 0
    const numeric = Number(value)
    if (!Number.isFinite(numeric)) return 0
    return Number.isInteger(numeric) ? numeric : numeric.toFixed(2)
  }

  const totalValue = players.reduce((sum, p) => sum + (p.price || 0), 0)

  const topIglPlayerId = players.reduce((bestId, p) => {
    if (bestId === null) return p.id
    const bestScore = players.find(player => player.id === bestId)?.igl_score || 0
    return (p.igl_score || 0) > bestScore ? p.id : bestId
  }, null)

  const starting = players.filter(p => p.is_active_roster)
  const bench    = players.filter(p => !p.is_active_roster)

  const renderPlayerRow = (p) => {
    const displayRole = p.selected_role || p.role || 'Unassigned'
    return (
      <React.Fragment key={p.id}>
        <tr className={p.is_active_roster ? 'active-roster-row' : ''}>
          <td className="player-name">
            {p.player}
            {p.id === topIglPlayerId && <span className="igl-tag">IGL</span>}
          </td>
          <td>
            <span className={`role-badge ${displayRole.toLowerCase().split(' ')[0] || 'default'}`}>
              {displayRole}
            </span>
          </td>
        <td className="stat highlight">{getDisplayRating(p)}</td>
        <td className="price-stat stat">{formatPrice(p.price)}</td>
      </tr>
      <tr>
        <td colSpan={4} style={{ paddingTop: 0 }}>
          <div className="stat-bars">
            <StatBar label="Firepower" value={p.firepower} />
            <StatBar label="Utility"   value={p.utility} />
            <StatBar label="Impact"    value={p.impact} />
            <StatBar label="Clutching" value={p.clutching} />
          </div>
        </td>
      </tr>
    </React.Fragment>
    )
  }

  return (
    <div className="team-card">
      <div className="team-header">
        <div className="team-info">
          <h3>{team.name}</h3>
          <span className="team-rank">Rank #{team.ranking || 'N/A'}</span>
        </div>
        <div className="team-value">
          <span className="label">Total Value:</span>
          <span className="value">{formatPrice(totalValue)}</span>
        </div>
      </div>

      <div className="team-roster">
        {players.length > 0 ? (
          <table className="roster-table">
            <thead>
              <tr>
                <th>Player</th>
                <th>Role</th>
                <th>Overall</th>
                <th>Price</th>
              </tr>
            </thead>
            <tbody>
              {starting.length > 0 && (
                <>
                  <tr>
                    <td colSpan={4}>
                      <div className="roster-section-label starting">
                        ▶ Starting Lineup ({starting.length}/5)
                      </div>
                    </td>
                  </tr>
                  {starting.map(renderPlayerRow)}
                </>
              )}
              {bench.length > 0 && (
                <>
                  <tr>
                    <td colSpan={4}>
                      <div className="roster-section-label bench">
                        Bench ({bench.length})
                      </div>
                    </td>
                  </tr>
                  {bench.map(renderPlayerRow)}
                </>
              )}
              {starting.length === 0 && bench.length === 0 && players.map(renderPlayerRow)}
            </tbody>
          </table>
        ) : (
          <p className="empty-roster">No players on roster</p>
        )}
      </div>
    </div>
  )
}

export default TeamRoster
