import React, { useState, useRef, useEffect } from 'react';
import { Building2, Search, Landmark, ChevronDown, Check, Info, ShieldAlert } from 'lucide-react';
import { useAuditProfile, AUDIT_PROFILES } from '../context/AuditProfileContext';
import './AuditProfileSelector.css';

const ICONS = {
  Building2,
  Search,
  Landmark,
};

export default function AuditProfileSelector({ variant = 'navbar', showNotice = false, onSelect }) {
  const { profileId, setProfile, profile, profiles } = useAuditProfile();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (id) => {
    setProfile(id);
    setDropdownOpen(false);
    if (onSelect) onSelect(id);
  };

  const CurrentIcon = ICONS[profile.icon] || Building2;

  if (variant === 'navbar') {
    return (
      <div className="profile-selector-nav" ref={dropdownRef}>
        <button
          type="button"
          className="profile-selector-nav-btn"
          onClick={() => setDropdownOpen(!dropdownOpen)}
          title={`Active Profile: ${profile.name}. Click to switch mode.`}
          aria-haspopup="listbox"
          aria-expanded={dropdownOpen}
        >
          <CurrentIcon size={15} style={{ color: profile.color }} />
          <span className="profile-selector-nav-label">{profile.shortName}</span>
          <ChevronDown size={13} className={`profile-chevron ${dropdownOpen ? 'rotate' : ''}`} />
        </button>

        {dropdownOpen && (
          <div className="profile-dropdown-menu" role="listbox">
            <div className="profile-dropdown-header">
              <span className="text-xs text-muted uppercase font-semibold">Audit Operational Mode</span>
            </div>
            {Object.values(profiles).map((p) => {
              const IconComp = ICONS[p.icon] || Building2;
              const isSelected = p.id === profileId;
              return (
                <button
                  key={p.id}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  className={`profile-dropdown-item ${isSelected ? 'active' : ''}`}
                  onClick={() => handleSelect(p.id)}
                >
                  <div className="profile-item-icon" style={{ color: p.color }}>
                    <IconComp size={16} />
                  </div>
                  <div className="profile-item-text">
                    <div className="profile-item-title flex items-center justify-between">
                      <strong>{p.name}</strong>
                      {isSelected && <Check size={14} className="text-accent-primary ml-2" />}
                    </div>
                    <small className="profile-item-desc">{p.badge}</small>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  if (variant === 'cards') {
    return (
      <div className="profile-cards-container mb-6">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-secondary flex items-center gap-2">
              <ShieldAlert size={16} className="text-accent-primary" />
              Target Organization & Audit Profile
            </h3>
            <p className="text-xs text-muted mt-1">
              Select who is using this audit system to customize expected datasets and screening logic.
            </p>
          </div>
          <span className="badge badge-blue text-xs">Profile: {profile.shortName}</span>
        </div>

        <div className="grid-cols-3 gap-4">
          {Object.values(profiles).map((p) => {
            const IconComp = ICONS[p.icon] || Building2;
            const isSelected = p.id === profileId;
            return (
              <div
                key={p.id}
                role="button"
                tabIndex={0}
                className={`profile-card glass-card ${isSelected ? 'profile-card-selected' : ''}`}
                onClick={() => handleSelect(p.id)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleSelect(p.id); }}
                style={{ cursor: 'pointer', borderTop: isSelected ? `3px solid ${p.color}` : undefined }}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className="profile-card-icon" style={{ color: p.color, background: `${p.color}18` }}>
                      <IconComp size={18} />
                    </div>
                    <strong className="text-sm font-semibold">{p.name}</strong>
                  </div>
                  {isSelected ? (
                    <span className="badge badge-green text-xs">Active</span>
                  ) : (
                    <span className="badge text-xs" style={{ background: 'rgba(255,255,255,0.06)' }}>Select</span>
                  )}
                </div>

                <div className="text-xs text-muted font-medium mb-2">{p.badge}</div>
                <p className="text-xs text-secondary leading-relaxed mb-3">{p.description}</p>

                <div className="profile-card-footer pt-2 border-t border-glass">
                  <span className="text-xs text-muted block mb-1">Key Evidence Data:</span>
                  <div className="flex flex-wrap gap-1">
                    {p.recommendedDatasets.map((ds) => (
                      <span key={ds} className="badge text-xs" style={{ fontSize: '0.68rem', padding: '2px 6px' }}>
                        {ds}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {showNotice && (
          <div className="profile-data-notice mt-3 glass-card flex items-start gap-3 p-3">
            <Info size={17} className="text-accent-primary flex-shrink-0 mt-0.5" />
            <div className="text-xs leading-relaxed text-secondary">
              <strong className="text-primary block mb-0.5">Data Scope for {profile.name}:</strong>
              {profile.dataNotice}
            </div>
          </div>
        )}
      </div>
    );
  }

  // Segmented toggle pills
  return (
    <div className="profile-segmented-pills flex gap-2">
      {Object.values(profiles).map((p) => {
        const IconComp = ICONS[p.icon] || Building2;
        const isSelected = p.id === profileId;
        return (
          <button
            key={p.id}
            type="button"
            className={`btn ${isSelected ? 'btn-primary' : 'btn-secondary'} py-1.5 px-3 text-xs`}
            onClick={() => handleSelect(p.id)}
          >
            <IconComp size={14} />
            <span>{p.shortName}</span>
          </button>
        );
      })}
    </div>
  );
}
