import test from 'node:test'
import assert from 'node:assert/strict'
import { completedSeasonYear, recapPlayers, recapDuration } from '../src/components/recapSequence.js'

test('reveal fires only after a successful December year rollover', () => {
  const december = { current_year: 2029, current_month: 12, tournament_start_pending: false }
  assert.equal(completedSeasonYear(december, { current_year: 2030, current_month: 1 }), 2029)
  assert.equal(completedSeasonYear(december, { current_year: 2029, current_month: 12 }), null)
  assert.equal(completedSeasonYear({ ...december, tournament_start_pending: true }, { current_year: 2030 }), null)
  assert.equal(completedSeasonYear({ ...december, current_month: 11 }, { current_year: 2029, current_month: 12 }), null)
  assert.equal(completedSeasonYear(null, { current_year: 2030 }), null)
})

test('countdown preserves archived ranks and excludes players outside the Top 20', () => {
  const season = { players: [{ rank: 1, player_name: 'Winner' }, { rank: 21 }, { rank: 20 }, { rank: 3 }] }
  const original = JSON.stringify(season)
  assert.deepEqual(recapPlayers(season).map(p => p.rank), [20, 3, 1])
  assert.equal(JSON.stringify(season), original)
  assert.equal(recapPlayers(season).at(-1).player_name, 'Winner')
})

test('short or empty seasons are handled without inventing ranking entries', () => {
  assert.deepEqual(recapPlayers(null), [])
  assert.deepEqual(recapPlayers({ players: [] }), [])
  assert.equal(recapPlayers({ players: [{ rank: 1 }] }).length, 1)
})

test('full ceremony is about 25 seconds and gives the podium longer reveals', () => {
  const players = Array.from({ length: 20 }, (_, i) => ({ rank: i + 1 }))
  const duration = recapDuration(null) + players.reduce((sum, player) => sum + recapDuration(player), 0)
  assert.ok(duration >= 24000 && duration <= 28000)
  assert.ok(recapDuration({ rank: 1 }) > recapDuration({ rank: 3 }))
  assert.ok(recapDuration({ rank: 3 }) > recapDuration({ rank: 4 }))
})
