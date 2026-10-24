// Only a successful December -> next-year transition earns an automatic reveal.
export function completedSeasonYear(before, after) {
  if (!before || !after || before.tournament_start_pending || before.current_month !== 12) return null
  return after.current_year === before.current_year + 1 ? before.current_year : null
}

export function recapPlayers(season) {
  return [...(season?.players || [])]
    .filter(player => player.rank >= 1 && player.rank <= 20)
    .sort((a, b) => b.rank - a.rank)
}

export function recapDuration(player) {
  if (!player) return 1400
  return player.rank === 1 ? 3200 : player.rank <= 3 ? 2200 : 950
}
