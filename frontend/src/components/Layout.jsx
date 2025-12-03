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
  Radio
} from 'lucide-react';
import { system } from '../services/api';

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard, color: 'from-blue-500 to-blue-600' },
  { path: '/devices', label: 'Devices', icon: Server, color: 'from-emerald-500 to-emerald-600' },
  { path: '/alerts', label: 'Alerts', icon: AlertTriangle, color: 'from-amber-500 to-amber-600' },
  { path: '/metrics', label: 'Metrics', icon: Activity, color: 'from-purple-500 to-purple-600' },
  { path: '/remediation', label: 'Remediation', icon: Wrench, color: 'from-rose-500 to-rose-600' },
  { path: '/tests', label: 'Tests', icon: FlaskConical, color: 'from-cyan-500 to-cyan-600' },
];

export default function Layout({ children, isConnected, onLogout }) {
  const location = useLocation();
  const [version, setVersion] = useState(null);

  useEffect(() => {
    system.version()
      .then(res => setVersion(res.data.version))
      .catch(() => setVersion(null));
  }, []);

  return (
    <div className="flex h-screen bg-slate-950">
      {/* Sidebar with tile navigation */}
      <aside className="w-72 bg-slate-900 border-r border-slate-800 flex flex-col">
        {/* Logo */}
        <div className="p-5 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/25">
              <Radio className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-white">NetMonitor</h1>
              {version && (
                <span className="text-xs text-slate-500">v{version}</span>
              )}
            </div>
          </div>
        </div>

        {/* Tile Navigation */}
        <nav className="flex-1 p-4">
          <div className="grid grid-cols-2 gap-3">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`
                    relative p-4 rounded-2xl transition-all duration-200 group
                    ${isActive
                      ? `bg-gradient-to-br ${item.color} shadow-lg`
                      : 'bg-slate-800/50 hover:bg-slate-800 border border-slate-700/50 hover:border-slate-600'
                    }
                  `}
                >
                  <div className={`
                    w-10 h-10 rounded-xl flex items-center justify-center mb-2
                    ${isActive
                      ? 'bg-white/20'
                      : 'bg-slate-700/50 group-hover:bg-slate-700'
                    }
                  `}>
                    <Icon className={`w-5 h-5 ${isActive ? 'text-white' : 'text-slate-400 group-hover:text-white'}`} />
                  </div>
                  <span className={`text-sm font-medium ${isActive ? 'text-white' : 'text-slate-400 group-hover:text-white'}`}>
                    {item.label}
                  </span>
                  {isActive && (
                    <div className="absolute top-2 right-2 w-2 h-2 rounded-full bg-white/50" />
                  )}
                </Link>
              );
            })}
          </div>
        </nav>

        {/* Status Card */}
        <div className="p-4 border-t border-slate-800">
          <div className={`
            p-4 rounded-2xl mb-3
            ${isConnected
              ? 'bg-emerald-500/10 border border-emerald-500/20'
              : 'bg-red-500/10 border border-red-500/20'
            }
          `}>
            <div className="flex items-center gap-3">
              <div className={`
                w-10 h-10 rounded-xl flex items-center justify-center
                ${isConnected ? 'bg-emerald-500/20' : 'bg-red-500/20'}
              `}>
                {isConnected ? (
                  <Wifi className="w-5 h-5 text-emerald-400" />
                ) : (
                  <WifiOff className="w-5 h-5 text-red-400" />
                )}
              </div>
              <div>
                <div className={`text-sm font-medium ${isConnected ? 'text-emerald-400' : 'text-red-400'}`}>
                  {isConnected ? 'Connected' : 'Disconnected'}
                </div>
                <div className="text-xs text-slate-500">
                  WebSocket {isConnected ? 'active' : 'inactive'}
                </div>
              </div>
            </div>
          </div>

          {/* Logout Button */}
          <button
            onClick={onLogout}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-slate-800/50 border border-slate-700/50 text-slate-400 hover:text-white hover:bg-slate-800 hover:border-red-500/50 transition-all"
          >
            <LogOut className="w-4 h-4" />
            <span className="text-sm font-medium">Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-slate-950">
        <div className="p-6">
          {children}
        </div>
      </main>
    </div>
  );
}
