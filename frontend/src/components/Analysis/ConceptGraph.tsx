import { useState, useMemo } from 'react';
import {
  ReactFlow,
  Node,
  Edge,
  Background,
  Controls,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';
import { Network, Loader2, RefreshCw, ChevronDown, ChevronRight } from 'lucide-react';
import { ConceptGraph as ConceptGraphData } from '../../types';

interface ConceptGraphProps {
  conceptGraph: ConceptGraphData | null | undefined;
  onGenerate: () => Promise<void>;
  loading?: boolean;
}

const TIER_COLORS = {
  prerequisite: { bg: '#1e3a5f', border: '#3b82f6', text: '#e0f2fe', label: 'you need this first' },
  intermediate: { bg: '#2d6a4f', border: '#22c55e', text: '#dcfce7', label: 'intermediate concept' },
  target: { bg: '#9a3412', border: '#f97316', text: '#ffedd5', label: 'target concept' },
};

function ConceptNode({ data }: { data: { label: string; tier: string; description: string } }) {
  const tier = data.tier as keyof typeof TIER_COLORS;
  const colors = TIER_COLORS[tier] || TIER_COLORS.intermediate;

  return (
    <div className="group" style={{ position: 'relative' }}>
      {/* Tooltip — outside the clipped box so it can overflow */}
      {data.description && (
        <div
          className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none"
          style={{
            background: '#1f2937',
            color: '#e5e7eb',
            padding: '8px 12px',
            borderRadius: '8px',
            fontSize: '12px',
            maxWidth: '250px',
            whiteSpace: 'normal',
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
            zIndex: 50,
          }}
        >
          {data.description}
        </div>
      )}
      <div
        style={{
          background: colors.bg,
          border: `2px solid ${colors.border}`,
          borderRadius: '12px',
          padding: '10px 16px',
          width: NODE_WIDTH - 4,
          textAlign: 'center',
          cursor: 'grab',
          overflow: 'hidden',
        }}
      >
        <Handle type="target" position={Position.Top} style={{ background: colors.border, width: 8, height: 8 }} />
        <div style={{
          color: colors.text,
          fontWeight: 600,
          fontSize: '13px',
          lineHeight: '1.3',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          wordBreak: 'break-word',
        }}>
          {data.label}
        </div>
        <Handle type="source" position={Position.Bottom} style={{ background: colors.border, width: 8, height: 8 }} />
      </div>
    </div>
  );
}

const NODE_WIDTH = 170;
const NODE_HEIGHT = 52;

const nodeTypes = { concept: ConceptNode };

function getLayoutedElements(
  graphData: ConceptGraphData,
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'TB', nodesep: 70, ranksep: 80, marginx: 20, marginy: 20 });

  graphData.concepts.forEach((c) => {
    g.setNode(c.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  });

  graphData.edges.forEach((e) => {
    g.setEdge(e.from, e.to);
  });

  dagre.layout(g);

  const nodes: Node[] = graphData.concepts.map((c) => {
    const pos = g.node(c.id);
    return {
      id: c.id,
      type: 'concept',
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
      data: { label: c.label, tier: c.tier, description: c.description },
      draggable: true,
    };
  });

  const edges: Edge[] = graphData.edges.map((e, i) => {
    const sourceTier = graphData.concepts.find((c) => c.id === e.from)?.tier || 'intermediate';
    const colors = TIER_COLORS[sourceTier as keyof typeof TIER_COLORS] || TIER_COLORS.intermediate;
    return {
      id: `e-${i}`,
      source: e.from,
      target: e.to,
      animated: true,
      style: { stroke: colors.border, strokeWidth: 2 },
      markerEnd: { type: MarkerType.ArrowClosed, color: colors.border, width: 16, height: 16 },
    };
  });

  return { nodes, edges };
}

function GraphCanvas({ graphData }: { graphData: ConceptGraphData }) {
  const { nodes: layoutNodes, edges: layoutEdges } = useMemo(
    () => getLayoutedElements(graphData),
    [graphData]
  );

  const [nodes, , onNodesChange] = useNodesState(layoutNodes);
  const [edges, , onEdgesChange] = useEdgesState(layoutEdges);

  return (
    <div style={{ height: 420 }} className="rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        proOptions={{ hideAttribution: true }}
        minZoom={0.3}
        maxZoom={2}
      >
        <Background color="#374151" gap={20} />
        <Controls
          showInteractive={false}
          style={{ background: '#1f2937', borderColor: '#374151' }}
        />
      </ReactFlow>
    </div>
  );
}

export default function ConceptGraphSection({ conceptGraph, onGenerate, loading }: ConceptGraphProps) {
  const [expanded, setExpanded] = useState(true);

  const tierCounts = useMemo(() => {
    if (!conceptGraph) return null;
    const counts = { prerequisite: 0, intermediate: 0, target: 0 };
    conceptGraph.concepts.forEach((c) => {
      if (c.tier in counts) counts[c.tier as keyof typeof counts]++;
    });
    return counts;
  }, [conceptGraph]);

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-6 py-4 hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors"
      >
        <div className="flex items-center gap-3">
          <Network className="w-5 h-5 text-blue-500" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Concept Prerequisite Graph
          </h3>
          {conceptGraph && tierCounts && (
            <span className="text-sm text-gray-500 dark:text-gray-400">
              {conceptGraph.concepts.length} concepts, {conceptGraph.edges.length} dependencies
            </span>
          )}
        </div>
        {expanded ? (
          <ChevronDown className="w-5 h-5 text-gray-400" />
        ) : (
          <ChevronRight className="w-5 h-5 text-gray-400" />
        )}
      </button>

      {expanded && (
        <div className="px-6 pb-6">
          {!conceptGraph && !loading && (
            <div className="text-center py-8">
              <Network className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
              <p className="text-gray-500 dark:text-gray-400 mb-4">
                Generate a concept graph to see what knowledge a reader needs before this text makes sense.
              </p>
              <button
                onClick={onGenerate}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
              >
                <Network className="w-4 h-4" />
                Generate Concept Graph
              </button>
            </div>
          )}

          {loading && (
            <div className="text-center py-8">
              <Loader2 className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-3" />
              <p className="text-gray-500 dark:text-gray-400">
                Extracting concepts and mapping prerequisites...
              </p>
            </div>
          )}

          {conceptGraph && !loading && (
            <>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-4 text-xs">
                  {Object.entries(TIER_COLORS).map(([tier, colors]) => (
                    <div key={tier} className="flex items-center gap-1.5">
                      <span
                        className="inline-block w-3 h-3 rounded"
                        style={{ background: colors.bg, border: `1.5px solid ${colors.border}` }}
                      />
                      <span className="text-gray-600 dark:text-gray-400">{colors.label}</span>
                    </div>
                  ))}
                </div>
                <button
                  onClick={onGenerate}
                  className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-blue-500 dark:text-gray-400 dark:hover:text-blue-400 transition-colors"
                  title="Regenerate"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Regenerate
                </button>
              </div>

              <GraphCanvas graphData={conceptGraph} />

              <p className="text-xs text-gray-400 dark:text-gray-500 mt-2 text-center italic">
                Arrows mean "is required before". The graph shows what a reader must already know.
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
