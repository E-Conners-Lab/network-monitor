import { useState, useEffect, useRef, useCallback } from 'react';
import * as d3 from 'd3';
import { RefreshCw, ZoomIn, ZoomOut, Maximize2, Info } from 'lucide-react';
import { devices } from '../services/api';

// E-University Network Topology Definition
// Based on the actual lab topology with EDGE naming convention
const TOPOLOGY_DATA = {
  nodes: [
    // Core Layer
    { id: 'EUNIV-CORE1', label: 'CORE1', type: 'core', layer: 'core', x: 300, y: 100 },
    { id: 'EUNIV-CORE2', label: 'CORE2', type: 'core', layer: 'core', x: 500, y: 100 },
    { id: 'EUNIV-CORE3', label: 'CORE3', type: 'core', layer: 'core', x: 400, y: 50 },
    { id: 'EUNIV-CORE4', label: 'CORE4', type: 'core', layer: 'core', x: 250, y: 50 },
    { id: 'EUNIV-CORE5', label: 'CORE5', type: 'core', layer: 'core', x: 550, y: 50 },

    // Internet Gateways
    { id: 'EUNIV-INET-GW1', label: 'INET-GW1', type: 'gateway', layer: 'edge', x: 300, y: -50 },
    { id: 'EUNIV-INET-GW2', label: 'INET-GW2', type: 'gateway', layer: 'edge', x: 500, y: -50 },

    // Main Campus
    { id: 'EUNIV-MAIN-AGG1', label: 'MAIN-AGG1', type: 'aggregation', layer: 'aggregation', x: 100, y: 200 },
    { id: 'EUNIV-MAIN-EDGE1', label: 'MAIN-EDGE1', type: 'edge', layer: 'access', x: 50, y: 320 },
    { id: 'EUNIV-MAIN-EDGE2', label: 'MAIN-EDGE2', type: 'edge', layer: 'access', x: 150, y: 320 },

    // Medical Campus
    { id: 'EUNIV-MED-AGG1', label: 'MED-AGG1', type: 'aggregation', layer: 'aggregation', x: 400, y: 200 },
    { id: 'EUNIV-MED-EDGE1', label: 'MED-EDGE1', type: 'edge', layer: 'access', x: 350, y: 320 },
    { id: 'EUNIV-MED-EDGE2', label: 'MED-EDGE2', type: 'edge', layer: 'access', x: 450, y: 320 },

    // Research Campus
    { id: 'EUNIV-RES-AGG1', label: 'RES-AGG1', type: 'aggregation', layer: 'aggregation', x: 700, y: 200 },
    { id: 'EUNIV-RES-EDGE1', label: 'RES-EDGE1', type: 'edge', layer: 'access', x: 650, y: 320 },
    { id: 'EUNIV-RES-EDGE2', label: 'RES-EDGE2', type: 'edge', layer: 'access', x: 750, y: 320 },
  ],
  links: [
    // Core mesh (full mesh between CORE1-5)
    { source: 'EUNIV-CORE1', target: 'EUNIV-CORE2', type: 'core', protocol: 'OSPF/MPLS' },
    { source: 'EUNIV-CORE1', target: 'EUNIV-CORE3', type: 'core', protocol: 'OSPF/MPLS' },
    { source: 'EUNIV-CORE1', target: 'EUNIV-CORE4', type: 'core', protocol: 'OSPF/MPLS' },
    { source: 'EUNIV-CORE2', target: 'EUNIV-CORE3', type: 'core', protocol: 'OSPF/MPLS' },
    { source: 'EUNIV-CORE2', target: 'EUNIV-CORE5', type: 'core', protocol: 'OSPF/MPLS' },
    { source: 'EUNIV-CORE3', target: 'EUNIV-CORE4', type: 'core', protocol: 'OSPF/MPLS' },
    { source: 'EUNIV-CORE3', target: 'EUNIV-CORE5', type: 'core', protocol: 'OSPF/MPLS' },

    // Internet Gateway connections (with BFD)
    { source: 'EUNIV-CORE1', target: 'EUNIV-INET-GW1', type: 'uplink', protocol: 'OSPF/BFD' },
    { source: 'EUNIV-CORE2', target: 'EUNIV-INET-GW2', type: 'uplink', protocol: 'OSPF/BFD' },

    // Aggregation to Core
    { source: 'EUNIV-CORE1', target: 'EUNIV-MAIN-AGG1', type: 'distribution', protocol: 'OSPF/MPLS' },
    { source: 'EUNIV-CORE2', target: 'EUNIV-MAIN-AGG1', type: 'distribution', protocol: 'OSPF/MPLS' },
    { source: 'EUNIV-CORE3', target: 'EUNIV-MED-AGG1', type: 'distribution', protocol: 'OSPF/MPLS' },
    { source: 'EUNIV-CORE4', target: 'EUNIV-MED-AGG1', type: 'distribution', protocol: 'OSPF/MPLS' },
    { source: 'EUNIV-CORE3', target: 'EUNIV-RES-AGG1', type: 'distribution', protocol: 'OSPF/MPLS' },
    { source: 'EUNIV-CORE5', target: 'EUNIV-RES-AGG1', type: 'distribution', protocol: 'OSPF/MPLS' },

    // Edge to Aggregation (with BFD)
    { source: 'EUNIV-MAIN-AGG1', target: 'EUNIV-MAIN-EDGE1', type: 'access', protocol: 'OSPF/BFD' },
    { source: 'EUNIV-MAIN-AGG1', target: 'EUNIV-MAIN-EDGE2', type: 'access', protocol: 'OSPF/BFD' },
    { source: 'EUNIV-MED-AGG1', target: 'EUNIV-MED-EDGE1', type: 'access', protocol: 'OSPF/BFD' },
    { source: 'EUNIV-MED-AGG1', target: 'EUNIV-MED-EDGE2', type: 'access', protocol: 'OSPF/BFD' },
    { source: 'EUNIV-RES-AGG1', target: 'EUNIV-RES-EDGE1', type: 'access', protocol: 'OSPF/BFD' },
    { source: 'EUNIV-RES-AGG1', target: 'EUNIV-RES-EDGE2', type: 'access', protocol: 'OSPF/BFD' },

    // HA links between Edge pairs (HSRP)
    { source: 'EUNIV-MAIN-EDGE1', target: 'EUNIV-MAIN-EDGE2', type: 'ha', protocol: 'HSRP' },
    { source: 'EUNIV-MED-EDGE1', target: 'EUNIV-MED-EDGE2', type: 'ha', protocol: 'HSRP' },
    { source: 'EUNIV-RES-EDGE1', target: 'EUNIV-RES-EDGE2', type: 'ha', protocol: 'HSRP' },
  ]
};

