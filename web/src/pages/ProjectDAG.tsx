import React, { useEffect, useState, useMemo } from 'react';
import { Card, Select, Tag, Spin, Empty, message } from 'antd';
import { getProjects, getProjectDAG } from '../services/api';
import type { DAGData, Project } from '../types';

const ACCENT = '#2563eb';
const NODE_W = 180;
const NODE_H = 52;
const LAYER_GAP = 100;
const NODE_GAP = 24;

interface LayoutNode {
  id: number;
  name: string;
  type: string;
  requires_instrument: boolean;
  status: string;
  x: number;
  y: number;
  layer: number;
}

interface LayoutEdge {
  from: LayoutNode;
  to: LayoutNode;
}

const ProjectDAG: React.FC = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProj, setSelectedProj] = useState<number | null>(null);
  const [dagData, setDagData] = useState<DAGData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getProjects().then(setProjects).catch(() => message.error('加载项目失败'));
  }, []);

  useEffect(() => {
    if (!selectedProj) { setDagData(null); return; }
    setLoading(true);
    getProjectDAG(selectedProj)
      .then(setDagData)
      .catch(() => message.error('加载依赖关系失败'))
      .finally(() => setLoading(false));
  }, [selectedProj]);

  const layout = useMemo(() => {
    if (!dagData || dagData.nodes.length === 0) return { nodes: [], edges: [], svgW: 0, svgH: 0 };

    const nodeMap = new Map(dagData.nodes.map(n => [n.id, n]));
    const children = new Map<number, number[]>();
    const parents = new Map<number, number[]>();
    dagData.nodes.forEach(n => { children.set(n.id, []); parents.set(n.id, []); });
    dagData.edges.forEach(e => {
      children.get(e.from)?.push(e.to);
      parents.get(e.to)?.push(e.from);
    });

    // Topological layering
    const layers: number[][] = [];
    const assigned = new Set<number>();
    const queue: number[] = [];
    dagData.nodes.forEach(n => { if ((parents.get(n.id)?.length || 0) === 0) queue.push(n.id); });

    while (queue.length > 0) {
      const currentLayer: number[] = [];
      const nextQueue: number[] = [];
      for (const nid of queue) {
        if (assigned.has(nid)) continue;
        currentLayer.push(nid);
        assigned.add(nid);
      }
      if (currentLayer.length === 0) break;
      layers.push(currentLayer);
      for (const nid of currentLayer) {
        for (const child of (children.get(nid) || [])) {
          if (!assigned.has(child)) nextQueue.push(child);
        }
      }
      queue.length = 0;
      queue.push(...nextQueue);
    }

    // Assign coordinates
    const layoutNodes: LayoutNode[] = [];
    layers.forEach((layer, li) => {
      const totalW = layer.length * NODE_W + (layer.length - 1) * NODE_GAP;
      const startX = -totalW / 2 + NODE_W / 2;
      layer.forEach((nid, ni) => {
        const node = nodeMap.get(nid)!;
        layoutNodes.push({
          id: node.id, name: node.name, type: node.type,
          requires_instrument: node.requires_instrument, status: node.status,
          x: startX + ni * (NODE_W + NODE_GAP),
          y: li * (NODE_H + LAYER_GAP) + NODE_H / 2,
          layer: li,
        });
      });
    });

    const nodeLookup = new Map(layoutNodes.map(n => [n.id, n]));
    const edges: LayoutEdge[] = dagData.edges
      .map(e => ({ from: nodeLookup.get(e.from)!, to: nodeLookup.get(e.to)! }))
      .filter(e => e.from && e.to);

    const maxX = Math.max(...layoutNodes.map(n => Math.abs(n.x) + NODE_W / 2), 400);
    const maxY = layers.length * (NODE_H + LAYER_GAP) + 40;

    return { nodes: layoutNodes, edges, svgW: maxX * 2 + 80, svgH: maxY };
  }, [dagData]);

  const statusColor = (status: string) => {
    switch (status) {
      case 'completed': return '#16a34a';
      case 'running': return ACCENT;
      case 'scheduled': return '#7c3aed';
      case 'blocked': return '#dc2626';
      default: return '#94a3b8';
    }
  };

  const statusLabel = (status: string) => {
    switch (status) {
      case 'completed': return '已完成';
      case 'running': return '运行中';
      case 'scheduled': return '已排程';
      case 'blocked': return '阻塞';
      default: return '待处理';
    }
  };

  return (
    <div>
      <div className="page-header">
        <h2>项目依赖关系</h2>
        <p>任务 DAG 拓扑图 — 可视化任务间的先后依赖与数据流</p>
      </div>

      <div style={{ marginBottom: 20 }}>
        <Select
          placeholder="选择项目查看依赖关系"
          style={{ width: 360 }}
          value={selectedProj}
          onChange={setSelectedProj}
          allowClear
          options={projects.map(p => ({ label: p.code + ' ' + p.name, value: p.id }))}
        />
      </div>

      {!selectedProj ? (
        <Card><Empty description="请先选择一个项目" /></Card>
      ) : loading ? (
        <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />
      ) : !dagData || dagData.nodes.length === 0 ? (
        <Card><Empty description="该项目暂无任务" /></Card>
      ) : (
        <Card bodyStyle={{ padding: 0 }}>
          <div style={{
            overflow: 'auto',
            width: '100%',
            maxWidth: layout.svgW,
            minHeight: Math.max(layout.svgH, 300),
            background: '#fafbfc',
            position: 'relative',
          }}>
            <svg
              width={layout.svgW}
              height={layout.svgH}
              style={{ display: 'block' }}
            >
              <defs>
                <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
                  <polygon points="0 0, 10 3.5, 0 7" fill="#cbd5e1" />
                </marker>
              </defs>

              {/* Edges */}
              {layout.edges.map((e, i) => {
                const fromX = e.from.x + layout.svgW / 2;
                const fromY = e.from.y;
                const toX = e.to.x + layout.svgW / 2;
                const toY = e.to.y;
                const midY = (fromY + toY) / 2;

                return (
                  <path
                    key={i}
                    d={`M ${fromX} ${fromY + NODE_H / 2} C ${fromX} ${midY}, ${toX} ${midY}, ${toX} ${toY - NODE_H / 2}`}
                    fill="none"
                    stroke="#cbd5e1"
                    strokeWidth={1.5}
                    markerEnd="url(#arrowhead)"
                  />
                );
              })}

              {/* Nodes */}
              {layout.nodes.map(n => {
                const cx = n.x + layout.svgW / 2;
                const cy = n.y;
                const isInstrument = n.requires_instrument;

                return (
                  <g key={n.id} transform={`translate(${cx - NODE_W / 2}, ${cy - NODE_H / 2})`}>
                    <rect
                      width={NODE_W}
                      height={NODE_H}
                      rx={8}
                      fill="#fff"
                      stroke={isInstrument ? ACCENT : '#e2e8f0'}
                      strokeWidth={isInstrument ? 1.5 : 1}
                      filter="url(#shadow)"
                    />
                    {/* Left accent bar for instrument tasks */}
                    {isInstrument && (
                      <rect x={0} y={0} width={4} height={NODE_H} rx={2} fill={ACCENT}
                        style={{ clipPath: 'inset(0 0 0 0 round 8px 0 0 8px)' }} />
                    )}
                    <text x={isInstrument ? 16 : 12} y={20} fontSize={12} fontWeight={600} fill="#1e293b"
                      textAnchor="start" dominantBaseline="middle"
                      style={{ maxWidth: NODE_W - 32 }}>
                      {n.name.length > 14 ? n.name.slice(0, 14) + '…' : n.name}
                    </text>
                    <text x={isInstrument ? 16 : 12} y={38} fontSize={11} fill="#94a3b8"
                      textAnchor="start" dominantBaseline="middle">
                      {n.type === 'instrument' ? '仪器任务' : n.type === 'manual' ? '人工任务' : '等待任务'}
                      {' · '}
                      <tspan fill={statusColor(n.status)}>{statusLabel(n.status)}</tspan>
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>

          {/* Legend */}
          <div style={{
            padding: '12px 20px', borderTop: '1px solid #f1f5f9',
            display: 'flex', gap: 20, alignItems: 'center', flexWrap: 'wrap',
          }}>
            <span style={{ fontSize: 12, color: '#94a3b8', fontWeight: 500 }}>图例：</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 12, height: 12, borderRadius: 3, border: '1.5px solid ' + ACCENT, background: '#fff' }} />
              <span style={{ fontSize: 12, color: '#475569' }}>仪器任务</span>
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 12, height: 12, borderRadius: 3, border: '1px solid #e2e8f0', background: '#fff' }} />
              <span style={{ fontSize: 12, color: '#475569' }}>人工/等待任务</span>
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 20, height: 2, background: '#cbd5e1' }} />
              <span style={{ fontSize: 12, color: '#475569' }}>前置依赖</span>
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 8 }}>
              <Tag color={ACCENT} style={{ margin: 0, fontSize: 10 }}>运行中</Tag>
              <Tag color="#16a34a" style={{ margin: 0, fontSize: 10 }}>已完成</Tag>
              <Tag color="#7c3aed" style={{ margin: 0, fontSize: 10 }}>已排程</Tag>
              <Tag color="#94a3b8" style={{ margin: 0, fontSize: 10 }}>待处理</Tag>
            </span>
          </div>
        </Card>
      )}
    </div>
  );
};

export default ProjectDAG;
