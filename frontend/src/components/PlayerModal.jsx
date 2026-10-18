import React, { useState, useEffect } from 'react'
import StatBar from './StatBar'

function PlayerModal({
  player,
  selectedTeam,
  onClose,
  onAction,
  statusMessage,
  isSubmitting,
  getTeamName,
  negotiation,
  transferLockName,
}) {
  const [offerAmount, setOfferAmount] = useState('')
  const [offerError, setOfferError] = useState(null)

  const isFreeAgent = player ? player.team_id === null : false
  const isOnSelectedTeam = selectedTeam?.id === player?.team_id
  const isNegotiationMode = player && !isFreeAgent && !isOnSelectedTeam
  const hasNegotiation = negotiation && negotiation.player_id === player?.id
  const isPendingNegotiation = hasNegotiation && negotiation.status === 'pending'

  const basePrice = player?.price || 50000

  // Pre-fill offer when player changes
  useEffect(() => {
    if (!player) return
    if (isPendingNegotiation) {
      const bump = Math.round(negotiation.offer_amount * 1.1)
      setOfferAmount(String(bump))
    } else {
      setOfferAmount(String(basePrice))
    }
    setOfferError(null)
  }, [player?.id, isPendingNegotiation])

  if (!player) return null

  const actionLabel = isFreeAgent
    ? 'Sign'
    : isOnSelectedTeam
    ? 'Release'
    : isPendingNegotiation
    ? 'Counter Offer'
    : 'Make Offer'

  const parsedOffer = parseInt(offerAmount.replace(/[^0-9]/g, ''), 10)
  const offerRatio = parsedOffer / basePrice
  const isUntouchableHint = selectedTeam && player.team_id !== null
  const sourceTeam = isNegotiationMode ? getTeamName(player.team_id) : null

  // Thresholds helpers
  const minToNegotiate = basePrice * (isUntouchableHint ? 1.0 : 1.0)
  const likelyAccept = basePrice * 1.5

  const getOfferMeterColor = () => {
    if (offerRatio >= 2.5) return '#22c55e'
    if (offerRatio >= 1.5) return '#eab308'
    if (offerRatio >= 1.0) return '#f97316'
    return '#ef4444'
  }

  const getOfferLabel = () => {
    if (offerRatio >= 3.0) return '🔥 Irresistible offer'
    if (offerRatio >= 2.5) return '✅ Very likely accepted'
    if (offerRatio >= 2.0) return '🟡 Strong offer'
    if (offerRatio >= 1.5) return '🟠 Fair offer'
    if (offerRatio >= 1.0) return '⚠️ Low — may be rejected'
    return '❌ Below market value'
  }

  const meterPercent = Math.min(100, Math.max(0, (offerRatio / 3.0) * 100))

  const handleSubmit = () => {
    if (isNegotiationMode) {
      if (!parsedOffer || parsedOffer < 1000) {
        setOfferError('Please enter a valid offer amount (minimum $1,000).')
        return
      }
      if (parsedOffer > 50_000_000) {
        setOfferError('Offer cannot exceed $50,000,000.')
        return
      }
      setOfferError(null)
    }
    onAction(player, isNegotiationMode ? parsedOffer : null)
  }

  const actionDisabled = Boolean(transferLockName) || isSubmitting || (hasNegotiation && ['accepted', 'rejected'].includes(negotiation.status))

  const negotiationDetails = isPendingNegotiation ? (
    <div className="modal-negotiation-details">
      <strong>Negotiation active</strong>
      <p>Round: {negotiation.rounds + 1}</p>
      <p>Last Offer: ${negotiation.offer_amount.toLocaleString()}</p>
      <p>Success Chance: {Math.round(negotiation.success_chance)}%</p>
    </div>
  ) : null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className={`modal-card ${isNegotiationMode ? 'negotiation-modal' : ''}`} onClick={(e) => e.stopPropagation()}>
        <header className="modal-header">
          <div>
            <h2>{player.player}</h2>
            <p className="modal-subtitle">
              {player.selected_role ? (
                <>
                  <span className="selected-role-tag">{player.selected_role}</span>
                  <span className="classified-role-tag"> (ML: {player.role})</span>
                </>
              ) : (
                player.role || 'Unassigned role'
              )}
            </p>
          </div>
          <button className="modal-close" type="button" onClick={onClose}>×</button>
        </header>

        <div className="modal-content">
          {transferLockName && (
            <p className="transfer-lock-notice">
              Transfers are locked while your team is participating in {transferLockName}.
            </p>
          )}
          <div className="modal-details-grid">
            <div>
              <span>Overall</span>
              <strong>{player.Rating ?? player.rating ?? player.overall_rating ?? 'N/A'}</strong>
            </div>
            <div>
              <span>Market Value</span>
              <strong>${basePrice.toLocaleString()}</strong>
            </div>
            <div>
              <span>IGL Probability</span>
              <strong>{player.igl_score != null ? `${player.igl_score.toFixed(0)}%` : 'N/A'}</strong>
            </div>
            <div>
              <span>Current Team</span>
              <strong>{isFreeAgent ? 'Free Agent' : getTeamName(player.team_id)}</strong>
            </div>
          </div>

          {/* Stat bars */}
          {(player.firepower != null || player.sniping != null || player.opening != null || player.clutching != null) && (
            <div className="modal-stats-section">
              <StatBar label="Firepower" value={player.firepower} />
              <StatBar label="Sniping" value={player.sniping} />
              <StatBar label="Opening" value={player.opening} />
              <StatBar label="Clutching" value={player.clutching} />
              <StatBar label="Entrying" value={player.entrying} />
              <StatBar label="Trading" value={player.trading} />
              <StatBar label="Utility" value={player.utility} />
            </div>
          )}

          {/* Offer Amount Section — only for negotiation */}
          {isNegotiationMode && (
            <div className="offer-section">
              <label className="offer-label">
                {isPendingNegotiation ? 'Counter Offer Amount' : 'Your Offer'}
              </label>

              {/* Quick preset buttons */}
              <div className="offer-presets">
                {[
                  { label: '1×', mult: 1.0 },
                  { label: '1.5×', mult: 1.5 },
                  { label: '2×', mult: 2.0 },
                  { label: '2.5×', mult: 2.5 },
                ].map(({ label, mult }) => (
                  <button
                    key={label}
                    type="button"
                    className={`offer-preset-btn ${Math.abs(offerRatio - mult) < 0.05 ? 'active' : ''}`}
                    onClick={() => setOfferAmount(String(Math.round(basePrice * mult)))}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {/* Amount input */}
              <div className="offer-input-row">
                <span className="offer-currency">$</span>
                <input
                  id="offer-amount-input"
                  type="number"
                  className="offer-input"
                  min="1000"
                  step="10000"
                  value={offerAmount}
                  onChange={(e) => {
                    setOfferAmount(e.target.value)
                    setOfferError(null)
                  }}
                />
              </div>

              {/* Offer strength meter */}
              {!isNaN(parsedOffer) && parsedOffer > 0 && (
                <div className="offer-meter-container">
                  <div className="offer-meter-track">
                    <div
                      className="offer-meter-fill"
                      style={{ width: `${meterPercent}%`, background: getOfferMeterColor() }}
                    />
                  </div>
                  <div className="offer-meter-label" style={{ color: getOfferMeterColor() }}>
                    {getOfferLabel()}
                    <span className="offer-ratio-hint">({offerRatio.toFixed(2)}× market value)</span>
                  </div>
                </div>
              )}

              {offerError && <p className="offer-error">{offerError}</p>}
              <p className="offer-hint">
                {sourceTeam}'s market value: <strong>${basePrice.toLocaleString()}</strong>
              </p>
            </div>
          )}

          {negotiationDetails}

          <div className="modal-actions">
            <button
              className="btn-primary"
              type="button"
              onClick={handleSubmit}
              disabled={actionDisabled}
            >
              {isSubmitting ? 'Working…' : actionLabel}
            </button>
            <button className="btn-secondary" type="button" onClick={onClose}>
              Close
            </button>
          </div>

          {statusMessage && (
            <div className="modal-status">{statusMessage}</div>
          )}
        </div>
      </div>
    </div>
  )
}

export default PlayerModal
