import React, { useState, useEffect } from 'react';

function TeamNeeds({ team, onRowClick, refreshTrigger }) {
  const [needs, setNeeds] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!team) return;
    
    let isMounted = true;
    
    async function fetchNeeds() {
      setLoading(true);
      setError(null);
      try {
        const [needsRes, candsRes] = await Promise.all([
          fetch(`/teams/${team.id}/needs`),
          fetch(`/teams/${team.id}/needs/candidates`)
        ]);
        
        if (!needsRes.ok) throw new Error('Failed to fetch team needs');
        if (!candsRes.ok) throw new Error('Failed to fetch candidates');
        
        const needsData = await needsRes.json();
        const candsData = await candsRes.json();
        
        if (isMounted) {
          setNeeds(needsData);
          setCandidates(candsData);
        }
      } catch (err) {
        if (isMounted) setError(err.message);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    
    fetchNeeds();
    return () => { isMounted = false };
  }, [team, refreshTrigger]);

  if (!team) return null;

  if (loading) return <div className="team-card"><p>Loading team needs...</p></div>;
  if (error) return <div className="team-card"><p className="form-error">{error}</p></div>;
  if (!needs) return null;

  const { roster_status, missing_roles, assigned_igl, roles_count } = needs;

  const formatPrice = (price) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(price || 0);

  const getDisplayRating = (player) => {
    const value = player?.Rating ?? player?.rating ?? player?.overall_rating ?? 0;
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric.toFixed() : '0.00';
  };

  return (
    <div className="team-card team-needs-card" style={{ marginTop: '20px' }}>
      <div className="team-header">
        <div className="team-info">
          <h3>Team Needs</h3>
          <span className={`team-rank ${roster_status === 'complete' ? 'complete' : 'incomplete'}`}>
            Status: {roster_status.toUpperCase()}
          </span>
        </div>
      </div>
      
      <div className="team-roster" style={{ padding: '15px' }}>
        <div className="needs-stats" style={{ marginBottom: '20px' }}>
          <p style={{ margin: '0 0 10px 0' }}><strong>Current IGL:</strong> {assigned_igl || <span style={{ color: '#ff6b6b' }}>None Selected</span>}</p>
          <div className="roles-breakdown" style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            {Object.entries(roles_count).map(([role, count]) => {
              const roleClass = role === 'igl' ? 'default' : role;
              return (
                <span key={role} className="role-count" style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                  <span className={`role-badge ${roleClass}`}>{role}</span> x{count}
                </span>
              );
            })}
          </div>
        </div>
        
        <h4 style={{ borderBottom: '1px solid #333', paddingBottom: '10px', marginBottom: '15px' }}>Missing Roles</h4>
        {missing_roles.length === 0 ? (
          <p className="empty-roster" style={{ color: '#51cf66' }}>All compulsory roles are filled!</p>
        ) : (
          <div className="missing-roles-list">
            {missing_roles.map(role => {
              const roleCandidates = candidates.filter(c => (c.role || 'unknown').toLowerCase().includes(role));
              
              return (
                <div key={role} className="missing-role-section" style={{ marginBottom: '25px' }}>
                  <h5 style={{ margin: '0 0 10px 0' }}>Candidates for: <span className={`role-badge ${role === 'igl' ? 'default' : role}`}>{role}</span></h5>
                  {roleCandidates.length > 0 ? (
                    <table className="roster-table">
                      <thead>
                        <tr>
                          <th>Candidate</th>
                          <th>Role</th>
                          <th>Overall</th>
                          <th>Price</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {roleCandidates.slice(0, 5).map(player => (
                          <tr key={player.id} className="clickable-row" onClick={() => onRowClick(player)}>
                            <td>{player.player}</td>
                            <td>{player.role || 'Unassigned'}</td>
                            <td>{getDisplayRating(player)}</td>
                            <td>{formatPrice(player.price)}</td>
                            <td>
                              <button className="btn-secondary btn-sm" type="button" onClick={(e) => {
                                e.stopPropagation();
                                onRowClick(player);
                              }}>
                                Negotiate
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <p className="empty-roster" style={{ fontSize: '0.9em' }}>No specific candidates found for {role}. Try searching free agents.</p>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default TeamNeeds;
