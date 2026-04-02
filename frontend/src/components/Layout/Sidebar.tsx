import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, PlusCircle, Clock, User, LogOut, BookOpen, Shield, Users, FileText, Settings, Upload, Search, ArrowLeftRight, FolderUp, Moon, Sun } from 'lucide-react';
import { useAuth } from '../../utils/auth';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

const Sidebar: React.FC = () => {
  const location = useLocation();
  const { user, logout } = useAuth();
  const [darkMode, setDarkMode] = React.useState(() => {
    return document.documentElement.classList.contains('dark');
  });

  const toggleDarkMode = () => {
    const next = !darkMode;
    setDarkMode(next);
    if (next) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  };

  const navItems = [
    { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/analyze', icon: PlusCircle, label: 'New Analysis' },
    { path: '/compare', icon: ArrowLeftRight, label: 'Compare Texts' },
    { path: '/batch', icon: FolderUp, label: 'Batch Analysis' },
    { path: '/history', icon: Clock, label: 'History' },
    { path: '/rag/upload', icon: Upload, label: 'Upload Textbooks' },
    { path: '/rag/query', icon: Search, label: 'Query Textbooks' },
  ];

  const adminItems = [
    { path: '/admin', icon: Shield, label: 'Admin Dashboard' },
    { path: '/admin/users', icon: Users, label: 'User Management' },
    { path: '/admin/analyses', icon: FileText, label: 'All Analyses' },
  ];

  const isActive = (path: string) => location.pathname === path;
  const isAdmin = user?.role === 'admin';

  return (
    <aside className="w-64 bg-white dark:bg-gray-800 shadow-lg h-screen fixed left-0 top-0 flex flex-col">
      <div className="p-6 border-b dark:border-gray-700">
        <div className="flex items-center gap-3">
          <BookOpen className="w-8 h-8 text-primary-600" />
          <h1 className="text-xl font-bold text-gray-800 dark:text-gray-100">ClarityWorks</h1>
        </div>
      </div>

      <nav className="flex-1 p-4 overflow-y-auto">
        <ul className="space-y-2">
          {navItems.map((item) => (
            <li key={item.path}>
              <Link
                to={item.path}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                  isActive(item.path)
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-600 hover:bg-gray-50'
                }`}
              >
                <item.icon className="w-5 h-5" />
                <span className="font-medium">{item.label}</span>
              </Link>
            </li>
          ))}
        </ul>

        {/* Admin Section */}
        {isAdmin && (
          <>
            <div className="mt-6 mb-2 px-4">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                Admin
              </p>
            </div>
            <ul className="space-y-2">
              {adminItems.map((item) => (
                <li key={item.path}>
                  <Link
                    to={item.path}
                    className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                      isActive(item.path)
                        ? 'bg-purple-50 text-purple-700'
                        : 'text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <item.icon className="w-5 h-5" />
                    <span className="font-medium">{item.label}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </>
        )}
      </nav>

      <div className="p-4 border-t dark:border-gray-700">
        <div className="flex items-center gap-3 px-4 py-3 mb-2">
          <div className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center overflow-hidden flex-shrink-0">
            {user?.profilePicture ? (
              <img
                src={`${API_URL}${user.profilePicture}`}
                alt="Profile"
                className="w-full h-full object-cover"
              />
            ) : (
              <User className="w-5 h-5 text-gray-500" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-700 truncate">
              {user?.fullName}
            </p>
            <div className="flex items-center gap-2">
              <p className="text-xs text-gray-500 truncate">{user?.email}</p>
              {isAdmin && (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700">
                  Admin
                </span>
              )}
            </div>
          </div>
        </div>
        <button
          onClick={toggleDarkMode}
          className="flex items-center gap-3 px-4 py-3 w-full text-gray-600 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-700 rounded-lg transition-colors mb-2"
        >
          {darkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          <span className="font-medium">{darkMode ? 'Light Mode' : 'Dark Mode'}</span>
        </button>
        <Link
          to="/profile"
          className={`flex items-center gap-3 px-4 py-3 w-full rounded-lg transition-colors mb-2 ${
            isActive('/profile')
              ? 'bg-primary-50 text-primary-700'
              : 'text-gray-600 hover:bg-gray-50'
          }`}
        >
          <Settings className="w-5 h-5" />
          <span className="font-medium">Profile Settings</span>
        </Link>
        <button
          onClick={logout}
          className="flex items-center gap-3 px-4 py-3 w-full text-gray-600 hover:bg-gray-50 rounded-lg transition-colors"
        >
          <LogOut className="w-5 h-5" />
          <span className="font-medium">Logout</span>
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
