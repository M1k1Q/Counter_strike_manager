import React from 'react'

function TeamRoster({ team, searchQuery }) {
  // Filter the team's players based on search query
  const players = (team.players || []).filter(p =>
    (p.player && p.player.toLowerCase().includes(searchQuery.toLowerCase())) ||
    (p.role && p.role.toLowerCase().includes(searchQuery.toLowerCase()))
  )

  // If there's a search query and no players match, don't render this team card
  if (searchQuery && players.length === 0) return null;

  const formatPrice = (price) => {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(price || 0)
  }

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
              {players.map(p => (
                <tr key={p.id}>
                  <td className="player-name">
                    {p.player}
                    {p.id === topIglPlayerId && <span className="igl-tag">IGL</span>}
                  </td>
                  <td>
                    <span className={`role-badge ${(p.role || '').toLowerCase().split(' ')[0] || 'default'}`}>{p.role || 'Unassigned'}</span>
                  </td>
                  <td className="stat highlight">{getDisplayRating(p)}</td>
                  <td className="price-stat stat">{formatPrice(p.price)}</td>
                </tr>
              ))}
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
