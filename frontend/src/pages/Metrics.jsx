import { useState, useEffect } from 'react';
import {
  Activity,
  RefreshCw,
  Cpu,
  HardDrive,
  Clock
} from 'lucide-react';
import { parseUTCDate } from '../utils/date';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts';
import { devices as devicesApi, metrics as metricsApi } from '../services/api';

export default function Metrics() {
  const [devices, setDevices] = useState([]);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [metricsData, setMetricsData] = useState({});
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState(24);

  useEffect(() => {
    const fetchDevices = async () => {
      try {
        const res = await devicesApi.list();
        setDevices(res.data);
        if (res.data.length > 0 && !selectedDevice) {
          setSelectedDevice(res.data[0].id);
        }
      } catch (error) {
        console.error('Failed to fetch devices:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchDevices();
  }, []);

  useEffect(() => {
    if (!selectedDevice) return;

    const fetchMetrics = async () => {
      try {
        const metricTypes = [
          'cpu_utilization',
          'memory_utilization',
          'ping_latency',
          'ping_loss'
        ];

        const results = {};
        for (const type of metricTypes) {
          try {
            const res = await metricsApi.history(selectedDevice, type, timeRange);
            results[type] = res.data;
          } catch (e) {
            results[type] = [];
          }
        }
        setMetricsData(results);
      } catch (error) {
        console.error('Failed to fetch metrics:', error);
      }
    };

    fetchMetrics();
    const interval = setInterval(fetchMetrics, 30000);
    return () => clearInterval(interval);
  }, [selectedDevice, timeRange]);

  const formatChartData = (data) => {
    if (!Array.isArray(data)) return [];
    return data.map(item => ({
      time: parseUTCDate(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      value: item.value,
    }));
  };

  const selectedDeviceData = devices.find(d => d.id === selectedDevice);

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
          <h1 className="text-2xl font-bold text-white">Metrics</h1>
          <p className="text-gray-400">Device performance monitoring</p>
        </div>
        <div className="flex items-center gap-4">
          <select
            value={selectedDevice || ''}
            onChange={(e) => setSelectedDevice(Number(e.target.value))}
            className="px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
          >
            {devices.map(device => (
              <option key={device.id} value={device.id}>
                {device.name}
              </option>
            ))}
          </select>
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(Number(e.target.value))}
            className="px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
          >
            <option value={1}>Last 1 hour</option>
            <option value={6}>Last 6 hours</option>
            <option value={24}>Last 24 hours</option>
            <option value={72}>Last 3 days</option>
            <option value={168}>Last 7 days</option>
          </select>
        </div>
      </div>

      {devices.length === 0 ? (
        <div className="bg-gray-800 rounded-lg p-12 text-center border border-gray-700">
          <Activity className="w-16 h-16 mx-auto text-gray-600 mb-4" />
          <h3 className="text-lg font-medium text-white mb-2">No devices to monitor</h3>
          <p className="text-gray-400">Add devices to start collecting metrics</p>
        </div>
      ) : (
        <>
          {/* Device Info */}
          {selectedDeviceData && (
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <div className="flex items-center gap-4">
                <div className={`w-3 h-3 rounded-full ${selectedDeviceData.is_reachable ? 'bg-green-500' : 'bg-red-500'}`} />
                <div>
                  <h3 className="font-semibold text-white">{selectedDeviceData.name}</h3>
                  <p className="text-sm text-gray-400">{selectedDeviceData.ip_address} - {selectedDeviceData.device_type}</p>
                </div>
              </div>
            </div>
          )}

          {/* Charts Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* CPU Chart */}
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <div className="flex items-center gap-2 mb-4">
                <Cpu className="w-5 h-5 text-blue-500" />
                <h3 className="font-semibold text-white">CPU Utilization</h3>
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={formatChartData(metricsData.cpu_utilization)}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="time" stroke="#9CA3AF" fontSize={12} />
                    <YAxis stroke="#9CA3AF" fontSize={12} domain={[0, 100]} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                      labelStyle={{ color: '#9CA3AF' }}
                    />
                    <Line type="monotone" dataKey="value" stroke="#3B82F6" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Memory Chart */}
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <div className="flex items-center gap-2 mb-4">
                <HardDrive className="w-5 h-5 text-green-500" />
                <h3 className="font-semibold text-white">Memory Utilization</h3>
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={formatChartData(metricsData.memory_utilization)}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="time" stroke="#9CA3AF" fontSize={12} />
                    <YAxis stroke="#9CA3AF" fontSize={12} domain={[0, 100]} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                      labelStyle={{ color: '#9CA3AF' }}
                    />
                    <Line type="monotone" dataKey="value" stroke="#10B981" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Latency Chart */}
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <div className="flex items-center gap-2 mb-4">
                <Clock className="w-5 h-5 text-yellow-500" />
                <h3 className="font-semibold text-white">Ping Latency (ms)</h3>
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={formatChartData(metricsData.ping_latency)}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="time" stroke="#9CA3AF" fontSize={12} />
                    <YAxis stroke="#9CA3AF" fontSize={12} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                      labelStyle={{ color: '#9CA3AF' }}
                    />
                    <Line type="monotone" dataKey="value" stroke="#F59E0B" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Packet Loss Chart */}
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <div className="flex items-center gap-2 mb-4">
                <Activity className="w-5 h-5 text-red-500" />
                <h3 className="font-semibold text-white">Packet Loss (%)</h3>
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={formatChartData(metricsData.ping_loss)}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="time" stroke="#9CA3AF" fontSize={12} />
                    <YAxis stroke="#9CA3AF" fontSize={12} domain={[0, 100]} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                      labelStyle={{ color: '#9CA3AF' }}
                    />
                    <Line type="monotone" dataKey="value" stroke="#EF4444" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
