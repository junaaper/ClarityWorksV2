import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, PlusCircle, Clock, User, LogOut,
  Shield, Users, FileText, Upload, Search,
  ArrowLeftRight, FolderUp, Moon, Sun, Settings,
} from 'lucide-react';
import { useAuth } from '../../utils/auth';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

type NavItem = { path: string; icon: React.ComponentType<{ className?: string }>; label: string };

const Sidebar: React.FC = () => {
  const location = useLocation();
  const { user, logout } = useAuth();
  const [darkMode, setDarkMode] = React.useState(() =>
    document.documentElement.classList.contains('dark'),
  );

  const toggleDarkMode = () => {
    const next = !darkMode;
    setDarkMode(next);
    const root = document.documentElement;
    if (next) {
      root.classList.add('dark');
      root.setAttribute('data-theme', 'dark');
      localStorage.setItem('theme', 'dark');
    } else {
      root.classList.remove('dark');
      root.removeAttribute('data-theme');
      localStorage.setItem('theme', 'light');
    }
  };

  const workspaceItems: NavItem[] = [
    { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/analyze', icon: PlusCircle, label: 'New Analysis' },
    { path: '/compare', icon: ArrowLeftRight, label: 'Compare Texts' },
    { path: '/batch', icon: FolderUp, label: 'Batch Analysis' },
    { path: '/history', icon: Clock, label: 'History' },
  ];

  const libraryItems: NavItem[] = [
    { path: '/rag/upload', icon: Upload, label: 'Upload Textbooks' },
    { path: '/rag/query', icon: Search, label: 'Query Textbooks' },
  ];

  const adminItems: NavItem[] = [
    { path: '/admin', icon: Shield, label: 'Admin Dashboard' },
    { path: '/admin/users', icon: Users, label: 'User Management' },
    { path: '/admin/analyses', icon: FileText, label: 'All Analyses' },
  ];

  const isActive = (path: string) => location.pathname === path;
  const isAdmin = user?.role === 'admin';

  const NavLink: React.FC<{ item: NavItem }> = ({ item }) => {
    const active = isActive(item.path);
    return (
      <li>
        <Link
          to={item.path}
          className="group flex items-center gap-2.5 pl-3 pr-3 py-2 rounded-md text-[12.5px] font-medium transition-all duration-150"
          style={{
            color: active ? 'var(--p-900)' : 'var(--text-2)',
            background: active ? 'var(--surface-raised)' : 'transparent',
            boxShadow: active ? 'var(--sh-1)' : 'none',
            fontWeight: active ? 600 : 500,
          }}
          onMouseEnter={(e) => {
            if (!active) {
              (e.currentTarget as HTMLAnchorElement).style.background = 'color-mix(in srgb, var(--surface-raised) 60%, transparent)';
              (e.currentTarget as HTMLAnchorElement).style.color = 'var(--text-1)';
              (e.currentTarget as HTMLAnchorElement).style.transform = 'translateX(2px)';
            }
          }}
          onMouseLeave={(e) => {
            if (!active) {
              (e.currentTarget as HTMLAnchorElement).style.background = 'transparent';
              (e.currentTarget as HTMLAnchorElement).style.color = 'var(--text-2)';
              (e.currentTarget as HTMLAnchorElement).style.transform = 'translateX(0)';
            }
          }}
        >
          <item.icon className="w-[15px] h-[15px] flex-shrink-0" />
          <span className="truncate">{item.label}</span>
        </Link>
      </li>
    );
  };

  const GroupLabel: React.FC<{ children: React.ReactNode }> = ({ children }) => (
    <div
      className="px-3 pt-4 pb-1.5"
      style={{
        fontFamily: 'var(--font-sans)',
        fontSize: 10,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        color: 'var(--text-4)',
        fontWeight: 700,
      }}
    >
      {children}
    </div>
  );

  return (
    <aside
      className="w-60 h-screen fixed left-0 top-0 flex flex-col z-40"
      style={{
        background: 'var(--surface-sunk)',
        borderRight: '1px solid var(--divider)',
      }}
    >
      {/* Brand */}
      <div className="flex items-center gap-2.5 px-5 pt-5 pb-4">
        <div
          className="grid place-items-center text-white flex-shrink-0"
          style={{
            width: 30,
            height: 30,
            borderRadius: 7,
            background: 'var(--g-scholar)',
            fontFamily: 'var(--font-display)',
            fontWeight: 800,
            fontSize: 14,
            letterSpacing: '-0.02em',
            boxShadow: 'inset 0 -4px 10px rgba(0,0,0,.18)',
          }}
        >
          CW
        </div>
        <div className="min-w-0">
          <div
            style={{
              fontFamily: 'var(--font-display)',
              fontWeight: 800,
              fontSize: 14,
              color: 'var(--text-1)',
              letterSpacing: '0.05em',
              textTransform: 'uppercase',
              lineHeight: 1.1,
            }}
          >
            ClarityWorks
          </div>
          <div
            style={{
              fontSize: 9.5,
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
              color: 'var(--text-4)',
              fontWeight: 600,
              marginTop: 2,
            }}
          >
            Readability Lab
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-3 pb-2">
        <GroupLabel>Workspace</GroupLabel>
        <ul className="space-y-0.5">
          {workspaceItems.map((item) => (
            <NavLink key={item.path} item={item} />
          ))}
        </ul>

        <GroupLabel>Library</GroupLabel>
        <ul className="space-y-0.5">
          {libraryItems.map((item) => (
            <NavLink key={item.path} item={item} />
          ))}
        </ul>

        {isAdmin && (
          <>
            <GroupLabel>Administration</GroupLabel>
            <ul className="space-y-0.5">
              {adminItems.map((item) => (
                <NavLink key={item.path} item={item} />
              ))}
            </ul>
          </>
        )}
      </nav>

      {/* Foot */}
      <div
        className="px-3 pt-3 pb-3 space-y-0.5"
        style={{ borderTop: '1px solid var(--divider)' }}
      >
        <div
          className="flex items-center gap-2.5 px-2.5 py-2 mb-1 rounded-md"
          style={{ background: 'var(--surface-raised)', boxShadow: 'var(--sh-1)' }}
        >
          <div
            className="grid place-items-center flex-shrink-0 overflow-hidden text-white"
            style={{
              width: 30,
              height: 30,
              borderRadius: 7,
              background: 'var(--g-scholar)',
              fontSize: 11,
              fontWeight: 700,
            }}
          >
            {user?.profilePicture ? (
              <img
                src={`${API_URL}${user.profilePicture}`}
                alt="Profile"
                className="w-full h-full object-cover"
              />
            ) : (
              <User className="w-3.5 h-3.5" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div
              className="truncate"
              style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-1)', lineHeight: 1.2 }}
            >
              {user?.fullName}
            </div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <div
                className="truncate"
                style={{ fontSize: 10.5, color: 'var(--text-4)' }}
              >
                {isAdmin ? 'Administrator' : 'Researcher'}
              </div>
              {isAdmin && <span className="cw-badge cw-badge-primary" style={{ height: 15, fontSize: 9, padding: '0 6px' }}>Admin</span>}
            </div>
          </div>
        </div>

        <Link
          to="/profile"
          className="flex items-center gap-2.5 px-2.5 py-1.5 w-full rounded-md transition-colors"
          style={{
            color: isActive('/profile') ? 'var(--p-900)' : 'var(--text-2)',
            background: isActive('/profile') ? 'var(--surface-raised)' : 'transparent',
            fontSize: 12,
            fontWeight: 500,
          }}
        >
          <Settings className="w-[14px] h-[14px]" />
          <span>Profile</span>
        </Link>

        <button
          onClick={toggleDarkMode}
          className="flex items-center gap-2.5 px-2.5 py-1.5 w-full rounded-md transition-colors"
          style={{ color: 'var(--text-2)', fontSize: 12, fontWeight: 500 }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'color-mix(in srgb, var(--surface-raised) 60%, transparent)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        >
          {darkMode ? <Sun className="w-[14px] h-[14px]" /> : <Moon className="w-[14px] h-[14px]" />}
          <span>{darkMode ? 'Light mode' : 'Dark mode'}</span>
        </button>

        <button
          onClick={logout}
          className="flex items-center gap-2.5 px-2.5 py-1.5 w-full rounded-md transition-colors"
          style={{ color: 'var(--text-2)', fontSize: 12, fontWeight: 500 }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'color-mix(in srgb, var(--surface-raised) 60%, transparent)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        >
          <LogOut className="w-[14px] h-[14px]" />
          <span>Log out</span>
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
