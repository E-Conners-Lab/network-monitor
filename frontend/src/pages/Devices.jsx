import { useState, useEffect } from 'react';
import {
  Server,
  Plus,
  RefreshCw,
  Search,
  Download,
  Play,
  X
} from 'lucide-react';
import { devices as devicesApi } from '../services/api';
import DeviceCard from '../components/DeviceCard';

export default function Devices() {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [checking, setChecking] = useState(false);
  const [syncing, setSyncing] = useState(false);

  const fetchDevices = async () => {
    try {
      const res = await devicesApi.list();
      setDevices(res.data);
    } catch (error) {
      console.error('Failed to fetch devices:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDevices();
  }, []);

  const handleCheckAll = async () => {
    setChecking(true);
    try {
      await devicesApi.checkAll();
      setTimeout(fetchDevices, 2000); // Wait for checks to complete
    } catch (error) {
      console.error('Failed to check devices:', error);
    } finally {
      setChecking(false);
    }
  };

  const handleSyncNetbox = async () => {
    setSyncing(true);
    try {
      await devicesApi.netboxSync();
      await fetchDevices();
    } catch (error) {
      console.error('Failed to sync NetBox:', error);
    } finally {
      setSyncing(false);
    }
  };

  const filteredDevices = devices.filter(device => {
    const matchesSearch = device.name.toLowerCase().includes(filter.toLowerCase()) ||
      device.ip_address.includes(filter);
    const matchesType = !typeFilter || device.device_type === typeFilter;
    return matchesSearch && matchesType;
  });

  const deviceTypes = [...new Set(devices.map(d => d.device_type))];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Devices</h1>
          <p className="text-gray-400">{devices.length} devices configured</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSyncNetbox}
            disabled={syncing}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg transition-colors disabled:opacity-50"
          >
            <Download className={`w-4 h-4 ${syncing ? 'animate-bounce' : ''}`} />
            Sync NetBox
          </button>
          <button
            onClick={handleCheckAll}
            disabled={checking}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg transition-colors disabled:opacity-50"
          >
            <Play className={`w-4 h-4 ${checking ? 'animate-pulse' : ''}`} />
            Check All
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Device
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search devices..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
          />
        </div>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
        >
          <option value="">All Types</option>
          {deviceTypes.map(type => (
            <option key={type} value={type} className="capitalize">
              {type}
            </option>
          ))}
        </select>
      </div>

      {/* Device Grid */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
        </div>
      ) : filteredDevices.length === 0 ? (
        <div className="bg-gray-800 rounded-lg p-12 text-center border border-gray-700">
          <Server className="w-16 h-16 mx-auto text-gray-600 mb-4" />
          <h3 className="text-lg font-medium text-white mb-2">No devices found</h3>
          <p className="text-gray-400 mb-4">
            {filter || typeFilter
              ? 'Try adjusting your filters'
              : 'Add devices manually or sync from NetBox'}
          </p>
          <div className="flex items-center justify-center gap-4">
            <button
              onClick={handleSyncNetbox}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg transition-colors"
            >
              Sync from NetBox
            </button>
            <button
              onClick={() => setShowAddModal(true)}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
            >
              Add Manually
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredDevices.map(device => (
            <DeviceCard key={device.id} device={device} />
          ))}
        </div>
      )}

      {/* Add Device Modal */}
      {showAddModal && (
        <AddDeviceModal
          onClose={() => setShowAddModal(false)}
          onAdded={fetchDevices}
        />
      )}
    </div>
  );
}

function AddDeviceModal({ onClose, onAdded }) {
  const [form, setForm] = useState({
    name: '',
    hostname: '',
    ip_address: '',
    device_type: 'router',
    vendor: 'cisco',
    snmp_community: 'public',
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError('');

    try {
      await devicesApi.create({
        ...form,
        hostname: form.hostname || form.name,
      });
      onAdded();
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create device');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-gray-800 rounded-lg p-6 w-full max-w-md border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Add Device</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-900/30 border border-red-700 rounded-lg text-red-400 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Name *</label>
            <input
              type="text"
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
              placeholder="e.g., core-router-01"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">IP Address *</label>
            <input
              type="text"
              required
              value={form.ip_address}
              onChange={(e) => setForm({ ...form, ip_address: e.target.value })}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
              placeholder="e.g., 192.168.1.1"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">Device Type</label>
            <select
              value={form.device_type}
              onChange={(e) => setForm({ ...form, device_type: e.target.value })}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
            >
              <option value="router">Router</option>
              <option value="switch">Switch</option>
              <option value="firewall">Firewall</option>
              <option value="access_point">Access Point</option>
              <option value="other">Other</option>
            </select>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">SNMP Community</label>
            <input
              type="text"
              value={form.snmp_community}
              onChange={(e) => setForm({ ...form, snmp_community: e.target.value })}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
              placeholder="public"
            />
          </div>

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50"
            >
              {submitting ? 'Creating...' : 'Create Device'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
