import React from 'react';
import { NavLink } from 'react-router-dom';
import { ShieldCheck, Upload, LayoutDashboard, FileText, Activity, LogOut } from 'lucide-react';
import { isReviewer, useAuth } from '../auth/AuthContext';
import './Navbar.css';

export default function Navbar() {
  const { user, logout } = useAuth();
  const reviewer = isReviewer(user);
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
          <div className="navbar-user"><strong>{user?.display_name}</strong><small>{user?.roles?.filter(role => role !== 'employee').join(' · ') || 'employee'}</small></div>
          <button className="nav-link navbar-signout" onClick={logout} title="Sign out"><LogOut size={17} /><span>Sign out</span></button>
        </div>
      </div>
    </nav>
  );
}
