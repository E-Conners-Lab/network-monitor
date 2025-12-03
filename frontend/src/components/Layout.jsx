import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Server,
  AlertTriangle,
  Activity,
  Wrench,
  FlaskConical,
  LogOut,
  Wifi,
  WifiOff,
  Radio,
  Settings,
  Bell
} from 'lucide-react';
import { system } from '../services/api';

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/devices', label: 'Devices', icon: Server },
  { path: '/alerts', label: 'Alerts', icon: AlertTriangle },
  { path: '/metrics', label: 'Metrics', icon: Activity },
  { path: '/remediation', label: 'Remediation', icon: Wrench },
  { path: '/tests', label: 'Tests', icon: FlaskConical },
];

export default function Layout({ children, isConnected, onLogout }) {
  const location = useLocation();
  const [version, setVersion] = useState(null);
  const [hoveredItem, setHoveredItem] = useState(null);

  useEffect(() => {
    system.version()
      .then(res => setVersion(res.data.version))
      .catch(() => setVersion(null));
  }, []);

  // Get current page title
  const currentPage = navItems.find(item => item.path === location.pathname)?.label || 'Dashboard';

  return (
    <div className="flex h-screen bg-zinc-900">
      {/* VS Code style activity bar - icons only */}
      <aside className="w-14 bg-zinc-950 flex flex-col items-center py-2 border-r border-zinc-800">
        {/* Logo */}
        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-teal-500 to-cyan-600 flex items-center justify-center mb-4">
          <Radio className="w-5 h-5 text-white" />
        </div>

        {/* Navigation icons */}
        <nav className="flex-1 flex flex-col items-center gap-1 py-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            const isHovered = hoveredItem === item.path;

            return (
              <div key={item.path} className="relative">
                <Link
                  to={item.path}
                  onMouseEnter={() => setHoveredItem(item.path)}
                  onMouseLeave={() => setHoveredItem(null)}
                  className={`
                    w-10 h-10 flex items-center justify-center rounded-lg transition-all
                    ${isActive
                      ? 'bg-zinc-800 text-teal-400'
                      : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50'
                    }
                  `}
                >
                  {isActive && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-6 bg-teal-400 rounded-r" />
                  )}
                  <Icon className="w-5 h-5" />
                </Link>

                {/* Tooltip */}
                {isHovered && (
                  <div className="absolute left-14 top-1/2 -translate-y-1/2 z-50">
                    <div className="bg-zinc-800 text-zinc-200 text-sm px-3 py-1.5 rounded-md shadow-xl border border-zinc-700 whitespace-nowrap">
                      {item.label}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </nav>

        {/* Bottom icons */}
        <div className="flex flex-col items-center gap-1 pb-2">
          {/* Connection status */}
          <div
            className="relative"
            onMouseEnter={() => setHoveredItem('status')}
            onMouseLeave={() => setHoveredItem(null)}
          >
            <div className={`
              w-10 h-10 flex items-center justify-center rounded-lg
              ${isConnected ? 'text-emerald-500' : 'text-red-500'}
            `}>
              {isConnected ? <Wifi className="w-5 h-5" /> : <WifiOff className="w-5 h-5" />}
            </div>
            {hoveredItem === 'status' && (
              <div className="absolute left-14 top-1/2 -translate-y-1/2 z-50">
                <div className="bg-zinc-800 text-zinc-200 text-sm px-3 py-1.5 rounded-md shadow-xl border border-zinc-700 whitespace-nowrap">
                  {isConnected ? 'Connected' : 'Disconnected'}
                </div>
              </div>
            )}
          </div>

          {/* Logout */}
          <div
            className="relative"
            onMouseEnter={() => setHoveredItem('logout')}
            onMouseLeave={() => setHoveredItem(null)}
          >
            <button
              onClick={onLogout}
              className="w-10 h-10 flex items-center justify-center rounded-lg text-zinc-500 hover:text-red-400 hover:bg-zinc-800/50 transition-all"
            >
              <LogOut className="w-5 h-5" />
            </button>
            {hoveredItem === 'logout' && (
              <div className="absolute left-14 top-1/2 -translate-y-1/2 z-50">
                <div className="bg-zinc-800 text-zinc-200 text-sm px-3 py-1.5 rounded-md shadow-xl border border-zinc-700 whitespace-nowrap">
                  Sign Out
                </div>
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* Main area */}
      <div className="flex-1 flex flex-col">
        {/* Top header bar */}
        <header className="h-12 bg-zinc-900 border-b border-zinc-800 flex items-center justify-between px-4">
          <div className="flex items-center gap-3">
            <h1 className="text-zinc-200 font-medium">{currentPage}</h1>
            <span className="text-zinc-600 text-sm">•</span>
            <span className="text-zinc-500 text-sm">Network Monitor</span>
          </div>

          <div className="flex items-center gap-2">
            {version && (
              <span className="text-xs text-zinc-600 px-2 py-1 bg-zinc-800 rounded">
                v{version}
              </span>
            )}
            <button className="w-8 h-8 flex items-center justify-center rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-all">
              <Bell className="w-4 h-4" />
            </button>
            <button className="w-8 h-8 flex items-center justify-center rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-all">
              <Settings className="w-4 h-4" />
            </button>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto bg-zinc-900">
          <div className="p-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
