import { useState, useEffect } from 'react'
import './TournamentCalendar.css'

const MONTH_NAMES = [
  '', 'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
]

function TournamentCalendar({
  manager,
  selectedTeam,
  onUpdateManager,
  onActiveTournamentChange,
  onTransferLockChange,
}) {
  const [calendarData, setCalendarData] = useState(null)
  const [eventHistory, setEventHistory] = useState([])
  const [selectedEventId, setSelectedEventId] = useState('')
  const [historyTournament, setHistoryTournament] = useState(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState(null)
  const [rankings, setRankings] = useState([])
  const [activeSubTab, setActiveSubTab] = useState('groups') // 'groups', 'playoffs', 'seeds', 'rankings', 'stats'
  const [activeGroup, setActiveGroup] = useState('A')
  const [loading, setLoading] = useState(true)
  const [advancing, setAdvancing] = useState(false)
  const [calendarActionError, setCalendarActionError] = useState(null)
  const [simulatingMatchId, setSimulatingMatchId] = useState(null)
  const [simulatingAi, setSimulatingAi] = useState(false)
  const [selectedScoreboardMatch, setSelectedScoreboardMatch] = useState(null)
  const [activeScoreboardMapIndex, setActiveScoreboardMapIndex] = useState(0)
  const [tournamentStats, setTournamentStats] = useState(null)
  const [statsLoading, setStatsLoading] = useState(false)
  const [statsTeamFilter, setStatsTeamFilter] = useState('all')
  const [statsStageFilter, setStatsStageFilter] = useState('all')
  const [statsAwardFilter, setStatsAwardFilter] = useState('all')

  const handleSelectEvent = async (event) => {
    const tournamentId = String(event.id)
    const currentTournament = calendarData?.active_tournament
    const isCurrentTournament = currentTournament?.id === event.id
    setActiveSubTab('groups')
    setHistoryTournament(null)
    setTournamentStats(null)
    setHistoryError(null)
    setStatsTeamFilter('all')
    setStatsStageFilter('all')
    setStatsAwardFilter('all')

    if (Number(selectedEventId) === event.id || isCurrentTournament) {
      setSelectedEventId('')
      onActiveTournamentChange?.(currentTournament?.name || null)
      return
    }

    if (event.status !== 'completed' && event.status !== 'active') return

    setSelectedEventId(tournamentId)
    onActiveTournamentChange?.(event.name)

    try {
      setHistoryLoading(true)
      const detailRes = await fetch(`/tournaments/${tournamentId}`)
      if (!detailRes.ok) throw new Error(`Event details returned HTTP ${detailRes.status}`)
      const detail = await detailRes.json()
      setHistoryTournament(detail)
      if (detail.status === 'completed') {
        const statsRes = await fetch(`/tournaments/${tournamentId}/stats`)
        if (!statsRes.ok) throw new Error(`Event statistics returned HTTP ${statsRes.status}`)
        setTournamentStats(await statsRes.json())
        setActiveSubTab('stats')
      }
    } catch (err) {
      console.error('Failed to load tournament:', err)
      setHistoryError('Unable to load this event. Please try again.')
    } finally {
      setHistoryLoading(false)
    }
  }

  const fetchTournamentStats = async (tournamentId) => {
    if (!tournamentId) return
    try {
      setStatsLoading(true)
      const res = await fetch(`/tournaments/${tournamentId}/stats`)
      if (res.ok) {
        const data = await res.json()
        setTournamentStats(data)
      }
    } catch (err) {
      console.error('Failed to fetch tournament stats:', err)
    } finally {
      setStatsLoading(false)
    }
  }

  const fetchCalendarData = async () => {
    try {
      setLoading(true)
      const res = await fetch('/tournaments/calendar')
      if (res.ok) {
        const data = await res.json()
        setCalendarData(data)
        setStatsTeamFilter('all')
        setStatsStageFilter('all')
        setStatsAwardFilter('all')
        onActiveTournamentChange?.(data.active_tournament?.name || null)
        onTransferLockChange?.(
          data.active_tournament?.status === 'active'
            && data.active_tournament.is_manager_participating
            && !data.tournament_start_pending
            ? data.active_tournament.name
            : null
        )
        if (data.manager_budget && onUpdateManager) {
          onUpdateManager({
            ...manager,
            budget: data.manager_budget,
            career_points: data.manager_career_points,
          })
        }
      }
    } catch (err) {
      console.error('Failed to fetch calendar:', err)
    } finally {
      setLoading(false)
    }
  }

  const fetchRankings = async () => {
    try {
      const res = await fetch('/tournaments/rankings/global')
      if (res.ok) {
        const data = await res.json()
        setRankings(data)
      }
    } catch (err) {
      console.error('Failed to fetch rankings:', err)
    }
  }

  useEffect(() => {
    fetchCalendarData()
    fetchRankings()
    fetch('/tournaments/history')
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        setEventHistory(await res.json())
      })
      .catch((err) => console.error('Failed to fetch tournament history:', err))
  }, [])

  const handleAdvanceMonth = async () => {
    try {
      setAdvancing(true)
      setCalendarActionError(null)
      const endpoint = calendarData?.tournament_start_pending
        ? '/tournaments/calendar/start'
        : '/tournaments/calendar/advance'
      const res = await fetch(endpoint, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)

      setCalendarData(data)
      onActiveTournamentChange?.(data.active_tournament?.name || null)
      onTransferLockChange?.(
        data.active_tournament?.status === 'active'
          && data.active_tournament.is_manager_participating
          && !data.tournament_start_pending
          ? data.active_tournament.name
          : null
      )
      fetchRankings()
      if (onUpdateManager) {
        onUpdateManager({
          ...manager,
          budget: data.manager_budget,
          career_points: data.manager_career_points,
        })
      }
    } catch (err) {
      console.error('Failed to advance calendar:', err)
      setCalendarActionError(err.message || 'Unable to advance the calendar.')
    } finally {
      setAdvancing(false)
    }
  }

  const handleSimulateMatch = async (matchId) => {
    if (isCompletedEvent || isSpectatorView || calendarData?.tournament_start_pending) return

    try {
      setSimulatingMatchId(matchId)
      const res = await fetch(`/tournaments/matches/${matchId}/simulate`, { method: 'POST' })
      if (res.ok) {
        const matchData = await res.json()
        setSelectedScoreboardMatch(matchData)
        setActiveScoreboardMapIndex(0)
        // Refresh tournament state
        await fetchCalendarData()
        fetchRankings()
      }
    } catch (err) {
      console.error('Failed to simulate match:', err)
    } finally {
      setSimulatingMatchId(null)
    }
  }

  const handleSimulateAiMatches = async (tournamentId) => {
    if (isCompletedEvent || isSpectatorView || calendarData?.tournament_start_pending) return

    try {
      setSimulatingAi(true)
      const res = await fetch(`/tournaments/${tournamentId}/simulate-ai-round`, { method: 'POST' })
      if (res.ok) {
        await fetchCalendarData()
        fetchRankings()
      }
    } catch (err) {
      console.error('Failed to simulate AI matches:', err)
    } finally {
      setSimulatingAi(false)
    }
  }

  const openScoreboard = (match) => {
    setSelectedScoreboardMatch(match)
    setActiveScoreboardMapIndex(0)
  }

  if (loading && !calendarData) {
    return <div className="loading-state">Loading Tournament Circuit & Calendar...</div>
  }

  const activeTournament = selectedEventId
    ? historyTournament
    : calendarData?.active_tournament
  const circuitEvents = [...new Map([
    ...eventHistory,
    ...(calendarData?.season_tournaments || []),
  ].map((event) => [event.id, event])).values()]
    .sort((a, b) => a.year - b.year || a.month - b.month)
  const isCompletedEvent = activeTournament?.status === 'completed'
  const userTeamId = selectedTeam?.id
  const isPreTournament = Boolean(
    !selectedEventId
      && calendarData?.tournament_start_pending
      && activeTournament?.id === calendarData?.active_tournament_id
  )
  const isSpectatorView = Boolean(
    activeTournament && !isPreTournament && !activeTournament.participants?.some(
      (participant) => participant.team_id === userTeamId
    )
  )
  const leaderboardPlayers = tournamentStats?.player_stats || []
  const teamFilterOptions = [...new Map(
    leaderboardPlayers.map((player) => [player.team_id, player.team_name])
  ).entries()].sort((a, b) => a[1].localeCompare(b[1]))
  const stageLabels = {
    group: 'Group Stage',
    quarterfinal: 'Quarter-finals',
    semifinal: 'Semi-finals',
    final: 'Finals',
  }
  const getPlayerStage = (player) => {
    const placement = (player.placement || '').toLowerCase()
    if (placement.includes('champion') || placement.includes('runner-up')) return 'final'
    if (placement.includes('semi')) return 'semifinal'
    if (placement.includes('quarter')) return 'quarterfinal'
    return 'group'
  }
  const stageFilterOptions = [...new Set(leaderboardPlayers.map(getPlayerStage))]
    .sort((a, b) => ['group', 'quarterfinal', 'semifinal', 'final'].indexOf(a) -
      ['group', 'quarterfinal', 'semifinal', 'final'].indexOf(b))
  const filteredLeaderboardPlayers = leaderboardPlayers.filter((player) => {
    const matchesTeam = statsTeamFilter === 'all' || String(player.team_id) === statsTeamFilter
    const matchesStage = statsStageFilter === 'all' || getPlayerStage(player) === statsStageFilter
    const matchesAward = statsAwardFilter === 'all' ||
      (statsAwardFilter === 'none'
        ? !player.award
        : statsAwardFilter === 'EVP'
          ? player.award?.startsWith('EVP')
          : player.award === statsAwardFilter)
    return matchesTeam && matchesStage && matchesAward
  })
  const refreshSelectedEvent = async () => {
    const tournamentId = selectedEventId || (isSpectatorView ? activeTournament?.id : null)
    if (!tournamentId) return
    try {
      setHistoryLoading(true)
      const detailRes = await fetch(`/tournaments/${tournamentId}`)
      if (!detailRes.ok) throw new Error(`Event details returned HTTP ${detailRes.status}`)
      const detail = await detailRes.json()
      if (selectedEventId) {
        setHistoryTournament(detail)
      } else {
        setCalendarData((current) => ({ ...current, active_tournament: detail }))
      }
      if (detail.status === 'completed') {
        const statsRes = await fetch(`/tournaments/${tournamentId}/stats`)
        if (!statsRes.ok) throw new Error(`Event statistics returned HTTP ${statsRes.status}`)
        setTournamentStats(await statsRes.json())
      }
      setHistoryError(null)
    } catch (err) {
      console.error('Failed to refresh tournament:', err)
      setHistoryError('Unable to refresh this event. Please try again.')
    } finally {
      setHistoryLoading(false)
    }
  }

  // Group stage matches & standings
  const groupMatches = activeTournament?.matches?.filter((m) => m.stage === 'group_stage') || []
  const quarterFinalMatches = activeTournament?.matches?.filter((m) => m.stage === 'quarter_final') || []
  const semiFinalMatches = activeTournament?.matches?.filter((m) => m.stage === 'semi_final') || []
  const grandFinalMatches = activeTournament?.matches?.filter((m) => m.stage === 'grand_final') || []

  const groupNames = ['A', 'B', 'C', 'D']
  const sortStandings = (a, b) => {
    if (b.wins !== a.wins) return b.wins - a.wins
    if (b.round_diff !== a.round_diff) return b.round_diff - a.round_diff
    return a.seed - b.seed
  }
  const groupStandings = Object.fromEntries(
    groupNames.map((groupName) => [
      groupName,
      (activeTournament?.participants || [])
        .filter((participant) => participant.group_name === groupName)
        .sort(sortStandings),
    ])
  )
  const activeGroupMatches = groupMatches.filter((match) => match.group_name === activeGroup)

  return (
    <div className="tournament-calendar-container">
      {/* ── Calendar Hero Bar ── */}
      <div className="calendar-hero-bar">
        <div className="calendar-meta">
          <div className="calendar-date-badge">
            <span className="year">{calendarData?.current_year || 2026} Season</span>
            <span className="month">{MONTH_NAMES[calendarData?.current_month] || 'January'}</span>
          </div>
          <div className="calendar-stats">
            <div className="cal-stat-item">
              <span className="cal-stat-label">Your Team</span>
              <span className="cal-stat-val">
                {selectedTeam ? selectedTeam.name : 'No Team Selected'}
              </span>
            </div>
            <div className="cal-stat-item">
              <span className="cal-stat-label">World Rank</span>
              <span className="cal-stat-val gold">
                {calendarData?.manager_team_rank ? `#${calendarData.manager_team_rank}` : 'Unranked'}
              </span>
            </div>
            <div className="cal-stat-item">
              <span className="cal-stat-label">Career Points</span>
              <span className="cal-stat-val">
                {calendarData?.manager_career_points?.toLocaleString() || 0} pts
              </span>
            </div>
          </div>
        </div>

        <div className="calendar-actions">
          <button
            className="btn-advance-month"
            onClick={handleAdvanceMonth}
            disabled={advancing || Boolean(selectedEventId)}
            title={
              calendarData?.tournament_start_pending
                ? 'Start this month’s tournament'
                : 'Advance the season to next month and open the transfer window'
            }
          >
            {advancing
              ? calendarData?.tournament_start_pending ? 'Starting Tournament...' : 'Advancing Month...'
              : calendarData?.tournament_start_pending ? 'Advance to Tournament 🏆' : 'Next Month ⏩'}
          </button>
          {calendarActionError && <span className="form-error" role="alert">{calendarActionError}</span>}
        </div>
      </div>

      {/* ── Season Circuit Timeline Strip ── */}
      <div className="circuit-strip-wrapper">
        <div className="circuit-strip-title">
          <span>📅 Tournament Circuit, Live Events & Archive</span>
        </div>
        <div className="circuit-strip">
          {circuitEvents.map((tourney) => {
            const isCurrentEvent = tourney.id === calendarData?.active_tournament?.id
            const isSelected = selectedEventId
              ? Number(selectedEventId) === tourney.id
              : isCurrentEvent
            const canOpen = tourney.status === 'completed' || tourney.status === 'active'
            const tierClass =
              tourney.tier === 'Major'
                ? 'tier-major'
                : tourney.tier === 'S-Tier'
                ? 'tier-s'
                : tourney.tier === 'A-Tier'
                ? 'tier-a'
                : tourney.tier === 'B-Tier'
                ? 'tier-b'
                : 'tier-c'

            return (
              <button
                key={tourney.id}
                type="button"
                className={`circuit-card ${isSelected ? 'active' : ''} ${!canOpen ? 'unavailable' : ''}`}
                onClick={() => handleSelectEvent(tourney)}
                disabled={!canOpen || historyLoading}
                title={
                  tourney.status === 'active'
                    ? `Watch ${tourney.name} live (${tourney.year})`
                    : canOpen
                      ? `View ${tourney.name} (${tourney.year})`
                      : 'This event has not started yet'
                }
              >
                <span className="circuit-card-top">
                  <span className="circuit-card-year">{tourney.year}</span>
                  <span className="circuit-card-month">{MONTH_NAMES[tourney.month]}</span>
                  <span className={`circuit-card-tier ${tierClass}`}>{tourney.tier}</span>
                </span>
                <span className="circuit-card-name">{tourney.name}</span>
                <span className="circuit-card-bottom">
                  <span className="circuit-card-prize">${tourney.prize_pool.toLocaleString()}</span>
                  <span className={`circuit-card-status status-${tourney.status}`}>
                    {tourney.status}
                  </span>
                </span>
              </button>
            )
          })}
        </div>
      </div>

      {/* ── Active Tournament Hub ── */}
      {activeTournament ? (
        <div className="active-tournament-hub">
          {(selectedEventId || isSpectatorView || isPreTournament) && (
            <div className="archive-viewing-banner">
              {isPreTournament
                ? 'Transfer window open · Make changes before starting the tournament'
                : isCompletedEvent
                ? `Archived event · ${activeTournament.year}`
                : `Spectating · Your team isn't participating in this event`}
              {(selectedEventId || isSpectatorView) && !isCompletedEvent && (
                <button
                  className="btn-view-score"
                  onClick={refreshSelectedEvent}
                  disabled={historyLoading}
                  style={{ marginLeft: '0.6rem' }}
                >
                  {historyLoading ? 'Refreshing...' : 'Refresh'}
                </button>
              )}
              {historyError && <span role="alert">{historyError}</span>}
            </div>
          )}
          {/* Tournament Header Banner */}
          <div className="tournament-banner">
            <div className="tournament-header-info">
              <div className="tournament-title-row">
                <h2>{activeTournament.name}</h2>
                <span
                  className={`circuit-card-tier ${
                    activeTournament.tier === 'Major'
                      ? 'tier-major'
                      : activeTournament.tier === 'S-Tier'
                      ? 'tier-s'
                      : activeTournament.tier === 'A-Tier'
                      ? 'tier-a'
                      : activeTournament.tier === 'B-Tier'
                      ? 'tier-b'
                      : 'tier-c'
                  }`}
                >
                  {activeTournament.tier}
                </span>
              </div>
              <div className="tournament-meta-tags">
                <span className="meta-tag prize">
                  💰 Prize Pool: ${activeTournament.prize_pool.toLocaleString()}
                </span>
                <span className="meta-tag format">
                  ⚔️ Series Format: {activeTournament.format} (Best of X, Odd)
                </span>
                <span className="meta-tag">
                  🎯 Top {activeTournament.min_rank_required} Cutoff
                </span>
              </div>
            </div>

            {/* Manager Team Invite Status */}
            <div
              className={`tournament-manager-invite-badge ${
                isSpectatorView ? 'invite-not-invited' : 'invite-invited'
              }`}
            >
              {isPreTournament
                ? <>🔓 Transfers are open before the tournament starts</>
                : isSpectatorView
                ? <>👀 Spectating — your team is not in this tournament</>
                : <>🏆 Your team is participating in this tournament</>}
            </div>
          </div>

          {/* Sub Navigation */}
          <div className="tournament-subnav">
            <button
              className={`t-subnav-btn ${activeSubTab === 'groups' ? 'active' : ''}`}
              onClick={() => setActiveSubTab('groups')}
            >
              Group Stage
            </button>
            <button
              className={`t-subnav-btn ${activeSubTab === 'playoffs' ? 'active' : ''}`}
              onClick={() => setActiveSubTab('playoffs')}
            >
              Playoffs Bracket
            </button>
            <button
              className={`t-subnav-btn ${activeSubTab === 'stats' ? 'active' : ''}`}
              onClick={() => {
                setActiveSubTab('stats')
                if (activeTournament?.id) fetchTournamentStats(activeTournament.id)
              }}
            >
              📊 Player Stats
            </button>
            <button
              className={`t-subnav-btn ${activeSubTab === 'seeds' ? 'active' : ''}`}
              onClick={() => setActiveSubTab('seeds')}
            >
              Seeded Teams (16)
            </button>
            <button
              className={`t-subnav-btn ${activeSubTab === 'rankings' ? 'active' : ''}`}
              onClick={() => setActiveSubTab('rankings')}
            >
              World Rankings
            </button>
          </div>

          {/* ── Subtab: Group Stage ── */}
          {activeSubTab === 'groups' && (
            <div className="groups-view-wrapper">
              <div className="group-tabs" role="tablist" aria-label="Group stage groups">
                {groupNames.map((groupName) => (
                  <button
                    key={groupName}
                    className={`group-tab-btn ${activeGroup === groupName ? 'active' : ''}`}
                    onClick={() => setActiveGroup(groupName)}
                    role="tab"
                    aria-selected={activeGroup === groupName}
                  >
                    Group {groupName}
                  </button>
                ))}
              </div>

              <div className="groups-container">
                <div className="group-card">
                  <div className="group-header">
                    <h3>Group {activeGroup}</h3>
                    <span className="qualifying-badge">Top 2 to Quarters</span>
                  </div>
                  <table className="standings-table">
                    <thead>
                      <tr>
                        <th>Pos</th>
                        <th>Team</th>
                        <th>W-L</th>
                        <th>Rounds</th>
                        <th>Diff</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(groupStandings[activeGroup] || []).map((part, idx) => {
                        const isQualifying = idx < 2
                        const isUser = userTeamId && part.team_id === userTeamId
                        return (
                          <tr
                            key={part.id}
                            className={`${isQualifying ? 'qualified' : ''} ${
                              isUser ? 'user-team-row' : ''
                            }`}
                          >
                            <td>#{idx + 1}</td>
                            <td>
                              <span className="team-cell-name">
                                {part.team_name}
                                <span className="seed-num">(Seed {part.seed})</span>
                              </span>
                            </td>
                            <td>{part.wins}-{part.losses}</td>
                            <td>{part.rounds_won}:{part.rounds_lost}</td>
                            <td
                              style={{
                                color:
                                  part.round_diff > 0
                                    ? '#34d399'
                                    : part.round_diff < 0
                                    ? '#f87171'
                                    : 'inherit',
                              }}
                            >
                              {part.round_diff > 0 ? `+${part.round_diff}` : part.round_diff}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Group Matches Schedule */}
              <div className="matches-section" style={{ marginTop: '2rem' }}>
                <div className="matches-section-header">
                  <h4>Group {activeGroup} Matches (Round Robin)</h4>
                  {!isSpectatorView && (
                    <button
                      className="btn-sim-ai"
                      onClick={() => handleSimulateAiMatches(activeTournament.id)}
                      disabled={simulatingAi || isCompletedEvent || isPreTournament}
                    >
                      {simulatingAi ? 'Simulating...' : '⚡ Simulate AI Matches'}
                    </button>
                  )}
                </div>

                <div className="match-list-grid">
                  {activeGroupMatches.map((m) => {
                    const isUserMatch =
                      userTeamId && (m.team1_id === userTeamId || m.team2_id === userTeamId)
                    const isCompleted = m.status === 'completed'
                    const isSimulating = simulatingMatchId === m.id

                    return (
                      <div
                        key={m.id}
                        className={`match-card ${isUserMatch ? 'is-user-match' : ''}`}
                      >
                        <div className="match-card-meta">
                          <span>{m.round_name}</span>
                          <span className="match-format-tag">{m.format}</span>
                        </div>
                        <div className="match-card-teams">
                          <div
                            className={`match-team-row ${
                              isCompleted && m.winner_id === m.team1_id ? 'winner' : ''
                            } ${userTeamId === m.team1_id ? 'user-team' : ''}`}
                          >
                            <span>{m.team1_name}</span>
                            <span className="match-card-score">{m.team1_score}</span>
                          </div>
                          <div
                            className={`match-team-row ${
                              isCompleted && m.winner_id === m.team2_id ? 'winner' : ''
                            } ${userTeamId === m.team2_id ? 'user-team' : ''}`}
                          >
                            <span>{m.team2_name}</span>
                            <span className="match-card-score">{m.team2_score}</span>
                          </div>
                        </div>

                        <div className="match-card-actions">
                          {isCompleted ? (
                            <button
                              className="btn-view-score"
                              onClick={() => openScoreboard(m)}
                            >
                              Scoreboard 📊
                            </button>
                          ) : isSpectatorView ? (
                            <span className="text-muted">Not played yet</span>
                          ) : (
                            <button
                              className="btn-play-match"
                              onClick={() => handleSimulateMatch(m.id)}
                              disabled={isSimulating || isCompletedEvent || isPreTournament}
                            >
                              {isSimulating ? 'Playing...' : isUserMatch ? 'Play Match ⚔️' : 'Simulate'}
                            </button>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          )}

          {/* ── Subtab: Playoffs Bracket ── */}
          {activeSubTab === 'playoffs' && (
            <div className="bracket-wrapper">
              {activeTournament.champion_name && (
                <div className="champion-podium">
                  <div className="trophy-large">🏆</div>
                  <div className="champ-title">Tournament Champion</div>
                  <div className="champ-name">{activeTournament.champion_name}</div>
                  <div className="champ-rewards">
                    <span className="reward-cash">
                      💵 Winner Prize: +${(activeTournament.prize_pool * 0.5).toLocaleString()}
                    </span>
                    <span className="reward-pts">📈 +1,000 Ranking Points</span>
                  </div>
                </div>
              )}

              <div className="bracket-rounds-container">
                {/* Quarter-Finals Column */}
                <div className="bracket-column">
                  <div className="bracket-column-header">Quarter-Finals (Bo3)</div>
                  {quarterFinalMatches.length === 0 ? (
                    <p className="text-muted" style={{ textAlign: 'center', padding: '2rem' }}>
                      Complete Group Stage to unlock Quarter-Finals
                    </p>
                  ) : (
                    quarterFinalMatches.map((m) => {
                      const isUserMatch =
                        userTeamId && (m.team1_id === userTeamId || m.team2_id === userTeamId)
                      const isCompleted = m.status === 'completed'
                      const isSimulating = simulatingMatchId === m.id
                      return (
                        <div
                          key={m.id}
                          className={`match-card ${isUserMatch ? 'is-user-match' : ''}`}
                        >
                          <div className="match-card-meta">
                            <span>{m.round_name}</span>
                            <span className="match-format-tag">{m.format}</span>
                          </div>
                          <div className="match-card-teams">
                            <div
                              className={`match-team-row ${
                                isCompleted && m.winner_id === m.team1_id ? 'winner' : ''
                              } ${userTeamId === m.team1_id ? 'user-team' : ''}`}
                            >
                              <span>{m.team1_name}</span>
                              <span className="match-card-score">{m.team1_score}</span>
                            </div>
                            <div
                              className={`match-team-row ${
                                isCompleted && m.winner_id === m.team2_id ? 'winner' : ''
                              } ${userTeamId === m.team2_id ? 'user-team' : ''}`}
                            >
                              <span>{m.team2_name}</span>
                              <span className="match-card-score">{m.team2_score}</span>
                            </div>
                          </div>
                          <div className="match-card-actions">
                            {isCompleted ? (
                              <button
                                className="btn-view-score"
                                onClick={() => openScoreboard(m)}
                              >
                                Scoreboard 📊
                              </button>
                            ) : isSpectatorView ? (
                              <span className="text-muted">Not played yet</span>
                            ) : (
                              <button
                                className="btn-play-match"
                                onClick={() => handleSimulateMatch(m.id)}
                                disabled={isSimulating || isCompletedEvent || isPreTournament}
                              >
                                {isSimulating ? 'Playing...' : isUserMatch ? 'Play QF ⚔️' : 'Simulate'}
                              </button>
                            )}
                          </div>
                        </div>
                      )
                    })
                  )}
                </div>

                {/* Semi-Finals Column */}
                <div className="bracket-column">
                  <div className="bracket-column-header">Semi-Finals (Bo3)</div>
                  {semiFinalMatches.length === 0 ? (
                    <p className="text-muted" style={{ textAlign: 'center', padding: '2rem' }}>
                      Complete Group Stage to unlock Semi-Finals
                    </p>
                  ) : (
                    semiFinalMatches.map((m) => {
                      const isUserMatch =
                        userTeamId && (m.team1_id === userTeamId || m.team2_id === userTeamId)
                      const isCompleted = m.status === 'completed'
                      const isSimulating = simulatingMatchId === m.id

                      return (
                        <div
                          key={m.id}
                          className={`match-card ${isUserMatch ? 'is-user-match' : ''}`}
                        >
                          <div className="match-card-meta">
                            <span>{m.round_name}</span>
                            <span className="match-format-tag">{m.format}</span>
                          </div>
                          <div className="match-card-teams">
                            <div
                              className={`match-team-row ${
                                isCompleted && m.winner_id === m.team1_id ? 'winner' : ''
                              } ${userTeamId === m.team1_id ? 'user-team' : ''}`}
                            >
                              <span>{m.team1_name}</span>
                              <span className="match-card-score">{m.team1_score}</span>
                            </div>
                            <div
                              className={`match-team-row ${
                                isCompleted && m.winner_id === m.team2_id ? 'winner' : ''
                              } ${userTeamId === m.team2_id ? 'user-team' : ''}`}
                            >
                              <span>{m.team2_name}</span>
                              <span className="match-card-score">{m.team2_score}</span>
                            </div>
                          </div>
                          <div className="match-card-actions">
                            {isCompleted ? (
                              <button
                                className="btn-view-score"
                                onClick={() => openScoreboard(m)}
                              >
                                Scoreboard 📊
                              </button>
                            ) : isSpectatorView ? (
                              <span className="text-muted">Not played yet</span>
                            ) : (
                              <button
                                className="btn-play-match"
                                onClick={() => handleSimulateMatch(m.id)}
                                disabled={isSimulating || isCompletedEvent || isPreTournament}
                              >
                                {isSimulating ? 'Playing...' : isUserMatch ? 'Play Semi ⚔️' : 'Simulate'}
                              </button>
                            )}
                          </div>
                        </div>
                      )
                    })
                  )}
                </div>

                {/* Grand Final Column */}
                <div className="bracket-column">
                  <div className="bracket-column-header">Grand Final ({activeTournament.format})</div>
                  {grandFinalMatches.length === 0 ? (
                    <p className="text-muted" style={{ textAlign: 'center', padding: '2rem' }}>
                      Winners of Semi-Finals advance here
                    </p>
                  ) : (
                    grandFinalMatches.map((m) => {
                      const isUserMatch =
                        userTeamId && (m.team1_id === userTeamId || m.team2_id === userTeamId)
                      const isCompleted = m.status === 'completed'
                      const isSimulating = simulatingMatchId === m.id

                      return (
                        <div
                          key={m.id}
                          className={`match-card ${isUserMatch ? 'is-user-match' : ''}`}
                          style={{ border: '2px solid rgba(251, 191, 36, 0.4)' }}
                        >
                          <div className="match-card-meta">
                            <span style={{ color: '#fbbf24', fontWeight: 800 }}>🏆 {m.round_name}</span>
                            <span className="match-format-tag">{m.format}</span>
                          </div>
                          <div className="match-card-teams">
                            <div
                              className={`match-team-row ${
                                isCompleted && m.winner_id === m.team1_id ? 'winner' : ''
                              } ${userTeamId === m.team1_id ? 'user-team' : ''}`}
                            >
                              <span>{m.team1_name}</span>
                              <span className="match-card-score">{m.team1_score}</span>
                            </div>
                            <div
                              className={`match-team-row ${
                                isCompleted && m.winner_id === m.team2_id ? 'winner' : ''
                              } ${userTeamId === m.team2_id ? 'user-team' : ''}`}
                            >
                              <span>{m.team2_name}</span>
                              <span className="match-card-score">{m.team2_score}</span>
                            </div>
                          </div>
                          <div className="match-card-actions">
                            {isCompleted ? (
                              <button
                                className="btn-view-score"
                                onClick={() => openScoreboard(m)}
                              >
                                Scoreboard 📊
                              </button>
                            ) : isSpectatorView ? (
                              <span className="text-muted">Not played yet</span>
                            ) : (
                              <button
                                className="btn-play-match"
                                onClick={() => handleSimulateMatch(m.id)}
                                disabled={isSimulating || isCompletedEvent || isPreTournament}
                              >
                                {isSimulating ? 'Playing...' : isUserMatch ? 'Play Final ⚔️' : 'Simulate'}
                              </button>
                            )}
                          </div>
                        </div>
                      )
                    })
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ── Subtab: Player Stats ── */}
          {activeSubTab === 'stats' && (
            <div className="event-stats-wrapper">
              {historyLoading || statsLoading ? (
                <div className="loading-state" style={{ padding: '3rem', textAlign: 'center' }}>Loading event statistics...</div>
              ) : historyError ? (
                <div className="empty-state">{historyError}</div>
              ) : !tournamentStats ? (
                <div className="empty-state">No stats available yet. Play some matches first!</div>
              ) : (
                <>
                  {/* MVP & EVP Awards Row */}
                  {(tournamentStats.mvp || tournamentStats.evps?.length > 0) && (
                    <div className="awards-section">
                      <div className="awards-section-title">🏅 Event Awards</div>
                      <div className="awards-row">
                        {tournamentStats.mvp && (
                          <div className="award-card mvp-card">
                            <div className="award-badge-label">🏆 Tournament MVP</div>
                            <div className="award-player-name">{tournamentStats.mvp.player_name}</div>
                            <div className="award-team-name">{tournamentStats.mvp.team_name}</div>
                            <div className="award-stats-row">
                              <span>Rating: <strong className="rating-high">{tournamentStats.mvp.rating.toFixed(2)}</strong></span>
                              <span>K/D: <strong>{tournamentStats.mvp.kd_ratio.toFixed(2)}</strong></span>
                              <span>ADR: <strong>{tournamentStats.mvp.adr}</strong></span>
                              <span>Maps: <strong>{tournamentStats.mvp.maps_played}</strong></span>
                            </div>
                            <div className="award-placement">{tournamentStats.mvp.placement}</div>
                          </div>
                        )}
                        <div className="evp-cards-list">
                          {tournamentStats.evps?.map((evp) => (
                            <div key={evp.player_id} className="award-card evp-card">
                              <div className="award-badge-label">⭐ {evp.award}</div>
                              <div className="award-player-name">{evp.player_name}</div>
                              <div className="award-team-name">{evp.team_name}</div>
                              <div className="award-stats-row">
                                <span>Rating: <strong className={evp.rating >= 1.1 ? 'rating-high' : 'rating-med'}>{evp.rating.toFixed(2)}</strong></span>
                                <span>K/D: <strong>{evp.kd_ratio.toFixed(2)}</strong></span>
                                <span>ADR: <strong>{evp.adr}</strong></span>
                              </div>
                              <div className="award-placement">{evp.placement}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Full Player Stats Leaderboard */}
                  <div className="stats-leaderboard-section">
                    <div className="stats-section-header">
                      <h4>📈 Event Player Leaderboard</h4>
                      <span className="stats-note">{tournamentStats.is_completed ? '✅ Final' : '⏳ In Progress'}</span>
                    </div>
                    <div className="stats-leaderboard-controls">
                      <label>
                        <span>Team</span>
                        <select
                          aria-label="Filter leaderboard by team"
                          value={statsTeamFilter}
                          onChange={(event) => setStatsTeamFilter(event.target.value)}
                        >
                          <option value="all">All teams</option>
                          {teamFilterOptions.map(([teamId, teamName]) => (
                            <option key={teamId} value={teamId}>{teamName}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        <span>Stage</span>
                        <select
                          aria-label="Filter leaderboard by stage"
                          value={statsStageFilter}
                          onChange={(event) => setStatsStageFilter(event.target.value)}
                        >
                          <option value="all">All stages</option>
                          {stageFilterOptions.map((stage) => (
                            <option key={stage} value={stage}>{stageLabels[stage]}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        <span>Award</span>
                        <select
                          aria-label="Filter leaderboard by award"
                          value={statsAwardFilter}
                          onChange={(event) => setStatsAwardFilter(event.target.value)}
                        >
                          <option value="all">All players</option>
                          <option value="MVP">MVP</option>
                          <option value="EVP">EVP</option>
                          <option value="none">No award</option>
                        </select>
                      </label>
                      <span className="stats-filter-count">
                        Showing {filteredLeaderboardPlayers.length} of {leaderboardPlayers.length}
                      </span>
                    </div>
                    <div className="stats-table-scroll">
                      <table className="cs-scoreboard-table event-stats-table">
                        <thead>
                          <tr>
                            <th>#</th>
                            <th>Player</th>
                            <th>Team</th>
                            <th>Maps</th>
                            <th>Kills</th>
                            <th>Deaths</th>
                            <th>+/-</th>
                            <th>K/D</th>
                            <th>ADR</th>
                            <th>Rating 2.0</th>
                            <th>Placement</th>
                            <th>Award</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredLeaderboardPlayers.map((ps, idx) => {
                            const isMvp = ps.award === 'MVP'
                            const isEvp = ps.award && ps.award.startsWith('EVP')
                            const ratingClass =
                              ps.rating >= 1.25 ? 'rating-high' : ps.rating >= 0.95 ? 'rating-med' : 'rating-low'
                            return (
                              <tr
                                key={ps.player_id}
                                className={`${
                                  isMvp ? 'mvp-row' : isEvp ? 'evp-row' : ''
                                } ${!ps.reached_playoffs ? 'group-stage-row' : ''}`}
                              >
                                <td style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>#{idx + 1}</td>
                                <td>
                                  <span className="player-scoreboard-name">
                                    {ps.player_name}
                                    {ps.role && <span className="role-pill">{ps.role}</span>}
                                  </span>
                                </td>
                                <td style={{ color: 'var(--text-muted)' }}>{ps.team_name}</td>
                                <td>{ps.maps_played}</td>
                                <td className="kills-cell">{ps.kills}</td>
                                <td>{ps.deaths}</td>
                                <td style={{ color: ps.kd_diff > 0 ? '#34d399' : ps.kd_diff < 0 ? '#f87171' : 'inherit', fontWeight: 700 }}>
                                  {ps.kd_diff > 0 ? `+${ps.kd_diff}` : ps.kd_diff}
                                </td>
                                <td>{ps.kd_ratio.toFixed(2)}</td>
                                <td>{ps.adr}</td>
                                <td className={`rating-cell ${ratingClass}`}>{ps.rating.toFixed(2)}</td>
                                <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{ps.placement || '-'}</td>
                                <td>
                                  {isMvp && <span className="award-pill award-mvp">🏆 MVP</span>}
                                  {isEvp && <span className="award-pill award-evp">{ps.award}</span>}
                                </td>
                              </tr>
                            )
                          })}
                          {filteredLeaderboardPlayers.length === 0 && (
                            <tr>
                              <td className="stats-filter-empty" colSpan="12">
                                No players match these filters.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {/* ── Subtab: Seeded Teams ── */}
          {activeSubTab === 'seeds' && (
            <div className="seeded-teams-grid">
              {activeTournament.participants.map((p) => {
                const isUser = userTeamId && p.team_id === userTeamId
                return (
                  <div key={p.id} className={`seed-card ${isUser ? 'user-team' : ''}`}>
                    <div className="seed-card-info">
                      <span className="seed-card-name">
                        {p.team_name} {isUser && '(You)'}
                      </span>
                      <span className="seed-card-rank">World Rank #{p.team_rank || 'N/A'}</span>
                    </div>
                    <span className="seed-card-badge">Seed #{p.seed} (Grp {p.group_name})</span>
                  </div>
                )
              })}
            </div>
          )}

          {/* ── Subtab: World Rankings ── */}
          {activeSubTab === 'rankings' && (
            <div className="world-rankings-wrapper">
              <table className="standings-table">
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Team</th>
                    <th>Ranking Points</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {rankings.map((t) => (
                    <tr key={t.id} className={t.is_user_team ? 'user-team-row' : ''}>
                      <td>
                        <strong>#{t.ranking || '-'}</strong>
                      </td>
                      <td>
                        <span className="team-cell-name">
                          {t.name} {t.is_user_team && '(Your Team)'}
                        </span>
                      </td>
                      <td>{t.ranking_points.toLocaleString()} pts</td>
                      <td>
                        {t.ranking <= (activeTournament?.min_rank_required || 8) ? (
                          <span style={{ color: '#34d399', fontWeight: 700 }}>Eligible</span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)' }}>Uninvited</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : selectedEventId ? (
        <div className="empty-state">
          {historyLoading ? 'Loading archived event...' : historyError || 'Archived event details are unavailable.'}
        </div>
      ) : (
        <div className="empty-state">No tournament active in current month.</div>
      )}

      {/* ── CS PRO MATCH SCOREBOARD MODAL ── */}
      {selectedScoreboardMatch && (
        <div className="scoreboard-overlay" onClick={() => setSelectedScoreboardMatch(null)}>
          <div className="scoreboard-modal" onClick={(e) => e.stopPropagation()}>
            <div className="scoreboard-header">
              <h3>Match Result & Scoreboard</h3>
              <button
                className="btn-close-scoreboard"
                onClick={() => setSelectedScoreboardMatch(null)}
              >
                ✕
              </button>
            </div>

            {/* Series Summary */}
            <div className="series-summary-row">
              <div className="series-team-block">
                <span className="series-team-name">{selectedScoreboardMatch.team1_name}</span>
                <span className="seed-num">Rank #{selectedScoreboardMatch.team1_rank || 'N/A'}</span>
              </div>
              <div className="series-score-center">
                {selectedScoreboardMatch.team1_score} - {selectedScoreboardMatch.team2_score}
              </div>
              <div className="series-team-block">
                <span className="series-team-name">{selectedScoreboardMatch.team2_name}</span>
                <span className="seed-num">Rank #{selectedScoreboardMatch.team2_rank || 'N/A'}</span>
              </div>
            </div>

            {/* Map Tabs */}
            {selectedScoreboardMatch.maps?.length > 0 && (
              <>
                <div className="map-tabs-row">
                  <button
                    className={`map-tab-btn ${activeScoreboardMapIndex === -1 ? 'active' : ''}`}
                    onClick={() => setActiveScoreboardMapIndex(-1)}
                  >
                    Overall Series
                  </button>
                  {selectedScoreboardMatch.maps.map((mapData, idx) => (
                    <button
                      key={mapData.id}
                      className={`map-tab-btn ${activeScoreboardMapIndex === idx ? 'active' : ''}`}
                      onClick={() => setActiveScoreboardMapIndex(idx)}
                    >
                      Map {idx + 1}: {mapData.map_name} ({mapData.team1_score}-{mapData.team2_score})
                      {mapData.overtime && ' (OT)'}
                    </button>
                  ))}
                </div>

                {/* Active Map Detail */}
                {(() => {
                  const isOverall = activeScoreboardMapIndex === -1
                  const currentMap = isOverall ? null : selectedScoreboardMatch.maps[activeScoreboardMapIndex]
                  if (!isOverall && !currentMap) return null

                  const team1Rounds = isOverall
                    ? selectedScoreboardMatch.maps.reduce((sum, mapData) => sum + mapData.team1_score, 0)
                    : currentMap.team1_score
                  const team2Rounds = isOverall
                    ? selectedScoreboardMatch.maps.reduce((sum, mapData) => sum + mapData.team2_score, 0)
                    : currentMap.team2_score
                  const allStats = isOverall
                    ? Object.values(selectedScoreboardMatch.maps.reduce((players, mapData) => {
                        for (const stat of mapData.player_stats) {
                          const key = `${stat.team_id}:${stat.player_id}`
                          const roundsPlayed = mapData.team1_score + mapData.team2_score
                          const existing = players[key] || {
                            ...stat,
                            kills: 0,
                            deaths: 0,
                            assists: 0,
                            adr: 0,
                            rating: 0,
                            is_mvp: false,
                            roundsPlayed: 0,
                          }
                          existing.kills += stat.kills
                          existing.deaths += stat.deaths
                          existing.assists += stat.assists
                          existing.adr += stat.adr * roundsPlayed
                          existing.rating += stat.rating * roundsPlayed
                          existing.roundsPlayed += roundsPlayed
                          players[key] = existing
                        }
                        return players
                      }, {})).map((stat) => ({
                        ...stat,
                        adr: stat.roundsPlayed ? stat.adr / stat.roundsPlayed : 0,
                        rating: stat.roundsPlayed ? stat.rating / stat.roundsPlayed : 0,
                      })).sort((a, b) => b.kills - a.kills)
                    : currentMap.player_stats

                  // Split stats by team
                  const team1Stats = allStats.filter(
                    (s) => s.team_id === selectedScoreboardMatch.team1_id
                  )
                  const team2Stats = allStats.filter(
                    (s) => s.team_id === selectedScoreboardMatch.team2_id
                  )

                  const maxMapKills = Math.max(
                    ...allStats.map((s) => s.kills),
                    1
                  )
                  const totalT1Kills = team1Stats.reduce((sum, s) => sum + s.kills, 0)
                  const totalT2Kills = team2Stats.reduce((sum, s) => sum + s.kills, 0)

                  return (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                      <div className="map-detail-banner">
                        <span className="map-name-display">
                          {isOverall ? 'Overall Series' : `🗺️ ${currentMap.map_name}`}
                          {!isOverall && currentMap.overtime && <span className="ot-badge">OVERTIME</span>}
                        </span>
                        <span className="map-score-display">
                          {isOverall
                            ? `${selectedScoreboardMatch.team1_name} ${selectedScoreboardMatch.team1_score} - ${selectedScoreboardMatch.team2_score} ${selectedScoreboardMatch.team2_name}`
                            : `${selectedScoreboardMatch.team1_name} ${currentMap.team1_score} : ${currentMap.team2_score} ${selectedScoreboardMatch.team2_name}`}
                        </span>
                      </div>

                      {/* Team 1 Scoreboard */}
                      <div className="team-scoreboard-wrapper">
                        <div className="team-scoreboard-title">
                          <span>{selectedScoreboardMatch.team1_name}</span>
                          <span className="seed-num">
                            ({team1Rounds} rounds won, {totalT1Kills} frags)
                          </span>
                        </div>
                        <table className="cs-scoreboard-table">
                          <thead>
                            <tr>
                              <th>Player</th>
                              <th>Kills</th>
                              <th>Deaths</th>
                              <th>Assists</th>
                              <th>+/-</th>
                              <th>ADR</th>
                              <th>Rating 2.0</th>
                              <th>Frag Share</th>
                            </tr>
                          </thead>
                          <tbody>
                            {team1Stats.map((stat) => {
                              const isTop = !isOverall && stat.kills === maxMapKills
                              const diff = stat.kills - stat.deaths
                              const sharePct = totalT1Kills > 0 ? (stat.kills / totalT1Kills) * 100 : 20
                              const ratingClass =
                                stat.rating >= 1.25
                                  ? 'rating-high'
                                  : stat.rating >= 0.95
                                  ? 'rating-med'
                                  : 'rating-low'

                              return (
                                <tr key={stat.player_id} className={isTop ? 'top-fragger-row' : ''}>
                                  <td>
                                    <span className="player-scoreboard-name">
                                      {stat.player_name}
                                      {stat.role && <span className="role-pill">{stat.role}</span>}
                                      {!isOverall && stat.is_mvp && <span title="Map MVP">⭐</span>}
                                      {isTop && <span title="Top Fragger of the Map">🔥</span>}
                                    </span>
                                  </td>
                                  <td className={`kills-cell ${isTop ? 'top-kills' : ''}`}>
                                    {stat.kills}
                                  </td>
                                  <td>{stat.deaths}</td>
                                  <td>{stat.assists}</td>
                                  <td
                                    style={{
                                      color: diff > 0 ? '#34d399' : diff < 0 ? '#f87171' : 'inherit',
                                      fontWeight: 700,
                                    }}
                                  >
                                    {diff > 0 ? `+${diff}` : diff}
                                  </td>
                                  <td>{stat.adr}</td>
                                  <td className={`rating-cell ${ratingClass}`}>{stat.rating.toFixed(2)}</td>
                                  <td>
                                    <div
                                      className="frag-share-bar-container"
                                      title={`${sharePct.toFixed(1)}% of team kills`}
                                    >
                                      <div
                                        className="frag-share-bar-fill"
                                        style={{ width: `${Math.min(100, sharePct * 2.5)}%` }}
                                      />
                                    </div>
                                  </td>
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>
                      </div>

                      {/* Team 2 Scoreboard */}
                      <div className="team-scoreboard-wrapper">
                        <div className="team-scoreboard-title">
                          <span>{selectedScoreboardMatch.team2_name}</span>
                          <span className="seed-num">
                            ({team2Rounds} rounds won, {totalT2Kills} frags)
                          </span>
                        </div>
                        <table className="cs-scoreboard-table">
                          <thead>
                            <tr>
                              <th>Player</th>
                              <th>Kills</th>
                              <th>Deaths</th>
                              <th>Assists</th>
                              <th>+/-</th>
                              <th>ADR</th>
                              <th>Rating 2.0</th>
                              <th>Frag Share</th>
                            </tr>
                          </thead>
                          <tbody>
                            {team2Stats.map((stat) => {
                              const isTop = !isOverall && stat.kills === maxMapKills
                              const diff = stat.kills - stat.deaths
                              const sharePct = totalT2Kills > 0 ? (stat.kills / totalT2Kills) * 100 : 20
                              const ratingClass =
                                stat.rating >= 1.25
                                  ? 'rating-high'
                                  : stat.rating >= 0.95
                                  ? 'rating-med'
                                  : 'rating-low'

                              return (
                                <tr key={stat.player_id} className={isTop ? 'top-fragger-row' : ''}>
                                  <td>
                                    <span className="player-scoreboard-name">
                                      {stat.player_name}
                                      {stat.role && <span className="role-pill">{stat.role}</span>}
                                      {!isOverall && stat.is_mvp && <span title="Map MVP">⭐</span>}
                                      {isTop && <span title="Top Fragger of the Map">🔥</span>}
                                    </span>
                                  </td>
                                  <td className={`kills-cell ${isTop ? 'top-kills' : ''}`}>
                                    {stat.kills}
                                  </td>
                                  <td>{stat.deaths}</td>
                                  <td>{stat.assists}</td>
                                  <td
                                    style={{
                                      color: diff > 0 ? '#34d399' : diff < 0 ? '#f87171' : 'inherit',
                                      fontWeight: 700,
                                    }}
                                  >
                                    {diff > 0 ? `+${diff}` : diff}
                                  </td>
                                  <td>{stat.adr}</td>
                                  <td className={`rating-cell ${ratingClass}`}>{stat.rating.toFixed(2)}</td>
                                  <td>
                                    <div
                                      className="frag-share-bar-container"
                                      title={`${sharePct.toFixed(1)}% of team kills`}
                                    >
                                      <div
                                        className="frag-share-bar-fill"
                                        style={{ width: `${Math.min(100, sharePct * 2.5)}%` }}
                                      />
                                    </div>
                                  </td>
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )
                })()}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default TournamentCalendar
