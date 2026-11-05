import { useEffect, useRef, useState } from 'react'
import './EventAtmosphere.css'

export default function EventAtmosphere() {
  const scene = useRef(null)
  const [enabled, setEnabled] = useState(() => {
    try { return localStorage.getItem('cs_manager_motion') !== 'off' } catch { return true }
  })
  useEffect(() => {
    const element = scene.current
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)')
    const fine = window.matchMedia('(hover: hover) and (pointer: fine)')
    let frame = 0
    let x = 0
    let y = 0
    const reset = () => {
      element.style.setProperty('--scene-x', '0px')
      element.style.setProperty('--scene-y', '0px')
    }
    const move = event => {
      if (!enabled || reduced.matches || !fine.matches || document.hidden) return
      x = (event.clientX / window.innerWidth - .5) * 18
      y = (event.clientY / window.innerHeight - .5) * 12
      if (!frame) frame = requestAnimationFrame(() => {
        element.style.setProperty('--scene-x', `${x}px`)
        element.style.setProperty('--scene-y', `${y}px`)
        frame = 0
      })
    }
    const visibility = () => { element.dataset.sleeping = String(document.hidden); if (document.hidden) reset() }
    const preferences = () => { reset() }
    visibility()
    window.addEventListener('pointermove', move, { passive: true })
    window.addEventListener('blur', reset)
    document.addEventListener('visibilitychange', visibility)
    reduced.addEventListener('change', preferences)
    fine.addEventListener('change', preferences)
    reset()
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('pointermove', move)
      window.removeEventListener('blur', reset)
      document.removeEventListener('visibilitychange', visibility)
      reduced.removeEventListener('change', preferences)
      fine.removeEventListener('change', preferences)
    }
  }, [enabled])
  const toggle = () => {
    setEnabled(value => {
      try { localStorage.setItem('cs_manager_motion', value ? 'off' : 'on') } catch { /* Storage may be unavailable. */ }
      return !value
    })
  }
  return <>
    <div ref={scene} className="event-atmosphere" data-motion={enabled ? 'on' : 'off'} aria-hidden="true">
      <div className="atmosphere-parallax">
        <div className="atmosphere-orbit"><div className="atmosphere-globe" /><div className="atmosphere-horizon" /></div>
        <svg className="atmosphere-shards" viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice">
          <g className="shard-bank shard-bank-left">
            <path d="M0 40 210 160 50 300Z" /><path d="M0 40 50 300 0 420Z" />
            <path d="M50 300 210 160 145 430Z" /><path d="M0 420 145 430 80 610Z" />
            <path d="M0 720 140 640 80 900Z" /><path d="M0 1000 80 900 210 1000Z" />
          </g>
          <g className="shard-bank shard-bank-right">
            <path d="M1600 80 1450 200 1600 370Z" /><path d="M1450 200 1360 400 1600 370Z" />
            <path d="M1600 370 1360 400 1490 570Z" /><path d="M1600 650 1490 570 1400 800Z" />
            <path d="M1600 650 1400 800 1600 940Z" /><path d="M1400 800 1450 1000 1600 940Z" />
          </g>
        </svg>
        <div className="atmosphere-ribbon ribbon-one" /><div className="atmosphere-ribbon ribbon-two" />
        <div className="atmosphere-grid" />
      </div>
      <div className="atmosphere-vignette" />
    </div>
    <button className="atmosphere-toggle" type="button" aria-pressed={enabled} aria-label="Background motion" title="Toggle decorative background motion" onClick={toggle}>
      <span aria-hidden="true">{enabled ? '◈' : '◇'}</span> Motion {enabled ? 'on' : 'off'}
    </button>
  </>
}
