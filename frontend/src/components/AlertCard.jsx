import { AlertTriangle, AlertCircle, Info, CheckCircle, Clock } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

const severityConfig = {
  critical: {
    icon: AlertTriangle,
    bg: 'bg-red-900/30',
    border: 'border-red-700',
    text: 'text-red-500',
  },
  warning: {
    icon: AlertCircle,
    bg: 'bg-yellow-900/30',
    border: 'border-yellow-700',
    text: 'text-yellow-500',
  },
  info: {
    icon: Info,
    bg: 'bg-blue-900/30',
    border: 'border-blue-700',
    text: 'text-blue-500',
  },
};

const statusConfig = {
  active: { icon: AlertCircle, text: 'text-red-400' },
  acknowledged: { icon: Clock, text: 'text-yellow-400' },
  resolved: { icon: CheckCircle, text: 'text-green-400' },
};

export default function AlertCard({ alert, onAcknowledge, onResolve, onAutoRemediate }) {
  const severity = severityConfig[alert.severity] || severityConfig.info;
  const status = statusConfig[alert.status] || statusConfig.active;
  const SeverityIcon = severity.icon;
  const StatusIcon = status.icon;

  return (
    <div className={`p-4 rounded-lg border ${severity.bg} ${severity.border}`}>
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <SeverityIcon className={`w-5 h-5 mt-0.5 ${severity.text}`} />
          <div>
            <h3 className="font-semibold text-white">{alert.title}</h3>
            <p className="text-sm text-gray-300 mt-1">{alert.message}</p>
            <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
              <span className="flex items-center gap-1">
                <StatusIcon className={`w-3 h-3 ${status.text}`} />
                <span className="capitalize">{alert.status}</span>
              </span>
              <span>
                {formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <span className={`px-2 py-1 rounded text-xs font-medium uppercase ${severity.text} ${severity.bg}`}>
            {alert.severity}
          </span>
        </div>
      </div>

      {alert.status === 'active' && (
        <div className="mt-3 flex gap-2">
          <button
            onClick={() => onAcknowledge?.(alert.id)}
            className="px-3 py-1 text-xs bg-yellow-600 hover:bg-yellow-700 rounded transition-colors"
          >
            Acknowledge
          </button>
          <button
            onClick={() => onResolve?.(alert.id)}
            className="px-3 py-1 text-xs bg-green-600 hover:bg-green-700 rounded transition-colors"
          >
            Resolve
          </button>
          <button
            onClick={() => onAutoRemediate?.(alert.id)}
            className="px-3 py-1 text-xs bg-blue-600 hover:bg-blue-700 rounded transition-colors"
          >
            Auto-Remediate
          </button>
        </div>
      )}
    </div>
  );
}
