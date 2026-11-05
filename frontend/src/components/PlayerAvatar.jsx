import { useState } from 'react'
import playerImages from '../data/playerImages.json'
import './PlayerAvatar.css'

// Static identity mapping: no API calls or database lookups for photos.
export default function PlayerAvatar({ player, size = 40, eager = false }) {
  const name = (player?.player || player?.player_name)?.trim() || '?'
  const entry = playerImages[name.toLowerCase()]
  const src = typeof entry === 'string' ? entry : (size > 40 ? entry?.profile || entry?.thumbnail : entry?.thumbnail || entry?.profile)
  // Keying the image state by URL resets failures when the selected player changes.
  return <AvatarImage key={src || name} src={src} name={name} size={size} eager={eager} />
}

function AvatarImage({ src, name, size, eager }) {
  const [failed, setFailed] = useState(false)
  return (
    <span className="player-avatar" style={{ width: size, height: size }} aria-hidden="true">
      {src && !failed ? (
        <img src={src} alt="" width={size} height={size}
          loading={eager ? 'eager' : 'lazy'} decoding="async"
          onError={() => setFailed(true)} />
      ) : name.slice(0, 2).toUpperCase()}
    </span>
  )
}
