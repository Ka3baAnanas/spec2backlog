import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type Simulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";
import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useRef, useState, type PointerEvent, type WheelEvent } from "react";
import type { Node } from "../../api/client";
import type { LeafRunState, RunState } from "../../lib/runState";
import { Chip } from "../Chip";
import { ZoomIn, ZoomOut } from "../Icons";

const WIDTH = 820;
const HEIGHT = 390;

type GraphNode = SimulationNodeDatum & {
  id: string;
  number: string;
  title: string;
};

type GraphLink = SimulationLinkDatum<GraphNode> & {
  id: string;
  kind: string;
  score: number;
};

type Transform = { x: number; y: number; k: number };

type DragState = {
  x: number;
  y: number;
  tx: number;
  ty: number;
  sx: number;
  sy: number;
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function MeaningGraph({
  leaves,
  state,
  selectedId,
  onSelect,
}: {
  leaves: Node[];
  state: RunState;
  selectedId: string | null;
  onSelect: (node: Node) => void;
}) {
  const reduced = useReducedMotion();
  const svgRef = useRef<SVGSVGElement>(null);
  const simulationRef = useRef<Simulation<GraphNode, GraphLink> | null>(null);
  const positionsRef = useRef(new Map<string, { x: number; y: number }>());
  const dragRef = useRef<DragState | null>(null);
  const [, setTick] = useState(0);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [transform, setTransform] = useState<Transform>({ x: 0, y: 0, k: 1 });

  const processedIds = useMemo(() => {
    const ids = new Set<string>();
    for (const [id, runtime] of Object.entries(state.leaves)) {
      if (runtime.state !== "waiting") ids.add(id);
    }
    for (const edge of state.edges) {
      ids.add(edge.source);
      ids.add(edge.target);
    }
    return ids;
  }, [state.leaves, state.edges]);

  const nodeSpecs = useMemo(
    () =>
      leaves
        .filter((node) => processedIds.has(node.id))
        .map((node) => ({
          id: node.id,
          number: node.number,
          title: node.title,
          source: node,
        })),
    [leaves, processedIds],
  );

  const visibleNodeIds = useMemo(
    () => new Set(nodeSpecs.map((node) => node.id)),
    [nodeSpecs],
  );
  const edgeSpecs = useMemo(
    () =>
      state.edges.filter(
        (edge) =>
          processedIds.has(edge.source) &&
          processedIds.has(edge.target) &&
          visibleNodeIds.has(edge.source) &&
          visibleNodeIds.has(edge.target),
      ),
    [state.edges, processedIds, visibleNodeIds],
  );

  const nodeKey = nodeSpecs.map((node) => node.id).join("|");
  const edgeKey = edgeSpecs.map((edge) => edge.id).join("|");
  const simulationKey = `${nodeKey}##${edgeKey}`;

  useEffect(() => {
    const previous = simulationRef.current;
    previous?.stop();
    const nodes: GraphNode[] = nodeSpecs.map((spec, index) => {
      const stored = positionsRef.current.get(spec.id);
      const angle = (index / Math.max(1, nodeSpecs.length)) * Math.PI * 2;
      const radius = 60 + Math.min(180, nodeSpecs.length * 5);
      return {
        id: spec.id,
        number: spec.number,
        title: spec.title,
        x: stored?.x ?? WIDTH / 2 + Math.cos(angle) * radius,
        y: stored?.y ?? HEIGHT / 2 + Math.sin(angle) * radius,
      };
    });
    const byId = new Map(nodes.map((node) => [node.id, node]));
    const links: GraphLink[] = edgeSpecs.map((edge) => ({
      id: edge.id,
      kind: edge.kind,
      score: edge.score,
      source: byId.get(edge.source)?.id ?? edge.source,
      target: byId.get(edge.target)?.id ?? edge.target,
    }));
    const simulation = forceSimulation<GraphNode>(nodes)
      .force("charge", forceManyBody<GraphNode>().strength(-120))
      .force("center", forceCenter(WIDTH / 2, HEIGHT / 2))
      .force("collide", forceCollide<GraphNode>().radius(18))
      .force(
        "link",
        forceLink<GraphNode, GraphLink>(links)
          .id((node) => node.id)
          .distance((link) => 70 + (1 - link.score) * 70)
          .strength(0.45),
      )
      .alpha(0.9)
      .on("tick", () => {
        for (const node of nodes) {
          if (typeof node.x === "number" && typeof node.y === "number") {
            positionsRef.current.set(node.id, { x: node.x, y: node.y });
          }
        }
        setTick((value) => value + 1);
      });
    simulationRef.current = simulation;
    setTick((value) => value + 1);
    return () => {
      simulation.stop();
      if (simulationRef.current === simulation) simulationRef.current = null;
    };
    // The key captures the structural graph; state changes recolor without restarting physics.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [simulationKey]);

  const simulationNodes = simulationRef.current?.nodes() ?? [];
  const positionById = new Map(
    simulationNodes.map((node) => [node.id, { x: node.x ?? WIDTH / 2, y: node.y ?? HEIGHT / 2 }]),
  );

  const focusId = hoverId ?? selectedId;
  const neighbours = useMemo(() => {
    const set = new Set<string>();
    if (!focusId) return set;
    for (const edge of state.edges) {
      if (edge.source === focusId) set.add(edge.target);
      if (edge.target === focusId) set.add(edge.source);
    }
    return set;
  }, [focusId, state.edges]);

  const zoomBy = (factor: number, anchorX = WIDTH / 2, anchorY = HEIGHT / 2) => {
    setTransform((previous) => {
      const k = clamp(previous.k * factor, 0.45, 2.8);
      const worldX = (anchorX - previous.x) / previous.k;
      const worldY = (anchorY - previous.y) / previous.k;
      return { k, x: anchorX - worldX * k, y: anchorY - worldY * k };
    });
  };

  const handleWheel = (event: WheelEvent<SVGSVGElement>) => {
    event.preventDefault();
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const px = ((event.clientX - rect.left) / rect.width) * WIDTH;
    const py = ((event.clientY - rect.top) / rect.height) * HEIGHT;
    zoomBy(event.deltaY < 0 ? 1.12 : 0.89, px, py);
  };

  const handlePointerDown = (event: PointerEvent<SVGSVGElement>) => {
    const target = event.target as Element | null;
    if (target?.closest("[data-graph-node]")) return;
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    dragRef.current = {
      x: event.clientX,
      y: event.clientY,
      tx: transform.x,
      ty: transform.y,
      sx: WIDTH / Math.max(1, rect.width),
      sy: HEIGHT / Math.max(1, rect.height),
    };
    svg.setPointerCapture(event.pointerId);
  };

  const handlePointerMove = (event: PointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current;
    if (!drag) return;
    setTransform((previous) => ({
      ...previous,
      x: drag.tx + (event.clientX - drag.x) * drag.sx,
      y: drag.ty + (event.clientY - drag.y) * drag.sy,
    }));
  };

  const endDrag = (event: PointerEvent<SVGSVGElement>) => {
    dragRef.current = null;
    if (svgRef.current?.hasPointerCapture(event.pointerId)) {
      svgRef.current.releasePointerCapture(event.pointerId);
    }
  };

  const linksByKind = useMemo(() => {
    const counts = new Map<string, number>();
    for (const edge of state.edges) counts.set(edge.kind, (counts.get(edge.kind) ?? 0) + 1);
    return Array.from(counts.entries());
  }, [state.edges]);

  return (
    <div className="live-graph">
      <div className="live-panel__head">
        <div>
          <h2>Meaning graph</h2>
          <p>Leaves appear as they are embedded; links arrive one by one.</p>
        </div>
        <div className="live-graph__chips">
          <Chip tone="blue">{state.edges.filter((edge) => edge.kind === "similarity").length} similar</Chip>
          <Chip tone="amber">
            {state.edges.filter((edge) => edge.kind === "reference").length} explicit
          </Chip>
        </div>
      </div>

      {nodeSpecs.length === 0 ? (
        <div className="live-graph__empty">
          <strong>Graph is waiting for leaves</strong>
          Nodes will appear when the graph stage starts embedding sections.
        </div>
      ) : (
        <div className="live-graph__canvas">
          <svg
            ref={svgRef}
            className="live-graph__svg"
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            role="img"
            aria-label="Animated meaning graph"
            onWheel={handleWheel}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={endDrag}
            onPointerCancel={endDrag}
          >
            <g transform={`translate(${transform.x} ${transform.y}) scale(${transform.k})`}>
              {edgeSpecs.map((edge) => {
                const source = positionById.get(edge.source);
                const target = positionById.get(edge.target);
                if (!source || !target) return null;
                const incident = !focusId || edge.source === focusId || edge.target === focusId;
                return (
                  <motion.path
                    key={edge.id}
                    d={`M ${source.x} ${source.y} L ${target.x} ${target.y}`}
                    className={[
                      "live-graph-edge",
                      `is-${edge.kind}`,
                      incident ? "is-hot" : "is-muted",
                    ].join(" ")}
                    strokeWidth={1.2 + edge.score * 2.4}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: incident ? 0.9 : 0.16 }}
                    transition={{ duration: reduced ? 0 : 0.35 }}
                  />
                );
              })}

              {nodeSpecs.map((node) => {
                const position = positionById.get(node.id);
                if (!position) return null;
                const leafState: LeafRunState = state.leaves[node.id]?.state ?? "waiting";
                const related = !focusId || node.id === focusId || neighbours.has(node.id);
                return (
                  <motion.g
                    key={node.id}
                    data-graph-node={node.id}
                    className={`live-graph-node is-${leafState} ${related ? "" : "is-muted"}`}
                    transform={`translate(${position.x} ${position.y})`}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: related ? 1 : 0.25 }}
                    transition={{ duration: reduced ? 0 : 0.3 }}
                    onPointerEnter={() => setHoverId(node.id)}
                    onPointerLeave={() => setHoverId((current) => (current === node.id ? null : current))}
                    onClick={(event) => {
                      event.stopPropagation();
                      onSelect(node.source);
                    }}
                  >
                    <title>{`${node.number || "Section"} ${node.title}`}</title>
                    <circle r={node.id === selectedId ? 10 : 7} />
                    <text y={18} textAnchor="middle" className="live-graph-node__label">
                      {node.number || "§"}
                    </text>
                  </motion.g>
                );
              })}
            </g>
          </svg>

          <div className="live-graph__controls" aria-label="Graph zoom controls">
            <button type="button" onClick={() => zoomBy(1.18)} aria-label="Zoom in">
              <ZoomIn size={14} />
            </button>
            <button type="button" onClick={() => zoomBy(0.85)} aria-label="Zoom out">
              <ZoomOut size={14} />
            </button>
            <button
              type="button"
              onClick={() => setTransform({ x: 0, y: 0, k: 1 })}
              aria-label="Reset graph view"
            >
              1:1
            </button>
          </div>
        </div>
      )}

      <div className="live-graph__legend">
        <span>
          <i className="is-similarity" /> similarity
        </span>
        <span>
          <i className="is-reference" /> explicit reference
        </span>
        <span>Thickness = score</span>
        <span>{state.edges.length} links drawn</span>
        {linksByKind.length > 0 && (
          <span>
            {linksByKind.map(([kind, count]) => `${count} ${kind}`).join(" · ")}
          </span>
        )}
      </div>
    </div>
  );
}
