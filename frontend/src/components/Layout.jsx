import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Server,
  AlertTriangle,
  Activity,
  Network,
  Wrench,
  FlaskConical,
  FileText,
  LogOut,
  Wifi,
  WifiOff
} from 'lucide-react';
import { system } from '../services/api';

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/devices', label: 'Devices', icon: Server },
  { path: '/alerts', label: 'Alerts', icon: AlertTriangle },
  { path: '/metrics', label: 'Metrics', icon: Activity },
  { path: '/topology', label: 'Topology', icon: Network },
  { path: '/remediation', label: 'Remediation', icon: Wrench },
  { path: '/tests', label: 'Tests', icon: FlaskConical },
  { path: '/configs', label: 'Configs', icon: FileText },
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
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-800 border-r border-gray-700">
        <div className="p-4 border-b border-gray-700">
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Activity className="w-6 h-6 text-green-500" />
            Network Monitor
          </h1>
        </div>

        <nav className="p-4">
          <ul className="space-y-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <li key={item.path}>
                  <Link
                    to={item.path}
                    className={`flex items-center gap-3 px-4 py-2 rounded-lg transition-colors ${
                      isActive
                        ? 'bg-blue-600 text-white'
                        : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                    }`}
                  >
                    <Icon className="w-5 h-5" />
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="absolute bottom-0 left-0 w-64 p-4 border-t border-gray-700">
          <div className="flex items-center justify-between text-sm mb-2">
            <div className="flex items-center gap-2">
              {isConnected ? (
                <>
                  <Wifi className="w-4 h-4 text-green-500" />
                  <span className="text-green-500">Connected</span>
                </>
              ) : (
                <>
                  <WifiOff className="w-4 h-4 text-red-500" />
                  <span className="text-red-500">Disconnected</span>
                </>
              )}
            </div>
            <button
              onClick={onLogout}
              className="flex items-center gap-1 text-gray-400 hover:text-white"
            >
              <LogOut className="w-4 h-4" />
              Logout
            </button>
          </div>
          {version && (
            <div className="text-xs text-gray-500 text-center">
              v{version}
            </div>
          )}
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="p-6">
          {children}
        </div>
      </main>
    </div>
  );
}
