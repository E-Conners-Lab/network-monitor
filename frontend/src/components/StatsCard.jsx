export default function StatsCard({ title, value, subtitle, icon: Icon, color = 'blue' }) {
  const colors = {
    blue: 'bg-blue-900/30 text-blue-500',
    green: 'bg-green-900/30 text-green-500',
    yellow: 'bg-yellow-900/30 text-yellow-500',
    red: 'bg-red-900/30 text-red-500',
    purple: 'bg-purple-900/30 text-purple-500',
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-400">{title}</p>
          <p className="text-2xl font-bold text-white mt-1">{value}</p>
          {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
        </div>
        {Icon && (
          <div className={`p-3 rounded-lg ${colors[color]}`}>
            <Icon className="w-6 h-6" />
          </div>
        )}
      </div>
    </div>
  );
}
