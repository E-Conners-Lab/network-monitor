import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft,
  Server,
  Activity,
  AlertTriangle,
  Network,
  Clock,
  RefreshCw,
  CheckCircle,
  XCircle,
  Cpu,
  HardDrive,
  Wifi,
  Terminal,
} from 'lucide-react';
import { devices as devicesApi, metrics as metricsApi, alerts as alertsApi } from '../services/api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export default function DeviceDetail() {
  const { id } = useParams();
  const [device, setDevice] = useState(null);
  const [deviceMetrics, setDeviceMetrics] = useState([]);
  const [deviceAlerts, setDeviceAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');

  const fetchDevice = async () => {
    try {
      const response = await devicesApi.get(id);
      setDevice(response.data);
    } catch (error) {
      console.error('Failed to fetch device:', error);
    }
  };

  const fetchMetrics = async () => {
    try {
      const response = await metricsApi.list({ device_id: id, limit: 100 });
      setDeviceMetrics(response.data || []);
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
    }
  };

  const fetchAlerts = async () => {
    try {
      const response = await alertsApi.list({ device_id: id, limit: 20 });
      setDeviceAlerts(response.data || []);
    } catch (error) {
      console.error('Failed to fetch alerts:', error);
    }
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchDevice(), fetchMetrics(), fetchAlerts()]);
      setLoading(false);
    };
    loadData();
  }, [id]);

  const handleCheck = async () => {
    setChecking(true);
    try {
      await devicesApi.check(id);
      await fetchDevice();
    } catch (error) {
      console.error('Health check failed:', error);
    } finally {
      setChecking(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  if (!device) {
    return (
      <div className="text-center py-12">
        <Server className="w-16 h-16 mx-auto text-gray-600 mb-4" />
        <h2 className="text-xl text-white mb-2">Device not found</h2>
        <Link to="/devices" className="text-blue-400 hover:text-blue-300">
          Back to devices
        </Link>
      </div>
    );
  }

  const tabs = [
    { id: 'overview', label: 'Overview', icon: Server },
    { id: 'metrics', label: 'Metrics', icon: Activity },
    { id: 'alerts', label: 'Alerts', icon: AlertTriangle },
    { id: 'interfaces', label: 'Interfaces', icon: Network },
  ];

  // Process metrics for charts
  const pingLatencyData = deviceMetrics
    .filter(m => m.metric_type === 'ping_latency')
    .slice(-24)
    .reverse()
    .map(m => ({
      time: new Date(m.created_at).toLocaleTimeString(),
      value: m.value,
    }));

  const pingLossData = deviceMetrics
    .filter(m => m.metric_type === 'ping_loss')
    .slice(-24)
    .reverse()
    .map(m => ({
      time: new Date(m.created_at).toLocaleTimeString(),
      value: m.value,
    }));

  // Get interface traffic data - group by interface
  const interfaceMetrics = deviceMetrics.filter(m =>
    m.metric_type === 'interface_in_octets' || m.metric_type === 'interface_out_octets'
  );

  // Group by interface index and get latest values, also track interface names
  const interfaceTraffic = {};
  const interfaceNames = {};
  interfaceMetrics.forEach(m => {
    const ifIndex = m.context?.replace('if_index_', '') || 'unknown';
    if (!interfaceTraffic[ifIndex]) {
      interfaceTraffic[ifIndex] = { in: 0, out: 0 };
    }
    // Get interface name from metadata if available
    if (m.metadata_?.if_name) {
      interfaceNames[ifIndex] = m.metadata_.if_name;
    }
    if (m.metric_type === 'interface_in_octets') {
      interfaceTraffic[ifIndex].in = Math.max(interfaceTraffic[ifIndex].in, m.value);
    } else {
      interfaceTraffic[ifIndex].out = Math.max(interfaceTraffic[ifIndex].out, m.value);
    }
  });

  // Get interface status and names
  const interfaceStatus = {};
  deviceMetrics
    .filter(m => m.metric_type === 'interface_status')
    .forEach(m => {
      const ifIndex = m.context?.replace('if_index_', '') || 'unknown';
      interfaceStatus[ifIndex] = m.value === 1 ? 'up' : 'down';
      // Get interface name from status metric metadata
      if (m.metadata_?.if_name) {
        interfaceNames[ifIndex] = m.metadata_.if_name;
      }
    });

  // Format bytes to human readable
  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            to="/devices"
            className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-gray-400" />
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-white">{device.name}</h1>
              <span
                className={`px-2 py-1 rounded-full text-xs font-medium ${
                  device.is_reachable
                    ? 'bg-green-900/50 text-green-400'
                    : 'bg-red-900/50 text-red-400'
                }`}
              >
                {device.is_reachable ? 'Online' : 'Offline'}
              </span>
            </div>
            <p className="text-gray-400">{device.ip_address}</p>
          </div>
        </div>
        <button
          onClick={handleCheck}
          disabled={checking}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${checking ? 'animate-spin' : ''}`} />
          Check Now
        </button>
      </div>

      {/* Device Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-900/50 rounded-lg">
              <Server className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <p className="text-sm text-gray-400">Model</p>
              <p className="text-white font-medium">{device.model || 'Unknown'}</p>
            </div>
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-900/50 rounded-lg">
              <Terminal className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <p className="text-sm text-gray-400">OS Version</p>
              <p className="text-white font-medium">{device.os_version || 'Unknown'}</p>
            </div>
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-900/50 rounded-lg">
              <Clock className="w-5 h-5 text-green-400" />
            </div>
            <div>
              <p className="text-sm text-gray-400">Last Seen</p>
              <p className="text-white font-medium">
                {device.last_seen
                  ? new Date(device.last_seen).toLocaleString()
                  : 'Never'}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-yellow-900/50 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-yellow-400" />
            </div>
            <div>
              <p className="text-sm text-gray-400">Active Alerts</p>
              <p className="text-white font-medium">
                {deviceAlerts.filter(a => !a.resolved_at).length}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-700">
        <nav className="flex gap-4">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-3 border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-gray-400 hover:text-white'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <h3 className="text-lg font-semibold text-white">Device Information</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-3">
                <div className="flex justify-between py-2 border-b border-gray-700">
                  <span className="text-gray-400">Hostname</span>
                  <span className="text-white">{device.hostname}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-700">
                  <span className="text-gray-400">IP Address</span>
                  <span className="text-white">{device.ip_address}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-700">
                  <span className="text-gray-400">Vendor</span>
                  <span className="text-white">{device.vendor || 'Unknown'}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-700">
                  <span className="text-gray-400">Device Type</span>
                  <span className="text-white">{device.device_type}</span>
                </div>
              </div>
              <div className="space-y-3">
                <div className="flex justify-between py-2 border-b border-gray-700">
                  <span className="text-gray-400">SSH Port</span>
                  <span className="text-white">{device.ssh_port}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-700">
                  <span className="text-gray-400">SNMP Community</span>
                  <span className="text-white">{device.snmp_community ? '••••••••' : 'Not set'}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-700">
                  <span className="text-gray-400">Location</span>
                  <span className="text-white">{device.location || 'Not set'}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-700">
                  <span className="text-gray-400">Status</span>
                  <span className={device.is_reachable ? 'text-green-400' : 'text-red-400'}>
                    {device.is_reachable ? 'Reachable' : 'Unreachable'}
                  </span>
                </div>
              </div>
            </div>

            {device.description && (
              <div className="mt-4">
                <h4 className="text-sm font-medium text-gray-400 mb-2">Description</h4>
                <p className="text-white bg-gray-900 p-3 rounded-lg">{device.description}</p>
              </div>
            )}

            {device.tags && Object.keys(device.tags).length > 0 && (
              <div className="mt-4">
                <h4 className="text-sm font-medium text-gray-400 mb-2">Tags</h4>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(device.tags).map(([key, value]) => (
                    key !== 'ssh_password' && (
                      <span
                        key={key}
                        className="px-2 py-1 bg-gray-700 rounded text-sm text-gray-300"
                      >
                        {key}: {value}
                      </span>
                    )
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'metrics' && (
          <div className="space-y-6">
            <h3 className="text-lg font-semibold text-white">Performance Metrics</h3>

            {pingLatencyData.length > 0 || pingLossData.length > 0 ? (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {pingLatencyData.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-400 mb-4 flex items-center gap-2">
                      <Activity className="w-4 h-4" /> Ping Latency (ms)
                    </h4>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={pingLatencyData}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                          <XAxis dataKey="time" stroke="#9CA3AF" fontSize={12} />
                          <YAxis stroke="#9CA3AF" fontSize={12} />
                          <Tooltip
                            contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                            labelStyle={{ color: '#9CA3AF' }}
                            formatter={(value) => [`${value.toFixed(2)} ms`, 'Latency']}
                          />
                          <Line
                            type="monotone"
                            dataKey="value"
                            stroke="#3B82F6"
                            strokeWidth={2}
                            dot={false}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}

                {pingLossData.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-400 mb-4 flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4" /> Packet Loss (%)
                    </h4>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={pingLossData}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                          <XAxis dataKey="time" stroke="#9CA3AF" fontSize={12} />
                          <YAxis stroke="#9CA3AF" fontSize={12} domain={[0, 100]} />
                          <Tooltip
                            contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                            labelStyle={{ color: '#9CA3AF' }}
                            formatter={(value) => [`${value}%`, 'Packet Loss']}
                          />
                          <Line
                            type="monotone"
                            dataKey="value"
                            stroke="#EF4444"
                            strokeWidth={2}
                            dot={false}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-12 text-gray-400">
                <Activity className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>No metrics collected yet</p>
                <p className="text-sm mt-1">Polling is running every 30 seconds</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'alerts' && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-white">Alert History</h3>

            {deviceAlerts.length > 0 ? (
              <div className="space-y-3">
                {deviceAlerts.map((alert) => (
                  <div
                    key={alert.id}
                    className={`p-4 rounded-lg border ${
                      alert.resolved_at
                        ? 'bg-gray-900 border-gray-700'
                        : alert.severity === 'critical'
                        ? 'bg-red-900/20 border-red-800'
                        : alert.severity === 'warning'
                        ? 'bg-yellow-900/20 border-yellow-800'
                        : 'bg-blue-900/20 border-blue-800'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3">
                        {alert.resolved_at ? (
                          <CheckCircle className="w-5 h-5 text-green-400 mt-0.5" />
                        ) : (
                          <XCircle className={`w-5 h-5 mt-0.5 ${
                            alert.severity === 'critical' ? 'text-red-400' :
                            alert.severity === 'warning' ? 'text-yellow-400' : 'text-blue-400'
                          }`} />
                        )}
                        <div>
                          <p className="text-white font-medium">{alert.title}</p>
                          <p className="text-sm text-gray-400 mt-1">{alert.message}</p>
                          <p className="text-xs text-gray-500 mt-2">
                            {new Date(alert.created_at).toLocaleString()}
                            {alert.resolved_at && (
                              <span className="text-green-400 ml-2">
                                Resolved {new Date(alert.resolved_at).toLocaleString()}
                              </span>
                            )}
                          </p>
                        </div>
                      </div>
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        alert.severity === 'critical' ? 'bg-red-900/50 text-red-400' :
                        alert.severity === 'warning' ? 'bg-yellow-900/50 text-yellow-400' :
                        'bg-blue-900/50 text-blue-400'
                      }`}>
                        {alert.severity}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-gray-400">
                <CheckCircle className="w-12 h-12 mx-auto mb-3 text-green-500 opacity-50" />
                <p>No alerts for this device</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'interfaces' && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-white">Network Interfaces</h3>

            {Object.keys(interfaceTraffic).length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="text-left text-gray-400 text-sm border-b border-gray-700">
                      <th className="pb-3 pr-4">Interface</th>
                      <th className="pb-3 pr-4">Status</th>
                      <th className="pb-3 pr-4 text-right">Bytes In</th>
                      <th className="pb-3 text-right">Bytes Out</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(interfaceTraffic)
                      .sort((a, b) => parseInt(a[0]) - parseInt(b[0]))
                      .map(([ifIndex, traffic]) => (
                        <tr key={ifIndex} className="border-b border-gray-700/50">
                          <td className="py-3 pr-4">
                            <div className="flex items-center gap-2">
                              <Wifi className="w-4 h-4 text-gray-500" />
                              <div>
                                <span className="text-white">{interfaceNames[ifIndex] || `Interface ${ifIndex}`}</span>
                                {interfaceNames[ifIndex] && (
                                  <span className="text-gray-500 text-xs ml-2">(idx: {ifIndex})</span>
                                )}
                              </div>
                            </div>
                          </td>
                          <td className="py-3 pr-4">
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              interfaceStatus[ifIndex] === 'up'
                                ? 'bg-green-900/50 text-green-400'
                                : 'bg-red-900/50 text-red-400'
                            }`}>
                              {interfaceStatus[ifIndex] || 'unknown'}
                            </span>
                          </td>
                          <td className="py-3 pr-4 text-right">
                            <span className="text-green-400">{formatBytes(traffic.in)}</span>
                          </td>
                          <td className="py-3 text-right">
                            <span className="text-blue-400">{formatBytes(traffic.out)}</span>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-12 text-gray-400">
                <Network className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>Interface data not yet collected</p>
                <p className="text-sm mt-1">SNMP polling will collect interface metrics</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
