import React from 'react';
import { Outlet, Navigate, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import { useAuth } from '../../utils/auth';

const ROUTE_EYEBROW: Record<string, string> = {
  '/dashboard': 'Overview',
  '/analyze': 'Workspace',
  '/compare': 'Workspace',
  '/batch': 'Workspace',
  '/history': 'Workspace',
  '/profile': 'Account',
  '/rag/upload': 'Library',
  '/rag/query': 'Library',
  '/admin': 'Administration',
  '/admin/users': 'Administration',
  '/admin/analyses': 'Administration',
};

const ROUTE_TITLE: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/analyze': 'New Analysis',
  '/compare': 'Compare Texts',
  '/batch': 'Batch Analysis',
  '/history': 'History',
  '/profile': 'Profile Settings',
  '/rag/upload': 'Upload Textbooks',
  '/rag/query': 'Query Textbooks',
  '/admin': 'Admin Dashboard',
  '/admin/users': 'User Management',
  '/admin/analyses': 'All Analyses',
};

const Layout: React.FC = () => {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ background: 'var(--surface)' }}
      >
        <div
          className="animate-spin rounded-full h-10 w-10 border-b-2"
          style={{ borderColor: 'var(--p-700)' }}
        />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  // resolve best prefix match
  const path = location.pathname;
  const matchKey = Object.keys(ROUTE_TITLE)
    .filter((k) => path === k || path.startsWith(k + '/'))
    .sort((a, b) => b.length - a.length)[0];
  const eyebrow = matchKey ? ROUTE_EYEBROW[matchKey] : 'Workspace';
  const title = matchKey ? ROUTE_TITLE[matchKey] : '';

  return (
    <div
      className="min-h-screen"
      style={{ background: 'var(--surface)', color: 'var(--text-1)' }}
    >
      <Sidebar />
      <main className="ml-60 min-h-screen flex flex-col">
        {/* Top app bar */}
        <header
          className="sticky top-0 z-30 flex items-center justify-between px-8 h-14"
          style={{
            background: 'color-mix(in srgb, var(--surface) 82%, transparent)',
            backdropFilter: 'blur(12px)',
            borderBottom: '1px solid var(--divider)',
          }}
        >
          <div className="flex items-baseline gap-3 min-w-0">
            <span className="cw-eyebrow" style={{ color: 'var(--text-3)' }}>{eyebrow}</span>
            <span style={{ color: 'var(--text-4)', fontSize: 11 }}>/</span>
            <h2
              className="truncate"
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: 14,
                fontWeight: 700,
                letterSpacing: '-0.01em',
                color: 'var(--text-1)',
              }}
            >
              {title}
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <span
              className="cw-eyebrow hidden md:inline-flex items-center gap-1.5 px-2.5 h-7"
              style={{
                background: 'var(--surface-sunk)',
                borderRadius: 'var(--r-full)',
                color: 'var(--text-3)',
                letterSpacing: '0.1em',
              }}
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: 'var(--ok-500)',
                  display: 'inline-block',
                  boxShadow: '0 0 0 3px color-mix(in srgb, var(--ok-500) 18%, transparent)',
                }}
              />
              ML Engine · Online
            </span>
          </div>
        </header>

        <div className="flex-1 px-8 py-8">
          <div className="max-w-canvas mx-auto">
            <Outlet />
          </div>
        </div>

        <footer
          className="mt-auto px-8 py-5 flex justify-between items-center"
          style={{
            borderTop: '1px solid var(--divider)',
            fontSize: 10.5,
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            color: 'var(--text-4)',
            fontWeight: 600,
          }}
        >
          <span>ClarityWorks · Readability Lab</span>
          <span>v4.2 · NLP Engine v2.0</span>
        </footer>
      </main>
    </div>
  );
};

export default Layout;
