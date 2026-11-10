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
import type { ProjectLink, Section } from "../../api/client";
import { Chip } from "../Chip";
import { ZoomIn, ZoomOut } from "../Icons";

const WIDTH = 820;
const HEIGHT = 440;

type GraphNode = SimulationNodeDatum & { id: string; number: string; title: string; role: string };
type GraphLink = SimulationLinkDatum<GraphNode> & { id: string; kind: string; score: number };
type Transform = { x: number; y: number; k: number };
type DragState = { x: number; y: number; tx: number; ty: number; sx: number; sy: number };

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function ContextGraph({
  sections,
  links,
  selectedId,
  onSelect,
}: {
  sections: Section[];
  links: ProjectLink[];
  selectedId: string | null;
  onSelect: (section: Section) => void;
}) {
  const reduced = useReducedMotion();
  const svgRef = useRef<SVGSVGElement>(null);
  const simulationRef = useRef<Simulation<GraphNode, GraphLink> | null>(null);
  const positionsRef = useRef(new Map<string, { x: number; y: number }>());
  const dragRef = useRef<DragState | null>(null);
  const [, setTick] = useState(0);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [transform, setTransform] = useState<Transform>({ x: 0, y: 0, k: 1 });

  const visibleSections = useMemo(
    () =>
      sections.filter(
        (section) =>
          section.text.trim() && section.role !== "front_matter" && section.role !== "ignored",
      ),
    [sections],
  );

  const visibleIds = useMemo(() => new Set(visibleSections.map((section) => section.id)), [visibleSections]);
  const enabledLinks = useMemo(
    () =>
      links.filter(
        (link) => link.enabled && visibleIds.has(link.source_id) && visibleIds.has(link.target_id),
      ),
    [links, visibleIds],
  );

  const nodeKey = visibleSections.map((section) => section.id).join("|");
  const edgeKey = enabledLinks.map((link) => link.id).join("|");
  const simulationKey = `${nodeKey}##${edgeKey}`;

  useEffect(() => {
    const previous = simulationRef.current;
    previous?.stop();
    const nodes: GraphNode[] = visibleSections.map((section, index) => {
      const stored = positionsRef.current.get(section.id);
      const angle = (index / Math.max(1, visibleSections.length)) * Math.PI * 2;
      const radius = 70 + Math.min(190, visibleSections.length * 4);
      return {
        id: section.id,
        number: section.number,
        title: section.title,
        role: section.role,
        x: stored?.x ?? WIDTH / 2 + Math.cos(angle) * radius,
        y: stored?.y ?? HEIGHT / 2 + Math.sin(angle) * radius,
      };
    });
    const byId = new Map(nodes.map((node) => [node.id, node]));
    const graphLinks: GraphLink[] = enabledLinks.map((link) => ({
      id: String(link.id),
      kind: link.kind,
      score: link.score,
      source: byId.get(link.source_id)?.id ?? link.source_id,
      target: byId.get(link.target_id)?.id ?? link.target_id,
    }));
    const simulation = forceSimulation<GraphNode>(nodes)
      .force("charge", forceManyBody<GraphNode>().strength(-150))
      .force("center", forceCenter(WIDTH / 2, HEIGHT / 2))
      .force("collide", forceCollide<GraphNode>().radius(22))
      .force(
        "link",
        forceLink<GraphNode, GraphLink>(graphLinks)
          .id((node) => node.id)
          .distance((link) => 75 + (1 - link.score) * 70)
          .strength(0.42),
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
    // The key captures the graph structure; selection only recolors.
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
    for (const link of enabledLinks) {
      if (link.source_id === focusId) set.add(link.target_id);
      if (link.target_id === focusId) set.add(link.source_id);
    }
    return set;
  }, [focusId, enabledLinks]);

  const byId = useMemo(() => new Map(visibleSections.map((section) => [section.id, section])), [visibleSections]);

  const zoomBy = (factor: number) => {
    setTransform((previous) => {
      const k = clamp(previous.k * factor, 0.45, 2.8);
      const worldX = (WIDTH / 2 - previous.x) / previous.k;
      const worldY = (HEIGHT / 2 - previous.y) / previous.k;
      return { k, x: WIDTH / 2 - worldX * k, y: HEIGHT / 2 - worldY * k };
    });
  };

  const handleWheel = (event: WheelEvent<SVGSVGElement>) => {
    event.preventDefault();
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const px = ((event.clientX - rect.left) / rect.width) * WIDTH;
    const py = ((event.clientY - rect.top) / rect.height) * HEIGHT;
    setTransform((previous) => {
      const k = clamp(previous.k * (event.deltaY < 0 ? 1.12 : 0.89), 0.45, 2.8);
      const worldX = (px - previous.x) / previous.k;
      const worldY = (py - previous.y) / previous.k;
      return { k, x: px - worldX * k, y: py - worldY * k };
    });
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

  const counts = useMemo(() => {
    const byKind = new Map<string, number>();
    for (const link of enabledLinks) byKind.set(link.kind, (byKind.get(link.kind) ?? 0) + 1);
    return Array.from(byKind.entries());
  }, [enabledLinks]);

  return (
    <div className="context-graph">
      <div className="context-graph__head">
        <div>
          <h2>Meaning graph</h2>
          <p>Click a section to inspect its links and exact prompt.</p>
        </div>
        <div className="context-graph__chips">
          <Chip tone="outline">{visibleSections.length} sections</Chip>
          <Chip tone="outline">{enabledLinks.length} links</Chip>
        </div>
      </div>

      {visibleSections.length === 0 ? (
        <div className="context-graph__empty">
          <strong>No graph yet</strong>
          The document has no text-bearing sections to link.
        </div>
      ) : (
        <div className="live-graph__canvas context-graph__canvas">
          <svg
            ref={svgRef}
            className="live-graph__svg"
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            role="img"
            aria-label="Meaning graph of document sections"
            onWheel={handleWheel}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={endDrag}
            onPointerCancel={endDrag}
          >
            <g transform={`translate(${transform.x} ${transform.y}) scale(${transform.k})`}>
              {enabledLinks.map((link) => {
                const source = positionById.get(link.source_id);
                const target = positionById.get(link.target_id);
                if (!source || !target) return null;
                const incident =
                  !focusId || link.source_id === focusId || link.target_id === focusId;
                return (
                  <motion.path
                    key={link.id}
                    d={`M ${source.x} ${source.y} L ${target.x} ${target.y}`}
                    className={`live-graph-edge is-${link.kind} ${incident ? "is-hot" : "is-muted"}`}
                    strokeWidth={1.2 + link.score * 2.4}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: incident ? 0.85 : 0.14 }}
                    transition={{ duration: reduced ? 0 : 0.3 }}
                  />
                );
              })}
              {visibleSections.map((section) => {
                const position = positionById.get(section.id);
                if (!position) return null;
                const related = !focusId || section.id === focusId || neighbours.has(section.id);
                return (
                  <motion.g
                    key={section.id}
                    data-graph-node={section.id}
                    className={[
                      "live-graph-node",
                      `is-role-${section.role}`,
                      section.id === selectedId ? "is-selected" : "",
                      related ? "" : "is-muted",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    transform={`translate(${position.x} ${position.y})`}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: related ? 1 : 0.25 }}
                    transition={{ duration: reduced ? 0 : 0.28 }}
                    onPointerEnter={() => setHoverId(section.id)}
                    onPointerLeave={() => setHoverId((current) => (current === section.id ? null : current))}
                    onClick={(event) => {
                      event.stopPropagation();
                      onSelect(section);
                    }}
                  >
                    <title>{`${section.number || "Section"} ${section.title}`}</title>
                    <circle r={section.id === selectedId ? 11 : 7} />
                    <text y={19} textAnchor="middle" className="live-graph-node__label">
                      {section.number || "§"}
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
            <button type="button" onClick={() => setTransform({ x: 0, y: 0, k: 1 })} aria-label="Reset graph view">
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
          <i className="is-reference" /> reference
        </span>
        <span>
          <i className="is-lexical" /> lexical
        </span>
        <span>Thickness = score</span>
        {counts.map(([kind, count]) => (
          <span key={kind}>{`${count} ${kind}`}</span>
        ))}
        {selectedId && byId.get(selectedId) && (
          <span className="context-graph__focus">{byId.get(selectedId)?.title}</span>
        )}
      </div>
    </div>
  );
}
