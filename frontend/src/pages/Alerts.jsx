import { useState, useEffect } from 'react';
import {
  AlertTriangle,
  RefreshCw,
  Filter,
  CheckCircle
} from 'lucide-react';
import { alerts as alertsApi, remediation as remediationApi } from '../services/api';
import AlertCard from '../components/AlertCard';

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('active');
  const [severityFilter, setSeverityFilter] = useState('');

  const fetchAlerts = async () => {
    try {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      if (severityFilter) params.severity = severityFilter;

      const res = await alertsApi.list(params);
      setAlerts(res.data);
    } catch (error) {
      console.error('Failed to fetch alerts:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, [statusFilter, severityFilter]);

  const handleAcknowledge = async (alertId) => {
    try {
      await alertsApi.acknowledge(alertId);
      fetchAlerts();
    } catch (error) {
      console.error('Failed to acknowledge alert:', error);
    }
  };

  const handleResolve = async (alertId) => {
    try {
      await alertsApi.resolve(alertId);
      fetchAlerts();
    } catch (error) {
      console.error('Failed to resolve alert:', error);
    }
  };

  const handleAutoRemediate = async (alertId) => {
    try {
      await remediationApi.autoRemediate(alertId);
      // Wait a bit then refresh
      setTimeout(fetchAlerts, 3000);
    } catch (error) {
      console.error('Failed to auto-remediate:', error);
    }
  };

  const criticalCount = alerts.filter(a => a.severity === 'critical' && a.status === 'active').length;
  const warningCount = alerts.filter(a => a.severity === 'warning' && a.status === 'active').length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Alerts</h1>
          <p className="text-gray-400">
            {criticalCount > 0 && <span className="text-red-400">{criticalCount} critical</span>}
            {criticalCount > 0 && warningCount > 0 && ', '}
            {warningCount > 0 && <span className="text-yellow-400">{warningCount} warning</span>}
            {criticalCount === 0 && warningCount === 0 && 'No active alerts'}
          </p>
        </div>
        <button
          onClick={fetchAlerts}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <Filter className="w-4 h-4" />
          Filters:
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
        >
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="resolved">Resolved</option>
        </select>
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
        >
          <option value="">All Severities</option>
          <option value="critical">Critical</option>
          <option value="warning">Warning</option>
          <option value="info">Info</option>
        </select>
      </div>

      {/* Alert List */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
        </div>
      ) : alerts.length === 0 ? (
        <div className="bg-gray-800 rounded-lg p-12 text-center border border-gray-700">
          <CheckCircle className="w-16 h-16 mx-auto text-green-500 mb-4" />
          <h3 className="text-lg font-medium text-white mb-2">No alerts</h3>
          <p className="text-gray-400">
            {statusFilter || severityFilter
              ? 'No alerts match your filters'
              : 'All systems are operating normally'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map(alert => (
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
  );
}
