import type { RunEvent, RunStage } from "../api/run";

export type ChecklistStage = "ingestion" | "tree" | "graph" | "generation" | "validation";
export type StageStatus = "pending" | "active" | "done";
export type LeafRunState = "waiting" | "embedding" | "generating" | "done" | "failed" | "retried";

export type StageState = {
  key: ChecklistStage;
  status: StageStatus;
  counter: string;
  startedAt?: string;
  endedAt?: string;
  error?: string;
};

export type LeafRuntime = {
  state: LeafRunState;
  attempts?: number;
  durationMs?: number;
  stories?: number;
  tests?: number;
  questions?: number;
  error?: string;
  index?: number;
  total?: number;
  startedAt?: string;
  completedAt?: string;
  lastAt?: string;
};

export type RunEdge = {
  id: string;
  source: string;
  target: string;
  kind: string;
  score: number;
  eventId: number;
};

export type RunState = {
  lastEventId: number;
  events: RunEvent[];
  stages: Record<ChecklistStage, StageState>;
  leaves: Record<string, LeafRuntime>;
  edges: RunEdge[];
  currentNodeId: string | null;
  ingestion: Record<string, unknown>;
  tree: Record<string, unknown>;
  graph: Record<string, unknown>;
  generation: Record<string, unknown>;
  error: string | null;
};

export type RunAction = { type: "reset" } | { type: "event"; event: RunEvent };

export const CHECKLIST_STAGES: { key: ChecklistStage; label: string; short: string }[] = [
  { key: "ingestion", label: "Ingestion", short: "Extract document" },
  { key: "tree", label: "Tree", short: "Build section tree" },
  { key: "graph", label: "Graph", short: "Link related sections" },
  { key: "generation", label: "Generation", short: "Draft backlog items" },
  { key: "validation", label: "Validation", short: "Human review" },
];

function emptyStages(): Record<ChecklistStage, StageState> {
  return {
    ingestion: { key: "ingestion", status: "pending", counter: "Waiting for a run" },
    tree: { key: "tree", status: "pending", counter: "Waiting for ingestion" },
    graph: { key: "graph", status: "pending", counter: "Waiting for the tree" },
    generation: { key: "generation", status: "pending", counter: "Waiting for the graph" },
    validation: { key: "validation", status: "pending", counter: "After generation" },
  };
}

export function initialRunState(): RunState {
  return {
    lastEventId: 0,
    events: [],
    stages: emptyStages(),
    leaves: {},
    edges: [],
    currentNodeId: null,
    ingestion: {},
    tree: {},
    graph: {},
    generation: {},
    error: null,
  };
}

export function stageKey(stage: RunStage): ChecklistStage | null {
  return stage === "ingestion" || stage === "tree" || stage === "graph" || stage === "generation"
    ? stage
    : null;
}

const asNumber = (value: unknown): number =>
  typeof value === "number" && Number.isFinite(value) ? value : Number(value) || 0;

const asString = (value: unknown): string => (typeof value === "string" ? value : "");

const asRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};

function ingestionCounter(data: Record<string, unknown>, fallback: string): string {
  if (!Object.keys(data).length) return fallback;
  const parts = [
    `${asNumber(data.headings)} headings`,
    `${asNumber(data.paragraphs)} paragraphs`,
    `${asNumber(data.tables)} tables`,
  ];
  const skipped = asNumber(data.skipped_toc);
  if (skipped) parts.push(`${skipped} TOC blocks skipped`);
  const warnings = asNumber(data.warnings);
  if (warnings) parts.push(`${warnings} warning${warnings === 1 ? "" : "s"}`);
  return parts.join(", ");
}

function treeCounter(data: Record<string, unknown>, fallback: string): string {
  if (!Object.keys(data).length) return fallback;
  const depth = asNumber(data.max_depth);
  return `${asNumber(data.nodes)} sections, ${asNumber(data.leaves)} leaves${depth ? ` · depth ${depth}` : ""}`;
}

function generationStats(leaves: Record<string, LeafRuntime>, total: number) {
  let ok = 0;
  let retried = 0;
  let failed = 0;
  let stories = 0;
  let tests = 0;
  let questions = 0;
  let durationMs = 0;
  let durations = 0;
  for (const leaf of Object.values(leaves)) {
    if (leaf.state === "done") ok += 1;
    if (leaf.state === "retried") retried += 1;
    if (leaf.state === "failed") failed += 1;
    stories += leaf.stories ?? 0;
    tests += leaf.tests ?? 0;
    questions += leaf.questions ?? 0;
    const completed = leaf.state === "done" || leaf.state === "retried" || leaf.state === "failed";
    if (completed) {
      const start = leaf.startedAt ? new Date(leaf.startedAt).getTime() : NaN;
      const end = leaf.completedAt ? new Date(leaf.completedAt).getTime() : NaN;
      const wallDuration = Number.isFinite(start) && Number.isFinite(end) ? end - start : 0;
      const measured = wallDuration > 0 ? wallDuration : leaf.durationMs ?? 0;
      if (measured > 0) {
        durationMs += measured;
        durations += 1;
      }
    }
  }
  return {
    ok,
    retried,
    failed,
    completed: ok + retried + failed,
    total,
    stories,
    tests,
    questions,
    averageDurationMs: durations ? durationMs / durations : null,
  };
}

