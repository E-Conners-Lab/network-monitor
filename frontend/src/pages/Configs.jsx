import { useState, useEffect } from 'react';
import {
  FileText,
  RefreshCw,
  Download,
  GitCompare,
  Clock,
  Server,
  Hash,
  ChevronDown,
  ChevronRight,
  X,
  Plus,
  Minus
} from 'lucide-react';
import { configs as configsApi, devices as devicesApi } from '../services/api';

export default function Configs() {
  const [backups, setBackups] = useState([]);
  const [devicesList, setDevicesList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [backingUp, setBackingUp] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState('');
  const [selectedBackup, setSelectedBackup] = useState(null);
  const [compareMode, setCompareMode] = useState(false);
  const [compareBackups, setCompareBackups] = useState([null, null]);
  const [diffResult, setDiffResult] = useState(null);
  const [showDiff, setShowDiff] = useState(false);

  const fetchBackups = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    const startTime = Date.now();
    try {
      const params = { limit: 100 };
      if (selectedDevice) params.device_id = selectedDevice;
      const res = await configsApi.list(params);
      setBackups(res.data);
    } catch (error) {
      console.error('Failed to fetch backups:', error);
    } finally {
      setLoading(false);
      if (isRefresh) {
        const elapsed = Date.now() - startTime;
        const remaining = Math.max(0, 500 - elapsed);
        setTimeout(() => setRefreshing(false), remaining);
      }
    }
  };

  const fetchDevices = async () => {
    try {
      const res = await devicesApi.list({ limit: 100 });
      setDevicesList(res.data);
    } catch (error) {
      console.error('Failed to fetch devices:', error);
    }
  };

  useEffect(() => {
    fetchDevices();
    fetchBackups();
  }, []);

  useEffect(() => {
    fetchBackups();
  }, [selectedDevice]);

  const handleBackupAll = async () => {
    setBackingUp(true);
    try {
      await configsApi.backupAll('manual');
      // Wait for backups to complete
      setTimeout(() => {
        fetchBackups(true);
        setBackingUp(false);
      }, 5000);
    } catch (error) {
      console.error('Failed to trigger backup:', error);
      setBackingUp(false);
    }
  };

  const handleViewConfig = async (backup) => {
    try {
      const res = await configsApi.get(backup.id);
      setSelectedBackup(res.data);
    } catch (error) {
      console.error('Failed to fetch config:', error);
    }
  };

  const handleSelectForCompare = (backup, index) => {
    const newCompare = [...compareBackups];
    newCompare[index] = backup;
    setCompareBackups(newCompare);
  };

  const handleCompare = async () => {
    if (!compareBackups[0] || !compareBackups[1]) return;
    try {
      const res = await configsApi.diff(compareBackups[0].id, compareBackups[1].id);
      setDiffResult(res.data);
      setShowDiff(true);
    } catch (error) {
      console.error('Failed to compare configs:', error);
    }
  };

  const getDeviceName = (deviceId) => {
    const device = devicesList.find(d => d.id === deviceId);
    return device ? device.name : `Device ${deviceId}`;
  };

  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleString();
  };

  const formatBytes = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Group backups by device
  const groupedBackups = backups.reduce((acc, backup) => {
    const deviceName = getDeviceName(backup.device_id);
    if (!acc[deviceName]) acc[deviceName] = [];
    acc[deviceName].push(backup);
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Config Backups</h1>
          <p className="text-gray-600 mt-1">
            View and compare device configuration history
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setCompareMode(!compareMode)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
              compareMode
                ? 'bg-purple-600 text-white'
                : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
            }`}
          >
            <GitCompare className="w-4 h-4" />
            {compareMode ? 'Exit Compare' : 'Compare'}
          </button>
          <button
            onClick={handleBackupAll}
            disabled={backingUp}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {backingUp ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            Backup All
          </button>
          <button
            onClick={() => fetchBackups(true)}
            disabled={refreshing}
            className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Server className="w-4 h-4 text-gray-500" />
            <select
              value={selectedDevice}
              onChange={(e) => setSelectedDevice(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
            >
              <option value="">All Devices</option>
              {devicesList.map(device => (
                <option key={device.id} value={device.id}>{device.name}</option>
              ))}
            </select>
          </div>
          <div className="text-sm text-gray-600">
            {backups.length} backup{backups.length !== 1 ? 's' : ''} found
          </div>
        </div>
      </div>

      {/* Compare Mode Selection */}
      {compareMode && (
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <div>
                <span className="text-sm text-purple-700 font-medium">Backup 1:</span>
                <span className="ml-2 text-sm">
                  {compareBackups[0] ? (
                    <span className="bg-purple-100 px-2 py-1 rounded">
                      {getDeviceName(compareBackups[0].device_id)} - {formatDate(compareBackups[0].created_at)}
                    </span>
                  ) : (
                    <span className="text-gray-500">Select a backup</span>
                  )}
                </span>
              </div>
              <div>
                <span className="text-sm text-purple-700 font-medium">Backup 2:</span>
                <span className="ml-2 text-sm">
                  {compareBackups[1] ? (
                    <span className="bg-purple-100 px-2 py-1 rounded">
                      {getDeviceName(compareBackups[1].device_id)} - {formatDate(compareBackups[1].created_at)}
                    </span>
                  ) : (
                    <span className="text-gray-500">Select a backup</span>
                  )}
                </span>
              </div>
            </div>
            <button
              onClick={handleCompare}
              disabled={!compareBackups[0] || !compareBackups[1]}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Compare
            </button>
          </div>
        </div>
      )}

      {/* Backups List */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
        </div>
      ) : backups.length === 0 ? (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
          <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900">No backups yet</h3>
          <p className="text-gray-600 mt-1">Click "Backup All" to create your first config backup</p>
        </div>
      ) : (
        <div className="space-y-4">
          {Object.entries(groupedBackups).map(([deviceName, deviceBackups]) => (
            <DeviceBackupGroup
              key={deviceName}
              deviceName={deviceName}
              backups={deviceBackups}
              onView={handleViewConfig}
              compareMode={compareMode}
              compareBackups={compareBackups}
              onSelectForCompare={handleSelectForCompare}
              formatDate={formatDate}
              formatBytes={formatBytes}
            />
          ))}
        </div>
      )}

      {/* Config Viewer Modal */}
      {selectedBackup && (
        <ConfigViewerModal
          backup={selectedBackup}
          deviceName={getDeviceName(selectedBackup.device_id)}
          onClose={() => setSelectedBackup(null)}
          formatDate={formatDate}
          formatBytes={formatBytes}
        />
      )}

      {/* Diff Viewer Modal */}
      {showDiff && diffResult && (
        <DiffViewerModal
          diff={diffResult}
          getDeviceName={getDeviceName}
          onClose={() => {
            setShowDiff(false);
            setDiffResult(null);
          }}
          formatDate={formatDate}
        />
      )}
    </div>
  );
}

function DeviceBackupGroup({ deviceName, backups, onView, compareMode, compareBackups, onSelectForCompare, formatDate, formatBytes }) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-gray-50"
      >
        <div className="flex items-center gap-3">
          {expanded ? <ChevronDown className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
          <Server className="w-5 h-5 text-blue-600" />
          <span className="font-medium">{deviceName}</span>
          <span className="text-sm text-gray-500">({backups.length} backup{backups.length !== 1 ? 's' : ''})</span>
        </div>
      </button>
      {expanded && (
        <div className="border-t border-gray-200">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                {compareMode && <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Select</th>}
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Date</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Size</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Lines</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Hash</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Triggered By</th>
                <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {backups.map((backup) => (
                <tr key={backup.id} className="hover:bg-gray-50">
                  {compareMode && (
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <button
                          onClick={() => onSelectForCompare(backup, 0)}
                          className={`px-2 py-1 text-xs rounded ${
                            compareBackups[0]?.id === backup.id
                              ? 'bg-purple-600 text-white'
                              : 'bg-gray-100 hover:bg-gray-200'
                          }`}
                        >
                          1
                        </button>
                        <button
                          onClick={() => onSelectForCompare(backup, 1)}
                          className={`px-2 py-1 text-xs rounded ${
                            compareBackups[1]?.id === backup.id
                              ? 'bg-purple-600 text-white'
                              : 'bg-gray-100 hover:bg-gray-200'
                          }`}
                        >
                          2
                        </button>
                      </div>
                    </td>
                  )}
                  <td className="px-4 py-3 text-sm">
                    <div className="flex items-center gap-2">
                      <Clock className="w-4 h-4 text-gray-400" />
                      {formatDate(backup.created_at)}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{formatBytes(backup.config_size)}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{backup.line_count}</td>
                  <td className="px-4 py-3">
                    <code className="text-xs bg-gray-100 px-2 py-1 rounded font-mono">
                      {backup.config_hash.substring(0, 12)}...
                    </code>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{backup.triggered_by || 'N/A'}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => onView(backup)}
                      className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ConfigViewerModal({ backup, deviceName, onClose, formatDate, formatBytes }) {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-5xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <div>
            <h2 className="text-lg font-semibold">{deviceName} - Configuration</h2>
            <p className="text-sm text-gray-600">
              {formatDate(backup.created_at)} | {formatBytes(backup.config_size)} | {backup.line_count} lines
            </p>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 overflow-auto p-4 bg-gray-900">
          <pre className="text-sm text-green-400 font-mono whitespace-pre-wrap">
            {backup.config_text}
          </pre>
        </div>
      </div>
    </div>
  );
}

function DiffViewerModal({ diff, getDeviceName, onClose, formatDate }) {
  const lines = diff.diff_text.split('\n');

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-6xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <div>
            <h2 className="text-lg font-semibold">Configuration Diff</h2>
            <p className="text-sm text-gray-600">
              {getDeviceName(diff.backup_1.device_id)}: {formatDate(diff.backup_1.created_at)} vs {formatDate(diff.backup_2.created_at)}
            </p>
            <div className="flex items-center gap-4 mt-2">
              <span className="flex items-center gap-1 text-sm">
                <Plus className="w-4 h-4 text-green-600" />
                <span className="text-green-600">{diff.added_lines} added</span>
              </span>
              <span className="flex items-center gap-1 text-sm">
                <Minus className="w-4 h-4 text-red-600" />
                <span className="text-red-600">{diff.removed_lines} removed</span>
              </span>
              {!diff.has_changes && (
                <span className="text-gray-600 text-sm">No changes detected</span>
              )}
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 overflow-auto p-4 bg-gray-900">
          <pre className="text-sm font-mono">
            {lines.map((line, i) => {
              let className = 'text-gray-400';
              if (line.startsWith('+') && !line.startsWith('+++')) {
                className = 'text-green-400 bg-green-900 bg-opacity-30';
              } else if (line.startsWith('-') && !line.startsWith('---')) {
                className = 'text-red-400 bg-red-900 bg-opacity-30';
              } else if (line.startsWith('@@')) {
                className = 'text-blue-400';
              }
              return (
                <div key={i} className={className}>
                  {line}
                </div>
              );
            })}
          </pre>
        </div>
      </div>
    </div>
  );
}
