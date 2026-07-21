import { useState, useEffect } from 'react'
import PlayerTable from './components/PlayerTable'
import PlayerModal from './components/PlayerModal'
import Navbar from './components/navbar'
import CareerStart from './components/CareerStart'
import TeamRoster from './components/TeamRoster'
import './App.css'

function App() {
  const [players, setPlayers] = useState([])
  const [teams, setTeams] = useState([])
  const [manager, setManager] = useState(null)
  const [selectedTeam, setSelectedTeam] = useState(null)
  const [activeTab, setActiveTab] = useState('home')
  const [search, setSearch] = useState('')
  const [playerSort, setPlayerSort] = useState('overall')
  const [playerFilter, setPlayerFilter] = useState('all')
  const [newTeamName, setNewTeamName] = useState('')
  const [creatingTeam, setCreatingTeam] = useState(false)
  const [teamError, setTeamError] = useState(null)
  const [modalStatus, setModalStatus] = useState(null)
  const [modalSubmitting, setModalSubmitting] = useState(false)
  const [activeNegotiation, setActiveNegotiation] = useState(null)
  const [isGameLoaded, setIsGameLoaded] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activePlayer, setActivePlayer] = useState(null)

  useEffect(() => {
    async function initGame() {
      try {
        // 1. Check Manager/Game Status
        const statusRes = await fetch('/game/status')
        if (statusRes.ok) {
          const status = await statusRes.json()
          setManager(status.manager)
          setSelectedTeam(status.team)
        }

        // 2. Fetch Players and Teams
        const [playersRes, teamsRes] = await Promise.all([
          fetch('/players'),
          fetch('/teams')
        ])
        
        if (!playersRes.ok) throw new Error(`HTTP ${playersRes.status}`)
        const playersData = await playersRes.json()
        setPlayers(playersData)

        if (teamsRes.ok) {
          const teamsData = await teamsRes.json()
          setTeams(teamsData)
        }
      } catch (err) {
        console.error('Failed to initialize app:', err)
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
    initGame()
  }, [])

  const handleCareerStart = (newManager) => {
    setManager(newManager)
  }

  const refreshAppData = async () => {
    try {
      const [playersRes, teamsRes] = await Promise.all([
        fetch('/players'),
        fetch('/teams')
      ])

      if (playersRes.ok) {
        const playersData = await playersRes.json()
        setPlayers(playersData)
      }

      if (teamsRes.ok) {
        const teamsData = await teamsRes.json()
        setTeams(teamsData)
        setSelectedTeam((prev) => {
          const match = prev?.id ? teamsData.find((team) => team.id === prev.id) : null
          return match || prev
        })
      }
    } catch (err) {
      console.error('Unable to refresh app data:', err)
    }
  }

  const refreshGameStatus = async () => {
    try {
      const statusRes = await fetch('/game/status')
      if (statusRes.ok) {
        const status = await statusRes.json()
        setManager(status.manager)
        setSelectedTeam(status.team)
      }
    } catch (err) {
      console.error('Unable to refresh game status:', err)
    }
  }

  const refreshAllData = async () => {
    await Promise.all([refreshGameStatus(), refreshAppData()])
  }

  const handleSelectTeam = async (teamId) => {
    try {
      const res = await fetch(`/game/select-team/${teamId}`, { method: 'POST' })
      if (!res.ok) throw new Error('Unable to select team')
      await refreshAllData()
    } catch (err) {
      console.error(err)
      setError('Failed to select team. Please try again.')
    }
  }

  const handleCreateTeam = async (event) => {
    event.preventDefault()
    if (!newTeamName.trim()) return

    setCreatingTeam(true)
    setTeamError(null)

    try {
      const res = await fetch('/game/create-team', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newTeamName.trim() })
      })

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Unable to create team')
      }

      await refreshAllData()
      setNewTeamName('')
      setActiveTab('teams')
    } catch (err) {
      console.error(err)
      setTeamError(err.message || 'Failed to create team')
    } finally {
      setCreatingTeam(false)
    }
  }

  const getDisplayRating = (player) => {
    const value = player?.Rating ?? player?.rating ?? player?.overall_rating ?? 0
    const numeric = Number(value)
    return Number.isFinite(numeric) ? numeric.toFixed() : '0.00'
  }

  const handleTransferPlayer = async (playerId) => {
    if (!selectedTeam?.id) {
      throw new Error('Select a team before transferring players.')
    }

    const res = await fetch(`/teams/${selectedTeam.id}/add_player/${playerId}`, { method: 'POST' })
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}))
      throw new Error(errorData.detail || 'Unable to move player')
    }

    await refreshAllData()
    return `${players.find((p) => p.id === playerId)?.player || 'Player'} signed.`
  }

  const handleNegotiatePlayer = async (player, existingNegotiation = null, customOfferAmount = null) => {
    if (!selectedTeam?.id) {
      throw new Error('Select a team before negotiating players.')
    }

    const baseOffer = Math.max(player.price || 50000, 50000)
    const offerAmount = customOfferAmount
      ?? (existingNegotiation
        ? Math.max(existingNegotiation.offer_amount + Math.round(baseOffer * 0.1), baseOffer)
        : baseOffer)

    const url = existingNegotiation
      ? `/negotiations/${existingNegotiation.id}/offer`
      : '/negotiations'
    const body = existingNegotiation
      ? JSON.stringify({ offer_amount: offerAmount, message: 'Follow-up negotiation offer' })
      : JSON.stringify({
          player_id: player.id,
          target_team_id: selectedTeam.id,
          offer_amount: offerAmount,
          message: 'Initial negotiation offer',
        })

    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
    })

    const data = await res.json()
    if (!res.ok) {
      throw new Error(data.detail || 'Unable to negotiate')
    }

    await refreshAllData()
    setActiveNegotiation(data)
    return data
  }

  const handleReleasePlayer = async (playerId) => {
    if (!selectedTeam?.id) {
      throw new Error('Select a team before removing players.')
    }

    const res = await fetch(`/teams/${selectedTeam.id}/remove_player/${playerId}`, { method: 'POST' })
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}))
      throw new Error(errorData.detail || 'Unable to remove player')
    }

    await refreshAllData()
    return `${players.find((p) => p.id === playerId)?.player || 'Player'} released.`
  }

  const handleModalAction = async (player, customOfferAmount = null) => {
    setModalStatus('Working...')
    setModalSubmitting(true)
    setTeamError(null)

    try {
      if (player.team_id === null) {
        const message = await handleTransferPlayer(player.id)
        setModalStatus(message)
        setActiveNegotiation(null)
        return
      }

      if (selectedTeam?.id === player.team_id) {
        const message = await handleReleasePlayer(player.id)
        setModalStatus(message)
        setActiveNegotiation(null)
        return
      }

      const data = await handleNegotiatePlayer(player, activeNegotiation, customOfferAmount)
      if (data.status_explanation) {
        setModalStatus(data.status_explanation)
      } else if (data.status === 'accepted') {
        setModalStatus(`${player.player} has joined ${selectedTeam.name}!`)
      } else if (data.status === 'rejected') {
        setModalStatus(`${player.player} rejected the offer.`)
      } else if (data.status === 'pending') {
        setModalStatus(`Negotiation pending: ${Math.round(data.success_chance)}% chance to succeed. Offer: $${data.offer_amount.toLocaleString()}`)
      } else {
        setModalStatus(`Negotiation status: ${data.status}`)
      }
    } catch (err) {
      console.error(err)
      setModalStatus(err.message || 'Action failed. Please try again.')
    } finally {
      setModalSubmitting(false)
    }
  }

  const closeModal = () => {
    setActivePlayer(null)
    setActiveNegotiation(null)
    setModalStatus(null)
  }

  // Filter players by search
  const filteredPlayers = players.filter(p =>
    (p.player && p.player.toLowerCase().includes(search.toLowerCase())) ||
    (p.role && p.role.toLowerCase().includes(search.toLowerCase()))
  )

  const sortedPlayers = filteredPlayers
    .filter(p => {
      if (playerFilter === 'free-agents') return p.team_id === null
      if (playerFilter === 'with-team') return p.team_id !== null
      return true
    })
    .slice()
    .sort((a, b) => {
      if (playerSort === 'price') return (b.price || 0) - (a.price || 0)
      if (playerSort === 'role') return (a.role || '').localeCompare(b.role || '')
      const aScore = a.Rating ?? a.rating ?? a.overall_rating ?? 0
      const bScore = b.Rating ?? b.rating ?? b.overall_rating ?? 0
      return bScore - aScore
    })

  const freeAgents = players.filter(p => p.team_id === null)
  const marketPlayers = selectedTeam ? players.filter(p => p.team_id !== null && p.team_id !== selectedTeam.id) : []
  const selectedTeamPlayers = selectedTeam?.players || []
  const getTeamName = (teamId) => teams.find((team) => team.id === teamId)?.name || 'Unknown'

  // Group market players by team
  const marketPlayersByTeam = marketPlayers.reduce((acc, player) => {
    const teamName = getTeamName(player.team_id)
    const teamRanking = teams.find(t => t.id === player.team_id)?.ranking ?? 99
    if (!acc[teamName]) acc[teamName] = { players: [], ranking: teamRanking, team_id: player.team_id }
    acc[teamName].players.push(player)
    return acc
  }, {})
  const marketTeamsSorted = Object.entries(marketPlayersByTeam).sort((a, b) => a[1].ranking - b[1].ranking)

  const formatPrice = (price) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(price || 0)
  const handlePlayerRowClick = (player) => {
    setActivePlayer(player)
    setActiveNegotiation(null)
    setModalStatus(null)
  }

  if (!isGameLoaded && loading) {
    return (
      <div className="loader-container">
        <div className="spinner"></div>
        <p>Loading Game Data...</p>
      </div>
    )
  }

  return (
    <> 
      <Navbar activeTab={activeTab} onTabChange={setActiveTab} />
      <div className="app">
        {!manager ? (
          <CareerStart onStart={handleCareerStart} />
        ) : (
          <>
            {activeTab === 'players' && (
              <div className="toolbar">
                <div className="search-box">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"/>
                  </svg>
                  <input
                    type="text"
                    placeholder="Search players by name or role…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
                <div className="filter-row">
                  <div className="filter-group">
                    <label>Filter</label>
                    <select value={playerFilter} onChange={(e) => setPlayerFilter(e.target.value)}>
                      <option value="all">All players</option>
                      <option value="free-agents">Free agents</option>
                      <option value="with-team">Assigned players</option>
                    </select>
                  </div>
                  <div className="filter-group">
                    <label>Sort</label>
                    <select value={playerSort} onChange={(e) => setPlayerSort(e.target.value)}>
                      <option value="overall">Overall rating</option>
                      <option value="price">Price</option>
                      <option value="role">Role</option>
                    </select>
                  </div>
                  <div className="player-count">
                    Showing <span className="count">{sortedPlayers.length}</span> players
                  </div>
                </div>
              </div>
            )}

            <div className="tab-panel">
              {activeTab === 'home' && (
                <div className="home-grid">
                  <div className="home-card">
                    <h2>Welcome, {manager.name}</h2>
                    <p>Build your team, choose a club, and manage your career.</p>
                    <div className="home-stats">
                      <div>
                        <span>Budget</span>
                        <strong>${manager.budget.toLocaleString()}</strong>
                      </div>
                      <div>
                        <span>Career Points</span>
                        <strong>{manager.career_points}</strong>
                      </div>
                      <div>
                        <span>Selected Team</span>
                        <strong>{selectedTeam?.name ?? 'None'}</strong>
                      </div>
                    </div>
                  </div>

                  <div className="home-card">
                    <h3>Choose your team</h3>
                    <p>Select a squad to manage from the available clubs below.</p>
                    <div className="team-selection-grid">
                      {teams.map((team) => (
                        <div key={team.id} className={`team-card-small ${selectedTeam?.id === team.id ? 'selected' : ''}`}>
                          <div>
                            <strong>{team.name}</strong>
                            <span>Rank #{team.ranking || 'N/A'}</span>
                          </div>
                          <div className="team-card-actions">
                            {selectedTeam?.id === team.id ? (
                              <span className="selected-badge">Selected</span>
                            ) : (
                              <button className="btn-primary" type="button" onClick={() => handleSelectTeam(team.id)}>Select</button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>

                    <form className="create-team-form" onSubmit={handleCreateTeam}>
                      <h4>Create a new team</h4>
                      <div className="form-row">
                        <input
                          type="text"
                          placeholder="New team name"
                          value={newTeamName}
                          onChange={(e) => setNewTeamName(e.target.value)}
                        />
                        <button className="btn-primary" type="submit" disabled={creatingTeam || !newTeamName.trim()}>
                          {creatingTeam ? 'Creating…' : 'Create Team'}
                        </button>
                      </div>
                      {teamError && <p className="form-error">{teamError}</p>}
                    </form>
                  </div>
                </div>
              )}

              {activeTab === 'players' && (
                <PlayerTable
                  players={sortedPlayers}
                  loading={loading}
                  error={error}
                  onRowClick={handlePlayerRowClick}
                />
              )}

              {activeTab === 'manage' && (
                <div className="dashboard-grid">
                  <div className="teams-section">
                    <h2 className="section-title">Manage Your Team</h2>
                    <div className="teams-list">
                      {!selectedTeam && (
                        <div className="team-card">
                          <div className="team-header">
                            <div className="team-info">
                              <h3>No team selected</h3>
                            </div>
                          </div>
                          <div className="team-roster">
                            <p className="empty-roster">Choose a team on the Home tab before managing players.</p>
                          </div>
                        </div>
                      )}
                      {selectedTeam && (
                        <div className="team-card">
                          <div className="team-header">
                            <div className="team-info">
                              <h3>{selectedTeam.name}</h3>
                              <span className="team-rank">Rank #{selectedTeam.ranking || 'N/A'}</span>
                            </div>
                            <div className="team-value">
                              <span className="label">Budget</span>
                              <span className="value">${manager.budget.toLocaleString()}</span>
                            </div>
                          </div>
                          <div className="team-roster">
                            <h4>Current roster</h4>
                            {selectedTeamPlayers.length === 0 ? (
                              <p className="empty-roster">No players in this team yet.</p>
                            ) : (
                              <table className="roster-table">
                                <thead>
                                  <tr>
                                    <th>Player</th>
                                    <th>Role</th>
                                    <th>Overall</th>
                                    <th>Action</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {selectedTeamPlayers.map((player) => (
                                    <tr key={player.id} onClick={() => setActivePlayer(player)} className="clickable-row">
                                      <td>{player.player}</td>
                                      <td>{player.role || 'Unassigned'}</td>
                                      <td>{getDisplayRating(player)}</td>
                                      <td>
                                        <button className="btn-secondary" type="button" onClick={(e) => { e.stopPropagation(); handleReleasePlayer(player.id); }}>
                                          Release
                                        </button>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {selectedTeam && (
                    <div className="teams-section">
                      <h2 className="section-title">Roster market</h2>
                      <div className="manage-market-list">
                        <div className="team-card">
                          <div className="team-header">
                            <div className="team-info">
                              <h3>Free agents</h3>
                              <span className="team-rank">No transfer fee</span>
                            </div>
                          </div>
                          <div className="team-roster">
                            {freeAgents.length === 0 ? (
                              <p className="empty-roster">No free agents available.</p>
                            ) : (
                              <table className="roster-table">
                                <thead>
                                  <tr>
                                    <th>Player</th>
                                    <th>Role</th>
                                    <th>Overall</th>
                                    <th>IGL</th>
                                    <th>Action</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {freeAgents.map((player) => (
                                    <tr key={player.id} onClick={() => setActivePlayer(player)} className="clickable-row">
                                      <td>{player.player}</td>
                                      <td>{player.role || 'Unassigned'}</td>
                                      <td>{getDisplayRating(player)}</td>
                                      <td>{player.igl_score != null ? `${player.igl_score.toFixed(0)}%` : '—'}</td>
                                      <td>
                                        <button className="btn-primary" type="button" onClick={(e) => { e.stopPropagation(); handleTransferPlayer(player.id); }}>
                                          Sign
                                        </button>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="manage-market-list">
                          {marketPlayers.length === 0 ? (
                            <div className="team-card">
                              <div className="team-header">
                                <div className="team-info"><h3>Players on other teams</h3></div>
                              </div>
                              <div className="team-roster">
                                <p className="empty-roster">No players available from other teams.</p>
                              </div>
                            </div>
                          ) : (
                            <>
                              <h3 className="market-section-title">
                                Players on other teams
                                <span className="market-count">{marketPlayers.length} players</span>
                              </h3>
                              {marketTeamsSorted.map(([teamName, { players: teamPlayers, ranking }]) => (
                                <div className="team-card market-team-card" key={teamName}>
                                  <div className="team-header">
                                    <div className="team-info">
                                      <h3>{teamName}</h3>
                                      <span className="team-rank">Rank #{ranking}</span>
                                    </div>
                                    <div className="team-value">
                                      <span className="label">Players</span>
                                      <span className="value">{teamPlayers.length}</span>
                                    </div>
                                  </div>
                                  <div className="team-roster">
                                    <table className="roster-table">
                                      <thead>
                                        <tr>
                                          <th>Player</th>
                                          <th>Role</th>
                                          <th>Overall</th>
                                          <th>IGL</th>
                                          <th>Market Value</th>
                                          <th>Action</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {teamPlayers
                                          .slice()
                                          .sort((a, b) => (b.Rating ?? 0) - (a.Rating ?? 0))
                                          .map((player) => {
                                            const sourceRank = ranking
                                            const isTopTeamStar = sourceRank <= 5 && (player.Rating ?? 0) >= 82
                                            return (
                                              <tr key={player.id} onClick={() => setActivePlayer(player)} className="clickable-row">
                                                <td>
                                                  <span className="player-name-cell">{player.player}</span>
                                                  {isTopTeamStar && (
                                                    <span className="untouchable-tag" title="Franchise star – very hard to sign">★</span>
                                                  )}
                                                </td>
                                                <td>{player.role || 'Unassigned'}</td>
                                                <td>{getDisplayRating(player)}</td>
                                                <td>{player.igl_score != null ? `${player.igl_score.toFixed(0)}%` : '—'}</td>
                                                <td className="market-value-cell">
                                                  <span className={`market-value ${isTopTeamStar ? 'market-value--star' : ''}`}>
                                                    {formatPrice(player.price)}
                                                  </span>
                                                </td>
                                                <td>
                                                  <button className="btn-secondary btn-sm" type="button" onClick={(e) => {
                                                    e.stopPropagation()
                                                    setActivePlayer(player)
                                                    setActiveNegotiation(null)
                                                    setModalStatus(null)
                                                  }}>
                                                    Negotiate
                                                  </button>
                                                </td>
                                              </tr>
                                            )
                                          })}
                                      </tbody>
                                    </table>
                                  </div>
                                </div>
                              ))}
                            </>
                          )}
                        </div>

                    </div>
                  )}

                  {teamError && <p className="form-error">{teamError}</p>}
                </div>
              )}

              {activeTab === 'teams' && (
                <div className="dashboard-grid">
                  <div className="teams-section">
                    <h2 className="section-title">Teams</h2>
                    <div className="teams-list">
                      {teams.length === 0 && !loading && <p className="text-muted">No teams available.</p>}
                      {teams.map(team => (
                        <TeamRoster key={team.id} team={team} searchQuery={search} />
                      ))}
                    </div>
                  </div>

                  <div className="free-agents-section">
                    <h2 className="section-title">Free Agents</h2>
                    <PlayerTable
                      players={freeAgents}
                      loading={loading}
                      error={error}
                      onRowClick={handlePlayerRowClick}
                    />
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
      <PlayerModal
        player={activePlayer}
        selectedTeam={selectedTeam}
        onClose={closeModal}
        onAction={handleModalAction}
        statusMessage={modalStatus}
        isSubmitting={modalSubmitting}
        negotiation={activeNegotiation}
        getTeamName={getTeamName}
      />
    </>
  )
}

export default App