export type GenerationStats = ReturnType<typeof generationStats>;

export function selectGenerationStats(state: RunState, totalLeaves: number): GenerationStats {
  const total = totalLeaves || asNumber(state.generation.N) || 0;
  return generationStats(state.leaves, total);
}

function generationCounter(state: RunState): string {
  const total = asNumber(state.generation.N);
  const stats = generationStats(state.leaves, total);
  if (!total) return stats.completed ? `${stats.completed} leaves processed` : "Preparing leaves";
  return `${stats.completed}/${total} leaves, ${stats.stories} stories`;
}

function updateLeaf(
  leaves: Record<string, LeafRuntime>,
  nodeId: string,
  patch: Partial<LeafRuntime>,
): Record<string, LeafRuntime> {
  if (!nodeId) return leaves;
  return { ...leaves, [nodeId]: { ...(leaves[nodeId] ?? { state: "waiting" }), ...patch } };
}

function edgeKey(source: string, target: string, kind: string): string {
  return `${source}->${target}:${kind}`;
}

export function runReducer(state: RunState, action: RunAction): RunState {
  if (action.type === "reset") return initialRunState();
  const event = action.event;
  if (!Number.isFinite(event.id) || event.id <= state.lastEventId) return state;

  const data = asRecord(event.data);
  const key = stageKey(event.stage);
  const message = event.message || `${event.stage} ${event.type}`;
  let stages = state.stages;
  let leaves = state.leaves;
  let edges = state.edges;
  let currentNodeId = state.currentNodeId;
  let ingestion = state.ingestion;
  let tree = state.tree;
  let graph = state.graph;
  let generation = state.generation;
  let error = state.error;

  if (key) {
    const current = stages[key];
    if (event.type === "stage_start") {
      error = null;
      stages = {
        ...stages,
        [key]: { ...current, status: "active", startedAt: current.startedAt ?? event.ts, error: undefined },
      };
    } else if (event.type === "stage_end") {
      stages = {
        ...stages,
        [key]: { ...current, status: "done", endedAt: event.ts },
      };
    }
  }

  if (event.stage === "ingestion") {
    if (event.type === "progress" || event.type === "stage_end" || event.type === "stage_start") {
      ingestion = { ...ingestion, ...data };
      stages = {
        ...stages,
        ingestion: {
          ...stages.ingestion,
          counter: ingestionCounter(ingestion, stages.ingestion.counter),
        },
      };
    }
  }

  if (event.stage === "tree") {
    if (event.type === "progress" || event.type === "stage_end" || event.type === "stage_start") {
      tree = { ...tree, ...data };
      stages = {
        ...stages,
        tree: { ...stages.tree, counter: treeCounter(tree, stages.tree.counter) },
      };
    }
  }

  if (event.stage === "graph") {
    if (event.type === "stage_start") {
      graph = { ...graph, ...data };
      currentNodeId = null;
    }
    if (event.type === "progress") {
      const nodeId = asString(data.node_id);
      const i = asNumber(data.i);
      const n = asNumber(data.N);
      if (nodeId) {
        const existing = leaves[nodeId];
        if (!existing || existing.state === "waiting") {
          leaves = updateLeaf(leaves, nodeId, { state: "embedding", lastAt: event.ts });
        }
        currentNodeId = nodeId;
      }
      graph = { ...graph, ...data, embedded: Math.max(asNumber(graph.embedded), i), N: n || graph.N };
      stages = {
        ...stages,
        graph: {
          ...stages.graph,
          counter: `${edges.length} links · ${i}/${n || asNumber(graph.N)} embedded`,
        },
      };
    }
    if (event.type === "link_found") {
      const source = asString(data.source_id);
      const target = asString(data.target_id);
      const kind = asString(data.kind) || "similarity";
      const score = asNumber(data.score);
      if (source && target) {
        const nextEdge: RunEdge = {
          id: `${event.id}:${edgeKey(source, target, kind)}`,
          source,
          target,
          kind,
          score,
          eventId: event.id,
        };
        const at = edges.findIndex(
          (edge) => edge.source === source && edge.target === target && edge.kind === kind,
        );
        if (at >= 0) {
          edges = edges.map((edge, index) => (index === at ? nextEdge : edge));
        } else {
          edges = [...edges, nextEdge];
        }
        for (const nodeId of [source, target]) {
          const existing = leaves[nodeId];
          if (!existing || existing.state === "waiting") {
            leaves = updateLeaf(leaves, nodeId, { state: "embedding", lastAt: event.ts });
          }
        }
        graph = { ...graph, links: edges.length };
        stages = {
          ...stages,
          graph: { ...stages.graph, counter: `${edges.length} links` },
        };
      }
    }
    if (event.type === "stage_end") {
      graph = { ...graph, ...data, links: asNumber(data.edges) || edges.length };
      currentNodeId = null;
      const byKind = asRecord(data.edges_by_kind);
      const kindText = Object.entries(byKind)
        .map(([kind, count]) => `${asNumber(count)} ${kind}`)
        .join(" · ");
      const zero = asNumber(data.leaves_with_zero_links);
      stages = {
        ...stages,
        graph: {
          ...stages.graph,
          counter: `${asNumber(data.edges) || edges.length} links${kindText ? ` · ${kindText}` : ""}${
            zero ? ` · ${zero} leaves without links` : ""
          }`,
        },
      };
    }
  }

  if (event.stage === "generation") {
    if (event.type === "stage_start") {
      generation = { ...generation, ...data };
      currentNodeId = null;
      stages = {
        ...stages,
        generation: {
          ...stages.generation,
          counter: `${asNumber(data.N)} leaves queued${data.only_failed ? " · retry mode" : ""}`,
        },
      };
    }
    if (event.type === "leaf_start") {
      const nodeId = asString(data.node_id);
      if (nodeId) {
        leaves = updateLeaf(leaves, nodeId, {
          state: "generating",
          index: asNumber(data.i),
          total: asNumber(data.N),
          startedAt: event.ts,
          completedAt: undefined,
          lastAt: event.ts,
          error: undefined,
        });
        currentNodeId = nodeId;
      }
      generation = { ...generation, N: asNumber(data.N) || asNumber(generation.N) };
      stages = {
        ...stages,
        generation: { ...stages.generation, counter: generationCounter({ ...state, generation, leaves }) },
      };
    }
    if (event.type === "leaf_done") {
      const nodeId = asString(data.node_id);
      const attempts = asNumber(data.attempts) || 1;
      if (nodeId) {
        leaves = updateLeaf(leaves, nodeId, {
          state: attempts > 1 ? "retried" : "done",
          attempts,
          durationMs: asNumber(data.duration_ms),
          stories: asNumber(data.stories),
          tests: asNumber(data.tests),
          questions: asNumber(data.questions),
          completedAt: event.ts,
          lastAt: event.ts,
          error: undefined,
        });
        if (currentNodeId === nodeId) currentNodeId = null;
      }
      stages = {
        ...stages,
        generation: { ...stages.generation, counter: generationCounter({ ...state, generation, leaves }) },
      };
    }
    if (event.type === "leaf_failed") {
      const nodeId = asString(data.node_id);
      if (nodeId) {
        leaves = updateLeaf(leaves, nodeId, {
          state: "failed",
          error: asString(data.error),
          attempts: asNumber(data.attempts) || 2,
          completedAt: event.ts,
          lastAt: event.ts,
        });
        if (currentNodeId === nodeId) currentNodeId = null;
      }
      stages = {
        ...stages,
        generation: { ...stages.generation, counter: generationCounter({ ...state, generation, leaves }) },
      };
    }
    if (event.type === "stage_end") {
      generation = { ...generation, ...data };
      currentNodeId = null;
      const total = asNumber(data.leaves) || asNumber(generation.N);
      const stats = generationStats(leaves, total);
      const succeeded = asNumber(data.succeeded) || stats.ok + stats.retried;
      stages = {
        ...stages,
        generation: {
          ...stages.generation,
          counter: `${succeeded}/${total} leaves, ${stats.stories} stories`,
        },
      };
    }
  }

  if (event.type === "warning") {
    // Warnings are visible in the log; they also keep the current stage active.
  }

  if (event.type === "error") {
    error = message;
    if (key) {
      stages = { ...stages, [key]: { ...stages[key], error } };
    }
  }

  return {
    ...state,
    lastEventId: event.id,
    events: [...state.events, event],
    stages,
    leaves,
    edges,
    currentNodeId,
    ingestion,
    tree,
    graph,
    generation,
    error,
  };
}