// Node colors by type
const NODE_COLORS = {
  core: { fill: '#3b82f6', stroke: '#1d4ed8' },      // Blue
  gateway: { fill: '#8b5cf6', stroke: '#6d28d9' },   // Purple
  aggregation: { fill: '#f59e0b', stroke: '#d97706' }, // Amber
  edge: { fill: '#10b981', stroke: '#059669' },      // Green
};

// Link colors by type
const LINK_COLORS = {
  core: '#6b7280',        // Gray
  uplink: '#8b5cf6',      // Purple
  distribution: '#3b82f6', // Blue
  access: '#10b981',      // Green
  ha: '#ef4444',          // Red (dashed)
};

export default function Topology() {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const [deviceStatus, setDeviceStatus] = useState({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedNode, setSelectedNode] = useState(null);
  const [transform, setTransform] = useState({ k: 1, x: 0, y: 0 });

  // Fetch device status from API
  const fetchDeviceStatus = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    const startTime = Date.now();
    try {
      const response = await devices.list();
      const statusMap = {};
      response.data.forEach(device => {
        statusMap[device.name] = {
          id: device.id,  // Include the numeric ID for linking
          is_reachable: device.is_reachable,
          ip_address: device.ip_address,
          device_type: device.device_type,
          last_seen: device.last_seen,
        };
      });
      setDeviceStatus(statusMap);
    } catch (error) {
      console.error('Failed to fetch device status:', error);
    } finally {
      setLoading(false);
      if (isRefresh) {
        const elapsed = Date.now() - startTime;
        const remaining = Math.max(0, 500 - elapsed);
        setTimeout(() => setRefreshing(false), remaining);
      }
    }
  }, []);

  useEffect(() => {
    fetchDeviceStatus();
    const interval = setInterval(fetchDeviceStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchDeviceStatus]);

  // Initialize D3 visualization
  useEffect(() => {
    if (!svgRef.current || loading) return;

    const svg = d3.select(svgRef.current);
    const container = containerRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight;

    // Clear previous content
    svg.selectAll('*').remove();

    // Create main group for zoom/pan
    const g = svg.append('g').attr('class', 'topology-main');

    // Add zoom behavior
    const zoom = d3.zoom()
      .scaleExtent([0.3, 3])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
        setTransform(event.transform);
      });

    svg.call(zoom);

    // Center the topology - calculate to fit all nodes
    // Topology spans x: 0-800, y: -80 to 380 (total height ~460)
    const topoWidth = 850;
    const topoHeight = 480;
    const scale = Math.min(width / topoWidth, height / topoHeight, 1) * 0.85;
    const xOffset = (width - topoWidth * scale) / 2;
    const yOffset = (height - topoHeight * scale) / 2 + 80 * scale; // Offset for negative y values

    const initialTransform = d3.zoomIdentity
      .translate(xOffset, yOffset)
      .scale(scale);
    svg.call(zoom.transform, initialTransform);

    // Draw layer backgrounds
    const layers = [
      { y: -80, height: 80, label: 'Internet', color: 'rgba(139, 92, 246, 0.1)' },
      { y: 20, height: 100, label: 'Core', color: 'rgba(59, 130, 246, 0.1)' },
      { y: 160, height: 80, label: 'Aggregation', color: 'rgba(245, 158, 11, 0.1)' },
      { y: 280, height: 100, label: 'Access/Edge', color: 'rgba(16, 185, 129, 0.1)' },
    ];

    const layerGroup = g.append('g').attr('class', 'layers');
    layers.forEach(layer => {
      layerGroup.append('rect')
        .attr('x', -50)
        .attr('y', layer.y)
        .attr('width', 900)
        .attr('height', layer.height)
        .attr('fill', layer.color)
        .attr('rx', 8);

      layerGroup.append('text')
        .attr('x', -40)
        .attr('y', layer.y + 20)
        .attr('fill', '#9ca3af')
        .attr('font-size', '12px')
        .attr('font-weight', '500')
        .text(layer.label);
    });

    // Create arrow marker for directed links
    svg.append('defs').append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '-0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('orient', 'auto')
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .append('path')
      .attr('d', 'M 0,-5 L 10,0 L 0,5')
      .attr('fill', '#6b7280');

    // Draw links
    const linkGroup = g.append('g').attr('class', 'links');

    TOPOLOGY_DATA.links.forEach(link => {
      const source = TOPOLOGY_DATA.nodes.find(n => n.id === link.source);
      const target = TOPOLOGY_DATA.nodes.find(n => n.id === link.target);

      if (!source || !target) return;

      const linkColor = LINK_COLORS[link.type] || '#6b7280';
      const isHA = link.type === 'ha';

      // Check if both ends are reachable
      const sourceStatus = deviceStatus[source.id];
      const targetStatus = deviceStatus[target.id];
      const linkUp = sourceStatus?.is_reachable && targetStatus?.is_reachable;

      const linkElement = linkGroup.append('line')
        .attr('x1', source.x)
        .attr('y1', source.y)
        .attr('x2', target.x)
        .attr('y2', target.y)
        .attr('stroke', linkUp ? linkColor : '#ef4444')
        .attr('stroke-width', isHA ? 2 : 3)
        .attr('stroke-dasharray', isHA ? '5,5' : 'none')
        .attr('opacity', linkUp ? 0.8 : 0.4)
        .attr('class', 'topology-link')
        .style('cursor', 'pointer');

      // Add hover effect and tooltip
      linkElement
        .on('mouseover', function(event) {
          d3.select(this)
            .attr('stroke-width', isHA ? 4 : 5)
            .attr('opacity', 1);

          // Show tooltip
          const tooltip = d3.select('#link-tooltip');
          tooltip.style('display', 'block')
            .style('left', (event.pageX + 10) + 'px')
            .style('top', (event.pageY - 10) + 'px')
            .html(`
              <div class="font-semibold">${source.label} ↔ ${target.label}</div>
              <div class="text-sm text-gray-400">${link.protocol}</div>
              <div class="text-sm ${linkUp ? 'text-green-400' : 'text-red-400'}">
                ${linkUp ? 'Link Up' : 'Link Down'}
              </div>
            `);
        })
        .on('mouseout', function() {
          d3.select(this)
            .attr('stroke-width', isHA ? 2 : 3)
            .attr('opacity', linkUp ? 0.8 : 0.4);
          d3.select('#link-tooltip').style('display', 'none');
        });
    });

    // Draw nodes
    const nodeGroup = g.append('g').attr('class', 'nodes');

    TOPOLOGY_DATA.nodes.forEach(node => {
      const colors = NODE_COLORS[node.type] || NODE_COLORS.edge;
      const status = deviceStatus[node.id];
      const isReachable = status?.is_reachable ?? false;

      const nodeG = nodeGroup.append('g')
        .attr('transform', `translate(${node.x}, ${node.y})`)
        .attr('class', 'topology-node')
        .style('cursor', 'pointer');

      // Node circle
      nodeG.append('circle')
        .attr('r', 25)
        .attr('fill', isReachable ? colors.fill : '#374151')
        .attr('stroke', isReachable ? colors.stroke : '#ef4444')
        .attr('stroke-width', 3)
        .attr('class', 'node-circle');

      // Status indicator
      nodeG.append('circle')
        .attr('cx', 18)
        .attr('cy', -18)
        .attr('r', 6)
        .attr('fill', isReachable ? '#10b981' : '#ef4444')
        .attr('stroke', '#1f2937')
        .attr('stroke-width', 2);

      // Node label
      nodeG.append('text')
        .attr('y', 45)
        .attr('text-anchor', 'middle')
        .attr('fill', '#e5e7eb')
        .attr('font-size', '11px')
        .attr('font-weight', '600')
        .text(node.label);

      // Icon/letter inside node
      nodeG.append('text')
        .attr('y', 5)
        .attr('text-anchor', 'middle')
        .attr('fill', '#ffffff')
        .attr('font-size', '12px')
        .attr('font-weight', 'bold')
        .text(node.type === 'core' ? 'C' :
              node.type === 'gateway' ? 'GW' :
              node.type === 'aggregation' ? 'A' : 'E');

      // Hover and click effects
      nodeG
        .on('mouseover', function(event) {
          d3.select(this).select('.node-circle')
            .transition()
            .duration(200)
            .attr('r', 30);

          // Show tooltip
          const tooltip = d3.select('#node-tooltip');
          tooltip.style('display', 'block')
            .style('left', (event.pageX + 15) + 'px')
            .style('top', (event.pageY - 10) + 'px')
            .html(`
              <div class="font-semibold text-base">${node.label}</div>
              <div class="text-xs text-gray-400 mb-1">${node.id}</div>
              <div class="text-sm">Type: <span class="capitalize">${node.type}</span></div>
              ${status ? `
                <div class="text-sm">IP: <span class="font-mono">${status.ip_address || 'N/A'}</span></div>
                <div class="text-sm ${isReachable ? 'text-green-400' : 'text-red-400'}">
                  Status: ${isReachable ? 'Online' : 'Offline'}
                </div>
              ` : '<div class="text-sm text-gray-500">Not in database</div>'}
            `);
        })
        .on('mousemove', function(event) {
          d3.select('#node-tooltip')
            .style('left', (event.pageX + 15) + 'px')
            .style('top', (event.pageY - 10) + 'px');
        })
        .on('mouseout', function() {
          d3.select(this).select('.node-circle')
            .transition()
            .duration(200)
            .attr('r', 25);
          d3.select('#node-tooltip').style('display', 'none');
        })
        .on('click', () => {
          d3.select('#node-tooltip').style('display', 'none');
          setSelectedNode({
            ...node,
            status: status,
          });
        });
    });

  }, [deviceStatus, loading]);

  // Zoom controls
  const handleZoom = (direction) => {
    const svg = d3.select(svgRef.current);
    const zoom = d3.zoom().scaleExtent([0.3, 3]);

    if (direction === 'in') {
      svg.transition().call(zoom.scaleBy, 1.3);
    } else if (direction === 'out') {
      svg.transition().call(zoom.scaleBy, 0.7);
    } else if (direction === 'reset') {
      const container = containerRef.current;
      const width = container.clientWidth;
      const height = container.clientHeight;
      const topoWidth = 850;
      const topoHeight = 480;
      const scale = Math.min(width / topoWidth, height / topoHeight, 1) * 0.85;
      const xOffset = (width - topoWidth * scale) / 2;
      const yOffset = (height - topoHeight * scale) / 2 + 80 * scale;
      const resetTransform = d3.zoomIdentity
        .translate(xOffset, yOffset)
        .scale(scale);
      svg.transition().call(zoom.transform, resetTransform);
    }
  };

  // Count device statuses
  const onlineCount = Object.values(deviceStatus).filter(d => d.is_reachable).length;
  const offlineCount = Object.values(deviceStatus).filter(d => !d.is_reachable).length;
  const totalDevices = TOPOLOGY_DATA.nodes.length;

  return (
    <div className="flex flex-col" style={{ height: 'calc(100vh - 48px)' }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-white">Network Topology</h1>
          <p className="text-gray-400 text-sm">E-University MPLS/VPN Network</p>
        </div>

        <div className="flex items-center gap-4">
          {/* Status summary */}
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-green-500"></span>
              <span className="text-gray-300">{onlineCount} Online</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-red-500"></span>
              <span className="text-gray-300">{offlineCount} Offline</span>
            </div>
            <div className="text-gray-500">|</div>
            <span className="text-gray-400">{totalDevices} Total Devices</span>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => handleZoom('out')}
              className="p-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
              title="Zoom Out"
            >
              <ZoomOut className="w-4 h-4 text-gray-300" />
            </button>
            <button
              onClick={() => handleZoom('in')}
              className="p-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
              title="Zoom In"
            >
              <ZoomIn className="w-4 h-4 text-gray-300" />
            </button>
            <button
              onClick={() => handleZoom('reset')}
              className="p-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
              title="Reset View"
            >
              <Maximize2 className="w-4 h-4 text-gray-300" />
            </button>
            <button
              onClick={() => fetchDeviceStatus(true)}
              disabled={refreshing}
              className={`p-2 rounded-lg transition-colors ${refreshing ? 'bg-gray-600' : 'bg-gray-700 hover:bg-gray-600'}`}
              title="Refresh Status"
            >
              <RefreshCw className={`w-4 h-4 text-gray-300 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-6 mb-4 text-sm flex-shrink-0">
        <div className="flex items-center gap-4">
          <span className="text-gray-400">Nodes:</span>
          <div className="flex items-center gap-2">
            <span className="w-4 h-4 rounded-full bg-blue-500"></span>
            <span className="text-gray-300">Core</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-4 h-4 rounded-full bg-purple-500"></span>
            <span className="text-gray-300">Gateway</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-4 h-4 rounded-full bg-amber-500"></span>
            <span className="text-gray-300">Aggregation</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-4 h-4 rounded-full bg-green-500"></span>
            <span className="text-gray-300">Edge</span>
          </div>
        </div>
        <div className="text-gray-600">|</div>
        <div className="flex items-center gap-4">
          <span className="text-gray-400">Links:</span>
          <div className="flex items-center gap-2">
            <span className="w-6 h-0.5 bg-gray-500"></span>
            <span className="text-gray-300">OSPF/MPLS</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-6 h-0.5 bg-green-500"></span>
            <span className="text-gray-300">BFD</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-6 h-0.5 bg-red-500 border-dashed" style={{borderTop: '2px dashed #ef4444', height: 0}}></span>
            <span className="text-gray-300">HSRP</span>
          </div>
        </div>
      </div>

      {/* Topology Container */}
      <div
        ref={containerRef}
        className="flex-1 bg-gray-800 rounded-lg border border-gray-700 relative overflow-hidden"
        style={{ minHeight: '500px' }}
      >
        {loading ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
          </div>
        ) : (
          <svg
            ref={svgRef}
            className="w-full h-full"
            style={{ background: '#1f2937' }}
          />
        )}

        {/* Node tooltip */}
        <div
          id="node-tooltip"
          className="fixed bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm z-50 pointer-events-none shadow-lg"
          style={{ display: 'none' }}
        />

        {/* Link tooltip */}
        <div
          id="link-tooltip"
          className="fixed bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm z-50 pointer-events-none"
          style={{ display: 'none' }}
        />
      </div>

      {/* Device Detail Panel */}
      {selectedNode && (
        <div className="fixed right-6 top-24 w-80 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-50">
          <div className="p-4 border-b border-gray-700 flex items-center justify-between">
            <h3 className="font-semibold text-white flex items-center gap-2">
              <Info className="w-4 h-4" />
              {selectedNode.label}
            </h3>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-gray-400 hover:text-white"
            >
              ×
            </button>
          </div>
          <div className="p-4 space-y-3">
            <div className="flex justify-between">
              <span className="text-gray-400">Device ID</span>
              <span className="text-white font-mono text-sm">{selectedNode.id}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Type</span>
              <span className="text-white capitalize">{selectedNode.type}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Layer</span>
              <span className="text-white capitalize">{selectedNode.layer}</span>
            </div>
            {selectedNode.status && (
              <>
                <div className="flex justify-between">
                  <span className="text-gray-400">Status</span>
                  <span className={selectedNode.status.is_reachable ? 'text-green-400' : 'text-red-400'}>
                    {selectedNode.status.is_reachable ? 'Online' : 'Offline'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">IP Address</span>
                  <span className="text-white font-mono text-sm">{selectedNode.status.ip_address}</span>
                </div>
                {selectedNode.status.last_seen && (
                  <div className="flex justify-between">
                    <span className="text-gray-400">Last Seen</span>
                    <span className="text-white text-sm">
                      {new Date(selectedNode.status.last_seen).toLocaleString()}
                    </span>
                  </div>
                )}
              </>
            )}
            {selectedNode.status?.id && (
              <div className="pt-2">
                <a
                  href={`/devices/${selectedNode.status.id}`}
                  className="block w-full text-center bg-blue-600 hover:bg-blue-700 text-white py-2 rounded-lg transition-colors"
                >
                  View Details
                </a>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
