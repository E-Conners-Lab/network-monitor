import { useState, useEffect } from 'react';
import {
  Wrench,
  RefreshCw,
  Play,
  CheckCircle,
  XCircle,
  Clock,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { devices as devicesApi, remediation as remediationApi } from '../services/api';
import { parseUTCDate } from '../utils/date';

export default function Remediation() {
  const [devices, setDevices] = useState([]);
  const [playbooks, setPlaybooks] = useState([]);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState('');
  const [selectedPlaybook, setSelectedPlaybook] = useState('');
  const [executing, setExecuting] = useState(false);
  const [expandedLog, setExpandedLog] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [devicesRes, playbooksRes, logsRes] = await Promise.all([
          devicesApi.list(),
          remediationApi.playbooks(),
          remediationApi.logs({ limit: 50 }),
        ]);
        setDevices(devicesRes.data);
        setPlaybooks(playbooksRes.data);
        setLogs(logsRes.data);
      } catch (error) {
        console.error('Failed to fetch data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const fetchLogs = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    const startTime = Date.now();
    try {
      const res = await remediationApi.logs({ limit: 50 });
      setLogs(res.data);
    } catch (error) {
      console.error('Failed to fetch logs:', error);
    } finally {
      if (isRefresh) {
        const elapsed = Date.now() - startTime;
        const remaining = Math.max(0, 500 - elapsed);
        setTimeout(() => setRefreshing(false), remaining);
      }
    }
  };

  const handleExecute = async () => {
    if (!selectedDevice || !selectedPlaybook) return;

    setExecuting(true);
    try {
      await remediationApi.execute(selectedDevice, selectedPlaybook);
      // Wait and refresh logs
      setTimeout(fetchLogs, 3000);
    } catch (error) {
      console.error('Failed to execute playbook:', error);
    } finally {
      setExecuting(false);
    }
  };

  const statusConfig = {
    pending: { icon: Clock, color: 'text-gray-400', bg: 'bg-gray-700' },
    in_progress: { icon: RefreshCw, color: 'text-blue-400', bg: 'bg-blue-900/30' },
    success: { icon: CheckCircle, color: 'text-green-400', bg: 'bg-green-900/30' },
    failed: { icon: XCircle, color: 'text-red-400', bg: 'bg-red-900/30' },
    skipped: { icon: Clock, color: 'text-yellow-400', bg: 'bg-yellow-900/30' },
  };

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
          <h1 className="text-2xl font-bold text-white">Remediation</h1>
          <p className="text-gray-400">Execute playbooks and view remediation history</p>
        </div>
        <button
          onClick={() => fetchLogs(true)}
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

      {/* Execute Playbook */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-lg font-semibold text-white mb-4">Execute Playbook</h2>
        <div className="flex items-end gap-4">
          <div className="flex-1">
            <label className="block text-sm text-gray-400 mb-2">Device</label>
            <select
              value={selectedDevice}
              onChange={(e) => setSelectedDevice(e.target.value)}
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
            >
              <option value="">Select a device...</option>
              {devices.map(device => (
                <option key={device.id} value={device.id}>
                  {device.name} ({device.ip_address})
                </option>
              ))}
            </select>
          </div>
          <div className="flex-1">
            <label className="block text-sm text-gray-400 mb-2">Playbook</label>
            <select
              value={selectedPlaybook}
              onChange={(e) => setSelectedPlaybook(e.target.value)}
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
            >
              <option value="">Select a playbook...</option>
              {playbooks.map(pb => (
                <option key={pb.name} value={pb.name}>
                  {pb.name} - {pb.description}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={handleExecute}
            disabled={!selectedDevice || !selectedPlaybook || executing}
            className="flex items-center gap-2 px-6 py-2 bg-green-600 hover:bg-green-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Play className={`w-4 h-4 ${executing ? 'animate-pulse' : ''}`} />
            {executing ? 'Executing...' : 'Execute'}
          </button>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-lg font-semibold text-white mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <QuickAction
            title="Clear Caches"
            description="Clear ARP and routing caches"
            devices={devices}
            onExecute={async (deviceId) => {
              await remediationApi.clearCaches(deviceId);
              setTimeout(fetchLogs, 2000);
            }}
          />
          <QuickAction
            title="Enable Interface"
            description="Re-enable a disabled interface"
            devices={devices}
            needsInput
            inputLabel="Interface Name"
            inputPlaceholder="e.g., GigabitEthernet0/1"
            onExecute={async (deviceId, input) => {
              await remediationApi.enableInterface(deviceId, input);
              setTimeout(fetchLogs, 2000);
            }}
          />
          <QuickAction
            title="Clear BGP"
            description="Soft reset BGP session"
            devices={devices}
            needsInput
            inputLabel="Neighbor IP"
            inputPlaceholder="e.g., 192.168.1.2"
            onExecute={async (deviceId, input) => {
              await remediationApi.clearBgp(deviceId, input);
              setTimeout(fetchLogs, 2000);
            }}
          />
        </div>
      </div>

      {/* Remediation Logs */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Remediation History</h2>
        {logs.length === 0 ? (
          <div className="bg-gray-800 rounded-lg p-8 text-center border border-gray-700">
            <Wrench className="w-12 h-12 mx-auto text-gray-600 mb-3" />
            <p className="text-gray-400">No remediation actions yet</p>
          </div>
        ) : (
          <div className="space-y-2">
            {logs.map(log => {
              const status = statusConfig[log.status] || statusConfig.pending;
              const StatusIcon = status.icon;
              const isExpanded = expandedLog === log.id;
              const device = devices.find(d => d.id === log.device_id);

              return (
                <div
                  key={log.id}
                  className={`bg-gray-800 rounded-lg border border-gray-700 overflow-hidden`}
                >
                  <div
                    className="p-4 flex items-center justify-between cursor-pointer hover:bg-gray-750"
                    onClick={() => setExpandedLog(isExpanded ? null : log.id)}
                  >
                    <div className="flex items-center gap-4">
                      <div className={`p-2 rounded-lg ${status.bg}`}>
                        <StatusIcon className={`w-4 h-4 ${status.color} ${log.status === 'in_progress' ? 'animate-spin' : ''}`} />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-white">{log.playbook_name}</span>
                          <span className="text-sm text-gray-400">on {device?.name || `Device #${log.device_id}`}</span>
                        </div>
                        <div className="text-sm text-gray-500">
                          {formatDistanceToNow(parseUTCDate(log.created_at), { addSuffix: true })}
                          {log.duration_ms && ` • ${log.duration_ms}ms`}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className={`px-2 py-1 rounded text-xs ${status.bg} ${status.color}`}>
                        {log.status}
                      </span>
                      {isExpanded ? (
                        <ChevronUp className="w-4 h-4 text-gray-400" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-gray-400" />
                      )}
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="px-4 pb-4 border-t border-gray-700 pt-4">
                      {log.commands_executed && (
                        <div className="mb-3">
                          <p className="text-sm text-gray-400 mb-1">Commands:</p>
                          <pre className="text-xs bg-gray-900 p-2 rounded text-green-400 overflow-x-auto">
                            {log.commands_executed.join('\n')}
                          </pre>
                        </div>
                      )}
                      {log.error_message && (
                        <div>
                          <p className="text-sm text-gray-400 mb-1">Error:</p>
                          <pre className="text-xs bg-red-900/20 p-2 rounded text-red-400 overflow-x-auto">
                            {log.error_message}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function QuickAction({ title, description, devices, onExecute, needsInput, inputLabel, inputPlaceholder }) {
  const [deviceId, setDeviceId] = useState('');
  const [input, setInput] = useState('');
  const [executing, setExecuting] = useState(false);

  const handleExecute = async () => {
    if (!deviceId || (needsInput && !input)) return;
    setExecuting(true);
    try {
      await onExecute(deviceId, input);
    } catch (error) {
      console.error('Quick action failed:', error);
    } finally {
      setExecuting(false);
    }
  };

  return (
    <div className="bg-gray-700/50 rounded-lg p-4">
      <h3 className="font-medium text-white">{title}</h3>
      <p className="text-sm text-gray-400 mb-3">{description}</p>
      <div className="space-y-2">
        <select
          value={deviceId}
          onChange={(e) => setDeviceId(e.target.value)}
          className="w-full px-3 py-1.5 text-sm bg-gray-700 border border-gray-600 rounded text-white focus:outline-none focus:border-blue-500"
        >
          <option value="">Select device...</option>
          {devices.map(d => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </select>
        {needsInput && (
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={inputPlaceholder}
            className="w-full px-3 py-1.5 text-sm bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
          />
        )}
        <button
          onClick={handleExecute}
          disabled={!deviceId || (needsInput && !input) || executing}
          className="w-full px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 rounded transition-colors disabled:opacity-50"
        >
          {executing ? 'Running...' : 'Run'}
        </button>
      </div>
    </div>
  );
}
