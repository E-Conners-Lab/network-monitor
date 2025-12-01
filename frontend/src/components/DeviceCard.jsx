import { Link } from 'react-router-dom';
import { Server, Router, Shield, Wifi, Circle } from 'lucide-react';

const deviceIcons = {
  router: Router,
  switch: Server,
  firewall: Shield,
  access_point: Wifi,
  other: Server,
};

export default function DeviceCard({ device, onClick }) {
  const Icon = deviceIcons[device.device_type] || Server;
  const isReachable = device.is_reachable;

  return (
    <Link
      to={`/devices/${device.id}`}
      onClick={(e) => {
        if (onClick) {
          e.preventDefault();
          onClick(device);
        }
      }}
      className={`
        block p-4 rounded-lg border cursor-pointer transition-all
        ${isReachable
          ? 'bg-gray-800 border-gray-700 hover:border-green-500'
          : 'bg-red-900/20 border-red-700 hover:border-red-500'}
      `}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${isReachable ? 'bg-green-900/30' : 'bg-red-900/30'}`}>
            <Icon className={`w-6 h-6 ${isReachable ? 'text-green-500' : 'text-red-500'}`} />
          </div>
          <div>
            <h3 className="font-semibold text-white">{device.name}</h3>
            <p className="text-sm text-gray-400">{device.ip_address}</p>
          </div>
        </div>
        <Circle
          className={`w-3 h-3 ${isReachable ? 'text-green-500 fill-green-500' : 'text-red-500 fill-red-500'}`}
        />
      </div>

      <div className="mt-3 flex items-center gap-4 text-xs text-gray-400">
        <span className="capitalize">{device.device_type}</span>
        <span>{device.vendor}</span>
        {device.location && <span>{device.location}</span>}
      </div>

      {device.last_seen && (
        <p className="mt-2 text-xs text-gray-500">
          Last seen: {new Date(device.last_seen).toLocaleString()}
        </p>
      )}
    </Link>
  );
}
