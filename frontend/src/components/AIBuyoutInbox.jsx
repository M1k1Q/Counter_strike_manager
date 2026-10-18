import { useState } from 'react'
import './AIBuyoutInbox.css'

/**
 * AIBuyoutInbox
 * Renders a notification bell that opens an inbox panel.
 * Each pending AI buyout offer shows Sell / Reject / Negotiate actions.
 */
export default function AIBuyoutInbox({ offers, onRefresh, transferLockName = null }) {
  const [open, setOpen] = useState(false)
  const [activeOffer, setActiveOffer] = useState(null)
  const [negotiating, setNegotiating] = useState(false)
  const [counterAmount, setCounterAmount] = useState('')
  const [actionMsg, setActionMsg] = useState(null)
  const [loading, setLoading] = useState(false)

  const pendingCount = offers.filter((o) => o.status === 'pending').length

  const fmt = (n) =>
    new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
    }).format(n || 0)

  const handleAccept = async (offer) => {
    setLoading(true)
    setActionMsg(null)
    try {
      const res = await fetch(`/ai-buyouts/${offer.id}/accept`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed to accept offer')
      setActionMsg(`✅ Deal done! ${offer.player_name} sold to ${offer.ai_team_name} for ${fmt(data.current_offer)}.`)
      setActiveOffer(null)
      setNegotiating(false)
      onRefresh()
    } catch (err) {
      setActionMsg(`❌ ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleReject = async (offer) => {
    setLoading(true)
    setActionMsg(null)
    try {
      const res = await fetch(`/ai-buyouts/${offer.id}/reject`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed to reject offer')
      setActionMsg(`🚫 Offer from ${offer.ai_team_name} rejected.`)
      setActiveOffer(null)
      setNegotiating(false)
      onRefresh()
    } catch (err) {
      setActionMsg(`❌ ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleCounter = async (offer) => {
    const amount = parseInt(counterAmount, 10)
    if (!amount || amount <= 0) {
      setActionMsg('Please enter a valid counter amount.')
      return
    }
    setLoading(true)
    setActionMsg(null)
    try {
      const res = await fetch(`/ai-buyouts/${offer.id}/counter`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ counter_amount: amount }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Counter failed')

      if (data.status === 'accepted') {
        setActionMsg(`✅ ${offer.ai_team_name} accepted your counter — ${offer.player_name} sold for ${fmt(data.current_offer)}!`)
        setActiveOffer(null)
        setNegotiating(false)
        onRefresh()
      } else if (data.status === 'collapsed') {
        setActionMsg(`💔 ${offer.ai_team_name} walked away — negotiations collapsed.`)
        setActiveOffer(null)
        setNegotiating(false)
        onRefresh()
      } else {
        // AI made a new counter
        setActiveOffer(data)
        setCounterAmount('')
        setActionMsg(
          `🔄 ${data.ai_team_name} raised their offer to ${fmt(data.current_offer)} (round ${data.rounds}/${3}).`
        )
      }
    } catch (err) {
      setActionMsg(`❌ ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  const openOffer = (offer) => {
    setActiveOffer(offer)
    setNegotiating(false)
    setCounterAmount('')
    setActionMsg(null)
  }

  const closeSidebar = () => {
    setOpen(false)
    setActiveOffer(null)
    setNegotiating(false)
    setActionMsg(null)
    setCounterAmount('')
  }

  return (
    <>
      {/* Bell icon in navbar area */}
      <button
        className={`buyout-bell ${pendingCount > 0 ? 'buyout-bell--active' : ''}`}
        onClick={() => setOpen((v) => !v)}
        title="AI Transfer Offers"
        id="ai-buyout-inbox-btn"
        type="button"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="22" height="22">
          <path d="M12 22c1.1 0 2-.9 2-2h-4a2 2 0 002 2zm6-6V11c0-3.07-1.64-5.64-4.5-6.32V4a1.5 1.5 0 00-3 0v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/>
        </svg>
        {pendingCount > 0 && (
          <span className="buyout-badge">{pendingCount}</span>
        )}
      </button>

      {/* Slide-in panel */}
      {open && (
        <div className="buyout-overlay" onClick={closeSidebar}>
          <aside className="buyout-panel" onClick={(e) => e.stopPropagation()}>
            <div className="buyout-panel__header">
              <h2>📨 Transfer Offers</h2>
              <button className="buyout-close" onClick={closeSidebar} type="button">✕</button>
            </div>

            {actionMsg && (
              <div className="buyout-action-msg">{actionMsg}</div>
            )}
            {transferLockName && (
              <div className="buyout-action-msg">
                Transfers are locked while your team is participating in {transferLockName}. You can still reject offers.
              </div>
            )}

            {offers.length === 0 ? (
              <p className="buyout-empty">No incoming transfer offers right now.</p>
            ) : (
              <ul className="buyout-list">
                {offers.map((offer) => (
                  <li
                    key={offer.id}
                    className={`buyout-item buyout-item--${offer.status} ${activeOffer?.id === offer.id ? 'buyout-item--selected' : ''}`}
                    onClick={() => offer.status === 'pending' && openOffer(offer)}
                  >
                    <div className="buyout-item__top">
                      <span className="buyout-item__team">
                        {offer.ai_team_ranking ? `#${offer.ai_team_ranking} ` : ''}{offer.ai_team_name}
                      </span>
                      <span className={`buyout-status buyout-status--${offer.status}`}>{offer.status}</span>
                    </div>
                    <div className="buyout-item__player">{offer.player_name}</div>
                    <div className="buyout-item__offer">{fmt(offer.current_offer)}</div>

                    {activeOffer?.id === offer.id && offer.status === 'pending' && (
                      <div className="buyout-actions" onClick={(e) => e.stopPropagation()}>
                        {!negotiating ? (
                          <>
                            <button
                              className="buyout-btn buyout-btn--sell"
                              onClick={() => handleAccept(offer)}
                              disabled={loading || Boolean(transferLockName)}
                              type="button"
                            >
                              💰 Sell
                            </button>
                            <button
                              className="buyout-btn buyout-btn--negotiate"
                              onClick={() => setNegotiating(true)}
                              disabled={loading || Boolean(transferLockName)}
                              type="button"
                            >
                              🤝 Negotiate
                            </button>
                            <button
                              className="buyout-btn buyout-btn--reject"
                              onClick={() => handleReject(offer)}
                              disabled={loading}
                              type="button"
                            >
                              ❌ Reject
                            </button>
                          </>
                        ) : (
                          <div className="buyout-counter">
                            <p className="buyout-counter__hint">
                              Round {activeOffer.rounds}/3 · AI ceiling ≈ {fmt(activeOffer.initial_offer * 2.5)}
                            </p>
                            <input
                              type="number"
                              className="buyout-counter__input"
                              placeholder="Your asking price…"
                              value={counterAmount}
                              disabled={Boolean(transferLockName)}
                              onChange={(e) => setCounterAmount(e.target.value)}
                            />
                            <div className="buyout-counter__row">
                              <button
                                className="buyout-btn buyout-btn--sell"
                                onClick={() => handleCounter(activeOffer)}
                                disabled={loading || !counterAmount || Boolean(transferLockName)}
                                type="button"
                              >
                                Submit
                              </button>
                              <button
                                className="buyout-btn buyout-btn--reject"
                                onClick={() => { setNegotiating(false); setCounterAmount('') }}
                                disabled={loading}
                                type="button"
                              >
                                Back
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </aside>
        </div>
      )}
    </>
  )
}
