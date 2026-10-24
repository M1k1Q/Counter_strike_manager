function Navbar({ activeTab, onTabChange, user, onLogout, hasCareer }) {
  return (
    <nav className="navbar" aria-label="Main navigation">
      <div className="nav-container">
        <div className="nav-brand logo">
          <div className="logo-icon" aria-hidden="true"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 3 5 14h6l-1 7 9-11h-6l1-7Z" /></svg></div>
          <span className="logo-text">CS Manager</span>
        </div>

        <ul className="nav-links">
          <li>
            <a href="#" aria-current={activeTab === 'home' ? 'page' : undefined} className={`nav-link ${activeTab === 'home' ? 'active' : ''}`} onClick={(e) => { e.preventDefault(); onTabChange('home') }}>Home</a>
          </li>
          <li>
            <a href="#" aria-current={activeTab === 'manage' ? 'page' : undefined} className={`nav-link ${activeTab === 'manage' ? 'active' : ''}`} onClick={(e) => { e.preventDefault(); onTabChange('manage') }}>Manage</a>
          </li>
          <li>
            <a href="#" aria-current={activeTab === 'tournaments' ? 'page' : undefined} className={`nav-link ${activeTab === 'tournaments' ? 'active' : ''}`} onClick={(e) => { e.preventDefault(); onTabChange('tournaments') }}>Tournaments</a>
          </li>
          {hasCareer && (
            <li>
              <a href="#" aria-current={activeTab === 'top20' ? 'page' : undefined} className={`nav-link ${activeTab === 'top20' ? 'active' : ''}`} onClick={(e) => { e.preventDefault(); onTabChange('top20') }}>Yearly Top 20</a>
            </li>
          )}
          <li>
            <a href="#" aria-current={activeTab === 'teams' ? 'page' : undefined} className={`nav-link ${activeTab === 'teams' ? 'active' : ''}`} onClick={(e) => { e.preventDefault(); onTabChange('teams') }}>Teams</a>
          </li>
          <li>
            <a href="#" aria-current={activeTab === 'players' ? 'page' : undefined} className={`nav-link ${activeTab === 'players' ? 'active' : ''}`} onClick={(e) => { e.preventDefault(); onTabChange('players') }}>Players</a>
          </li>
        </ul>

        <div className="nav-actions">
          {user && (
            <div className="user-profile-badge">
              <span className="user-avatar">{user.username?.slice(0, 1).toUpperCase()}</span>
              <span className="user-name">{user.username}</span>
              <button className="btn-logout" onClick={onLogout} title="Log Out">
                Log out
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  )
}


export default Navbar
