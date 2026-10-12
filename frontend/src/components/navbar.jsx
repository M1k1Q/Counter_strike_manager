function Navbar({ activeTab, onTabChange, user, onLogout }) {
  return (
    <nav className="navbar">
      <div className="nav-container">
        <div className="logo">
          <div className="logo-icon">⚡</div>
          <span className="logo-text">CS Manager</span>
        </div>
        <ul className="nav-links">
          <li>
            <a href="#" className={`nav-link ${activeTab === 'home' ? 'active' : ''}`} onClick={(e) => { e.preventDefault(); onTabChange('home') }}>Home</a>
          </li>
          <li>
            <a href="#" className={`nav-link ${activeTab === 'manage' ? 'active' : ''}`} onClick={(e) => { e.preventDefault(); onTabChange('manage') }}>Manage</a>
          </li>
          <li>
            <a href="#" className={`nav-link ${activeTab === 'tournaments' ? 'active' : ''}`} onClick={(e) => { e.preventDefault(); onTabChange('tournaments') }}>Tournaments 🏆</a>
          </li>
          <li>
            <a href="#" className={`nav-link ${activeTab === 'teams' ? 'active' : ''}`} onClick={(e) => { e.preventDefault(); onTabChange('teams') }}>Teams</a>
          </li>
          <li>
            <a href="#" className={`nav-link ${activeTab === 'players' ? 'active' : ''}`} onClick={(e) => { e.preventDefault(); onTabChange('players') }}>Players</a>
          </li>
        </ul>

        {user && (
          <div className="user-profile-badge">
            <span className="user-avatar">👤</span>
            <span className="user-name">{user.username}</span>
            <button className="btn-logout" onClick={onLogout} title="Log Out">
              Logout 🚪
            </button>
          </div>
        )}
      </div>
    </nav>
  )
}


export default Navbar
