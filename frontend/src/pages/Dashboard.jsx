import { useState, useEffect, useMemo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Server,
  AlertTriangle,
  CheckCircle,
  Activity,
  RefreshCw
} from 'lucide-react';
import { devices as devicesApi, alerts as alertsApi, remediation as remediationApi } from '../services/api';
import StatsCard from '../components/StatsCard';
import DeviceCard from '../components/DeviceCard';
import AlertCard from '../components/AlertCard';

export default function Dashboard() {
  const [devices, setDevices] = useState([]);
  const [activeAlerts, setActiveAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = async (isRefresh = false) => {
    const startTime = Date.now();
    try {
      const [devicesRes, alertsRes] = await Promise.all([
        devicesApi.list(),
        alertsApi.listActive(),
      ]);
      setDevices(devicesRes.data);
      setActiveAlerts(alertsRes.data);
    } catch (error) {
      console.error('Failed to fetch data:', error);
    } finally {
      setLoading(false);
      if (isRefresh) {
        const elapsed = Date.now() - startTime;
        const remaining = Math.max(0, 500 - elapsed);
        setTimeout(() => setRefreshing(false), remaining);
      } else {
        setRefreshing(false);
      }
    }
  };

  useEffect(() => {
    fetchData();
    // Refresh every 30 seconds
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchData(true);
  };

  const handleAcknowledge = async (alertId) => {
    try {
      await alertsApi.acknowledge(alertId);
      fetchData();
    } catch (error) {
      console.error('Failed to acknowledge alert:', error);
    }
  };

  const handleResolve = async (alertId) => {
    try {
      await alertsApi.resolve(alertId);
      fetchData();
    } catch (error) {
      console.error('Failed to resolve alert:', error);
    }
  };

  const handleAutoRemediate = async (alertId) => {
    try {
      await remediationApi.autoRemediate(alertId);
      // Wait a bit then refresh
      setTimeout(fetchData, 3000);
    } catch (error) {
      console.error('Failed to auto-remediate:', error);
    }
  };

  // Memoize computed values to avoid recalculation on every render
  const reachableCount = useMemo(() => devices.filter(d => d.is_reachable).length, [devices]);
  const unreachableCount = useMemo(() => devices.filter(d => !d.is_reachable).length, [devices]);
  const criticalAlerts = useMemo(() => activeAlerts.filter(a => a.severity === 'critical').length, [activeAlerts]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-gray-400">Network overview and status</p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all ${
            refreshing
              ? 'bg-blue-700 cursor-wait'
              : 'bg-blue-600 hover:bg-blue-700'
          }`}
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="Total Devices"
          value={devices.length}
          icon={Server}
          color="blue"
        />
        <StatsCard
          title="Devices Online"
          value={reachableCount}
          subtitle={`${devices.length > 0 ? Math.round((reachableCount / devices.length) * 100) : 0}% uptime`}
          icon={CheckCircle}
          color="green"
        />
        <StatsCard
          title="Devices Offline"
          value={unreachableCount}
          icon={Server}
          color={unreachableCount > 0 ? 'red' : 'green'}
        />
        <StatsCard
          title="Active Alerts"
          value={activeAlerts.length}
          subtitle={`${criticalAlerts} critical`}
          icon={AlertTriangle}
          color={criticalAlerts > 0 ? 'red' : activeAlerts.length > 0 ? 'yellow' : 'green'}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Devices */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">Devices</h2>
            <Link to="/devices" className="text-sm text-blue-400 hover:text-blue-300">
              View all
            </Link>
          </div>
          {devices.length === 0 ? (
            <div className="bg-gray-800 rounded-lg p-8 text-center border border-gray-700">
              <Server className="w-12 h-12 mx-auto text-gray-600 mb-3" />
              <p className="text-gray-400">No devices configured</p>
              <Link
                to="/devices"
                className="inline-block mt-3 text-sm text-blue-400 hover:text-blue-300"
              >
                Add your first device
              </Link>
            </div>
          ) : (
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {devices.slice(0, 6).map(device => (
                <DeviceCard key={device.id} device={device} />
              ))}
            </div>
          )}
        </div>

        {/* Alerts */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">Active Alerts</h2>
            <Link to="/alerts" className="text-sm text-blue-400 hover:text-blue-300">
              View all
            </Link>
          </div>
          {activeAlerts.length === 0 ? (
            <div className="bg-gray-800 rounded-lg p-8 text-center border border-gray-700">
              <CheckCircle className="w-12 h-12 mx-auto text-green-500 mb-3" />
              <p className="text-gray-400">No active alerts</p>
              <p className="text-sm text-gray-500 mt-1">All systems operational</p>
            </div>
          ) : (
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {activeAlerts.slice(0, 5).map(alert => (
                <AlertCard
                  key={alert.id}
                  alert={alert}
                  onAcknowledge={handleAcknowledge}
                  onResolve={handleResolve}
                  onAutoRemediate={handleAutoRemediate}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
