import { useState, useEffect, useRef } from 'react';
import {
  PlayCircle,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  Zap,
  FileText,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { tests as testsApi } from '../services/api';
import { formatLocalDateTime } from '../utils/date';

const statusConfig = {
  passed: { icon: CheckCircle, color: 'text-green-500', bg: 'bg-green-900/30' },
  failed: { icon: XCircle, color: 'text-red-500', bg: 'bg-red-900/30' },
  skipped: { icon: AlertCircle, color: 'text-yellow-500', bg: 'bg-yellow-900/30' },
  error: { icon: AlertCircle, color: 'text-orange-500', bg: 'bg-orange-900/30' },
};

function TestResultItem({ result, expanded, onToggle }) {
  const config = statusConfig[result.status] || statusConfig.error;
  const StatusIcon = config.icon;

  return (
    <div className={`border rounded-lg ${config.bg} border-gray-700`}>
      <div
        className="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-800/50"
        onClick={onToggle}
      >
        <div className="flex items-center gap-3">
          {expanded ? (
            <ChevronDown className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-400" />
          )}
          <StatusIcon className={`w-5 h-5 ${config.color}`} />
          <div>
            <p className="text-white font-medium">{result.name}</p>
            <p className="text-sm text-gray-400">{result.message}</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {result.duration_ms > 0 && (
            <span className="text-xs text-gray-500">
              {result.duration_ms.toFixed(0)}ms
            </span>
          )}
          <span className={`px-2 py-1 rounded text-xs font-medium uppercase ${config.color} ${config.bg}`}>
            {result.status}
          </span>
        </div>
      </div>

      {expanded && result.details && Object.keys(result.details).length > 0 && (
        <div className="px-4 pb-3 border-t border-gray-700">
          <pre className="text-xs text-gray-300 mt-2 overflow-x-auto bg-gray-900 p-2 rounded">
            {JSON.stringify(result.details, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export default function Tests() {
  const [running, setRunning] = useState(false);
  const [taskId, setTaskId] = useState(null);
  const [testResult, setTestResult] = useState(null);
  const [expandedResults, setExpandedResults] = useState({});
  const [testType, setTestType] = useState('quick');
  const pollIntervalRef = useRef(null);

  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  const startTest = async (type) => {
    setTestType(type);
    setRunning(true);
    setTestResult(null);

    try {
      const response = type === 'quick'
        ? await testsApi.runQuick()
        : await testsApi.runFull();

      setTaskId(response.data.task_id);

      // Start polling for results
      pollIntervalRef.current = setInterval(async () => {
        try {
          const statusRes = await testsApi.getStatus(response.data.task_id);

          if (statusRes.data.status === 'completed') {
            setTestResult(statusRes.data.result);
            setRunning(false);
            clearInterval(pollIntervalRef.current);
          } else if (statusRes.data.status === 'failed') {
            setTestResult({ error: statusRes.data.result?.error || 'Test failed' });
            setRunning(false);
            clearInterval(pollIntervalRef.current);
          }
        } catch (err) {
          console.error('Failed to poll status:', err);
        }
      }, 2000);
    } catch (error) {
      console.error('Failed to start test:', error);
      setRunning(false);
    }
  };

  const toggleExpanded = (index) => {
    setExpandedResults(prev => ({
      ...prev,
      [index]: !prev[index],
    }));
  };

  const expandAll = () => {
    if (!testResult?.results) return;
    const expanded = {};
    testResult.results.forEach((_, index) => {
      expanded[index] = true;
    });
    setExpandedResults(expanded);
  };

  const collapseAll = () => {
    setExpandedResults({});
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Network Tests</h1>
          <p className="text-gray-400">Validate network health using pyATS</p>
        </div>
      </div>

      {/* Test Type Selection */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div
          className={`p-6 rounded-lg border cursor-pointer transition-all ${
            testType === 'quick' && !running
              ? 'border-blue-500 bg-blue-900/20'
              : 'border-gray-700 bg-gray-800 hover:border-gray-600'
          }`}
          onClick={() => !running && setTestType('quick')}
        >
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 bg-blue-900/50 rounded-lg">
              <Zap className="w-6 h-6 text-blue-400" />
            </div>
            <h3 className="text-lg font-semibold text-white">Quick Health Check</h3>
          </div>
          <p className="text-gray-400 text-sm mb-4">
            Fast validation of device connectivity, BGP, and OSPF neighbor states.
            Recommended for routine checks.
          </p>
          <ul className="text-sm text-gray-500 space-y-1">
            <li>- SSH connectivity to all devices</li>
            <li>- BGP neighbor validation</li>
            <li>- OSPF neighbor validation</li>
          </ul>
          <button
            onClick={(e) => { e.stopPropagation(); startTest('quick'); }}
            disabled={running}
            className="mt-4 w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50"
          >
            {running && testType === 'quick' ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Running...
              </>
            ) : (
              <>
                <PlayCircle className="w-4 h-4" />
                Run Quick Test
              </>
            )}
          </button>
        </div>

        <div
          className={`p-6 rounded-lg border cursor-pointer transition-all ${
            testType === 'full' && !running
              ? 'border-purple-500 bg-purple-900/20'
              : 'border-gray-700 bg-gray-800 hover:border-gray-600'
          }`}
          onClick={() => !running && setTestType('full')}
        >
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 bg-purple-900/50 rounded-lg">
              <FileText className="w-6 h-6 text-purple-400" />
            </div>
            <h3 className="text-lg font-semibold text-white">Full Validation</h3>
          </div>
          <p className="text-gray-400 text-sm mb-4">
            Comprehensive network validation including routing tables and
            end-to-end path verification.
          </p>
          <ul className="text-sm text-gray-500 space-y-1">
            <li>- All quick health checks</li>
            <li>- Interface status validation</li>
            <li>- Route table verification</li>
            <li>- End-to-end path testing</li>
          </ul>
          <button
            onClick={(e) => { e.stopPropagation(); startTest('full'); }}
            disabled={running}
            className="mt-4 w-full flex items-center justify-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg transition-colors disabled:opacity-50"
          >
            {running && testType === 'full' ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Running...
              </>
            ) : (
              <>
                <PlayCircle className="w-4 h-4" />
                Run Full Test
              </>
            )}
          </button>
        </div>
      </div>

      {/* Running Status */}
      {running && (
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center gap-3">
            <RefreshCw className="w-6 h-6 text-blue-500 animate-spin" />
            <div>
              <h3 className="text-lg font-semibold text-white">
                {testType === 'quick' ? 'Quick Health Check' : 'Full Validation'} Running...
              </h3>
              <p className="text-gray-400 text-sm">
                This may take several minutes depending on the number of devices.
              </p>
            </div>
          </div>
          {taskId && (
            <p className="mt-3 text-xs text-gray-500">Task ID: {taskId}</p>
          )}
        </div>
      )}

      {/* Test Results */}
      {testResult && !testResult.error && (
        <div className="bg-gray-800 rounded-lg border border-gray-700">
          {/* Summary Header */}
          <div className="p-6 border-b border-gray-700">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                {testResult.status === 'passed' ? (
                  <CheckCircle className="w-8 h-8 text-green-500" />
                ) : (
                  <XCircle className="w-8 h-8 text-red-500" />
                )}
                <div>
                  <h3 className="text-xl font-bold text-white">{testResult.suite_name}</h3>
                  <p className="text-gray-400 text-sm">
                    Completed {testResult.completed_at && formatLocalDateTime(testResult.completed_at)}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={expandAll}
                  className="px-3 py-1 text-sm bg-gray-700 hover:bg-gray-600 rounded transition-colors"
                >
                  Expand All
                </button>
                <button
                  onClick={collapseAll}
                  className="px-3 py-1 text-sm bg-gray-700 hover:bg-gray-600 rounded transition-colors"
                >
                  Collapse All
                </button>
              </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="text-center">
                <p className="text-2xl font-bold text-white">{testResult.total_tests}</p>
                <p className="text-sm text-gray-400">Total</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-green-500">{testResult.passed}</p>
                <p className="text-sm text-gray-400">Passed</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-red-500">{testResult.failed}</p>
                <p className="text-sm text-gray-400">Failed</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-yellow-500">{testResult.skipped}</p>
                <p className="text-sm text-gray-400">Skipped</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-blue-500">{testResult.success_rate?.toFixed(1)}%</p>
                <p className="text-sm text-gray-400">Success Rate</p>
              </div>
            </div>
          </div>

          {/* Results List */}
          <div className="p-6 space-y-2 max-h-[600px] overflow-y-auto">
            {testResult.results?.map((result, index) => (
              <TestResultItem
                key={index}
                result={result}
                expanded={expandedResults[index]}
                onToggle={() => toggleExpanded(index)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Error State */}
      {testResult?.error && (
        <div className="bg-red-900/20 rounded-lg p-6 border border-red-700">
          <div className="flex items-center gap-3">
            <XCircle className="w-6 h-6 text-red-500" />
            <div>
              <h3 className="text-lg font-semibold text-white">Test Failed</h3>
              <p className="text-gray-300">{testResult.error}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
