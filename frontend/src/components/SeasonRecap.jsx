import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { recapDuration, recapPlayers } from './recapSequence.js'
import './SeasonRecap.css'

export default function SeasonRecap({ season, onClose }) {
  const players = useMemo(() => recapPlayers(season), [season])
  const [index, setIndex] = useState(-1)
  const [paused, setPaused] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  const dialogRef = useRef(null)
  const currentRef = useRef(null)
  const player = players[index]
  const finished = index >= players.length

  useEffect(() => {
    const dialog = dialogRef.current
    const previousFocus = document.activeElement
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    dialog.showModal()
    return () => {
      dialog.close()
      document.body.style.overflow = previousOverflow
      previousFocus?.focus?.()
    }
  }, [])

  useEffect(() => {
    if (paused || finished) return undefined
    const timeout = window.setTimeout(() => setIndex(value => value + 1), recapDuration(player))
    return () => window.clearTimeout(timeout)
  }, [index, player, paused, finished])

  useEffect(() => {
    currentRef.current?.scrollIntoView?.({ block: 'nearest' })
  }, [index])

  return createPortal(
    <dialog ref={dialogRef} className="season-recap" aria-labelledby="recap-title" onCancel={event => { event.preventDefault(); onClose() }}>
      <div className="recap-shell">
        <header className="recap-header">
          <div><span className="recap-kicker">CS MANAGER / SEASON HONORS</span><h2 id="recap-title">{season.year} · The Top 20</h2></div>
          <button type="button" className="recap-text-button" autoFocus onClick={onClose}>{finished ? 'Continue to next season' : 'Skip ceremony'} <span aria-hidden="true">↗</span></button>
        </header>
        <div className={`recap-body ${finished ? 'recap-finished' : ''}`}>
          <aside className="recap-list" aria-label="Season ranking countdown">
            <span className="recap-kicker">{finished ? 'THE FINAL RANKINGS' : 'THE COUNTDOWN'}</span>
            <ol>{(finished ? [...players].reverse() : players).map((entry, position) => {
              const revealed = finished || position <= index
              const active = !finished && position === index
              return <li key={entry.player_id} ref={active ? currentRef : null} className={`${revealed ? 'revealed' : ''} ${active ? 'current' : ''}`} aria-current={active ? 'step' : undefined}>
                <span className="recap-list-rank">{String(entry.rank).padStart(2, '0')}</span>
                <span className="recap-list-name">{revealed ? entry.player_name : '—'}{revealed && <small>{entry.team_name}</small>}</span>
                {revealed && <b>{Number(entry.rating).toFixed(2)}</b>}
              </li>
            })}</ol>
          </aside>
          <section className="recap-stage" aria-live="polite" aria-atomic="true">
            {finished ? <div className="recap-finale">
              <span className="recap-kicker">A SEASON TO REMEMBER</span>
              <h3>The names.<br />The moments.<br /><em>The legacy.</em></h3>
              <p>{players.length} standouts. One unforgettable season.</p>
              <button type="button" className="btn-primary" onClick={onClose}>Continue to next season →</button>
              <button type="button" className="recap-text-button" onClick={() => { setIndex(-1); setPaused(false) }}>Replay countdown</button>
            </div> : player ? <div key={player.player_id} className={`recap-player ${player.rank <= 3 ? 'recap-podium' : ''}`}>
              <span className="recap-rank-ghost" aria-hidden="true">{String(player.rank).padStart(2, '0')}</span>
              <span className="recap-kicker">{player.rank === 1 ? 'PLAYER OF THE YEAR' : player.rank <= 3 ? 'THE ELITE' : 'THE SEASON’S STANDOUTS'}</span>
              <div className="recap-rank">#{player.rank}<span> / {season.year}</span></div>
              <h3>{player.player_name}</h3>
              <p className="recap-team">{player.team_name} <span> / {player.role || 'Player'}</span></p>
              <div className="recap-stat-strip">
                <div><strong>{Number(player.rating).toFixed(2)}</strong><small>SEASON RATING</small></div>
                <div><strong>{player.maps_played}</strong><small>MAPS PLAYED</small></div>
                <div><strong>{player.mvp_count || 0}<span> / {player.evp_count || 0}</span></strong><small>MVP / EVP</small></div>
              </div>
              <div className={`recap-slide-progress ${paused ? 'paused' : ''}`} style={{ '--slide-duration': `${recapDuration(player)}ms` }} aria-hidden="true"><span /></div>
            </div> : <div className="recap-intro">
              <span className="recap-kicker">THE SEASON IS COMPLETE</span>
              <h3>Twenty places.<br /><em>One legacy.</em></h3>
              <p>The players who defined {season.year}.</p>
            </div>}
          </section>
        </div>
        <footer className="recap-footer">
          <span>{finished ? `${season.year} season archived` : `${Math.max(0, index + 1)} / ${players.length} revealed`}</span>
          {!finished && <div>
            <button type="button" className="recap-text-button" onClick={() => setPaused(value => !value)}>{paused ? 'Play' : 'Pause'}</button>
            <button type="button" className="recap-text-button" onClick={() => setIndex(value => value + 1)}>Next player →</button>
            <button type="button" className="recap-text-button" onClick={() => setIndex(players.length)}>Show full list</button>
          </div>}
        </footer>
      </div>
    </dialog>, document.body,
  )
}
