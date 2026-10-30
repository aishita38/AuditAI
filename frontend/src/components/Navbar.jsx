import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { ShieldCheck, Upload, LayoutDashboard, FileText, Activity, LogOut, Settings, Building2 } from 'lucide-react';
import { isReviewer, useAuth } from '../auth/AuthContext';
import { useAuditProfile } from '../context/AuditProfileContext';
import WorkspaceSettingsModal from './WorkspaceSettingsModal';
import './Navbar.css';

export default function Navbar() {
  const { user, logout } = useAuth();
  const { companyName, profile } = useAuditProfile();
  const reviewer = isReviewer(user);
  const isAdmin = user?.roles?.includes('admin');
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <nav className="navbar glass-card">
      <div className="navbar-content">
        <div className="navbar-brand">
          <img className="brand-logo" src="/auditai-logo.png" alt="AuditAI mascot" />
          <span className="brand-text">AuditAI</span>
        </div>

        <div className="navbar-links">
          {reviewer && <NavLink to="/" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
            <LayoutDashboard size={18} />
            <span>Dashboard</span>
          </NavLink>}

          <NavLink to="/upload" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
            <Upload size={18} />
            <span>Upload</span>
          </NavLink>

          <NavLink to="/claims" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
            <FileText size={18} />
            <span>Claims</span>
          </NavLink>

          {reviewer && <NavLink to="/audit-screens" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
            <Activity size={18} />
            <span>Audit Screens</span>
          </NavLink>}
          {reviewer && <NavLink to="/review-queue" aria-label="Review Queue" title="Review Queue" className={({isActive})=>isActive?'nav-link active':'nav-link'}><ShieldCheck size={18}/><span>Review Queue</span></NavLink>}

          {/* Company & Workspace Identity Badge */}
          <div className="navbar-workspace-badge" title={`${companyName} · ${profile.name}`}>
            <Building2 size={13} style={{ color: profile.color, flexShrink: 0 }} />
            <span className="navbar-workspace-name">{companyName}</span>
            <span
              className="navbar-workspace-edition"
              style={{ background: `${profile.color}20`, color: profile.color }}
            >
              {profile.shortName}
            </span>
          </div>

          <div className="navbar-user">
            <strong>{user?.display_name}</strong>
            <small>{user?.roles?.filter(role => role !== 'employee').join(' · ') || 'employee'}</small>
          </div>

          {isAdmin && (
            <button
              type="button"
              className="nav-link navbar-settings-btn"
              onClick={() => setSettingsOpen(true)}
              title="Workspace & Organization Settings (Admin)"
              aria-label="Workspace Settings"
            >
              <Settings size={16} />
            </button>
          )}

          <button className="nav-link navbar-signout" onClick={logout} title="Sign out">
            <LogOut size={17} />
            <span>Sign out</span>
          </button>
        </div>
      </div>

      <WorkspaceSettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </nav>
  );
}
