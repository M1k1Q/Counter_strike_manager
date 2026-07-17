import React from 'react'

function PlayerModal({
  player,
  selectedTeam,
  onClose,
  onAction,
  statusMessage,
  isSubmitting,
  getTeamName,
  negotiation,
}) {
  if (!player) return null

  const isFreeAgent = player.team_id === null
  const isOnSelectedTeam = selectedTeam?.id === player.team_id
  const hasNegotiation = negotiation && negotiation.player_id === player.id
  const isPendingNegotiation = hasNegotiation && negotiation.status === 'pending'
  const actionLabel = isFreeAgent
    ? 'Sign'
    : isOnSelectedTeam
    ? 'Release'
    : isPendingNegotiation
    ? 'Counter Offer'
    : 'Negotiate'

  const negotiationDetails = isPendingNegotiation ? (
    <div className="modal-negotiation-details">
      <strong>Negotiation active</strong>
      <p>Round: {negotiation.rounds + 1}</p>
      <p>Offer: ${negotiation.offer_amount.toLocaleString()}</p>
      <p>Success chance: {Math.round(negotiation.success_chance)}%</p>
    </div>
  ) : null

  const actionDisabled = isSubmitting || (hasNegotiation && ['accepted', 'rejected'].includes(negotiation.status))

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <header className="modal-header">
          <div>
            <h2>{player.player}</h2>
            <p className="modal-subtitle">{player.role || 'Unassigned role'}</p>
          </div>
          <button className="modal-close" type="button" onClick={onClose}>
            ×
          </button>
        </header>

        <div className="modal-content">
          <div className="modal-details-grid">
            <div>
              <span>Overall</span>
              <strong>{player.Rating ?? player.rating ?? player.overall_rating ?? 'N/A'}</strong>
            </div>
            <div>
              <span>Price</span>
              <strong>${player.price?.toLocaleString() ?? '0'}</strong>
            </div>
            <div>
              <span>IGL Probability</span>
              <strong>{player.igl_score != null ? `${player.igl_score.toFixed(0)}%` : 'N/A'}</strong>
            </div>
            <div>
              <span>Current team</span>
              <strong>{isFreeAgent ? 'Free Agent' : getTeamName(player.team_id)}</strong>
            </div>
          </div>

          <div className="modal-actions">
            <button className="btn-primary" type="button" onClick={() => onAction(player)} disabled={actionDisabled}>
              {isSubmitting ? 'Working…' : actionLabel}
            </button>
            <button className="btn-secondary" type="button" onClick={onClose}>
              Close
            </button>
          </div>
          {negotiationDetails}
          {statusMessage && (
            <div className="modal-status">
              {statusMessage}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default PlayerModal
