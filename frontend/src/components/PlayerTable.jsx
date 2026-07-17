function PlayerTable({ players, loading, error, onRowClick }) {
  // Helper: overall badge class
  function overallClass(val) {
    if (val >= 1.15) return 'overall-high'
    if (val >= 1.0) return 'overall-mid'
    return 'overall-low'
  }

  // Helper: role badge class
  function roleClass(role) {
    const r = (role || '').toLowerCase().split(' ')[0]
    const map = { awper: 'awper', rifler: 'rifler', igl: 'igl', entry: 'entry', support: 'support', lurker: 'lurker' }
    return map[r] || 'default'
  }

  const formatPrice = (price) => {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(price || 0)
  }

  const getDisplayRating = (player) => {
    const value = player?.Rating ?? player?.rating ?? player?.overall_rating ?? 0
    const numeric = Number(value)
    if (!Number.isFinite(numeric)) return 0
    return Number.isInteger(numeric) ? numeric : numeric.toFixed(2)
  }

  // Loading skeleton
  if (loading) {
    return (
      <div className="table-wrapper">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>#</th><th>Player</th><th>Role</th><th>Overall</th><th>Price</th>
              </tr>
            </thead>
            <tbody>
              {[...Array(3)].map((_, i) => (
                <tr key={i} className="skeleton-row">
                  <td colSpan="5"><div className="skeleton" style={{ width: `${90 + i * 5}%` }}></div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="table-wrapper">
        <div className="empty-state">
          <div className="icon">⚠️</div>
          <h3>Connection error</h3>
          <p>Could not reach the API. Make sure the backend server is running.</p>
        </div>
      </div>
    )
  }

  // Empty state
  if (players.length === 0) {
    return (
      <div className="table-wrapper">
        <div className="empty-state">
          <div className="icon">🎯</div>
          <h3>No players found</h3>
          <p>Try adjusting your search criteria.</p>
        </div>
      </div>
    )
  }

  // Player table
  return (
    <div className="table-wrapper">
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Player</th>
              <th>Role</th>
              <th>Overall</th>
              <th>Price</th>
            </tr>
          </thead>
          <tbody>
            {players.map((player, index) => (
              <tr
                key={player.id}
                className="fade-in clickable-row"
                style={{ animationDelay: `${index * 0.04}s` }}
                onClick={() => onRowClick?.(player)}
              >
                <td style={{ color: 'var(--text-muted)', fontWeight: 500 }}>{index + 1}</td>
                <td className="player-name">
                  {player.player}
                  {player.igl_score >= 70 && <span className="igl-tag">IGL</span>}
                </td>
                <td><span className={`role-badge ${roleClass(player.role)}`}>{player.role || 'Unassigned'}</span></td>
                <td><span className={`overall-badge ${overallClass(Number(player?.Rating ?? player?.rating ?? player?.overall_rating ?? 0))}`}>{getDisplayRating(player)}</span></td>
                <td className="stat">{formatPrice(player.price)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default PlayerTable
