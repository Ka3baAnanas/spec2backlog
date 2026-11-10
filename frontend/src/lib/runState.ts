import type { RunEvent, RunStage } from "../api/run";

export type ChecklistStage =
  | "ingestion"
  | "structure"
  | "knowledge"
  | "context"
  | "generation"
  | "review"
  | "export";
export type StageStatus = "pending" | "active" | "done";
export type LeafRunState = "waiting" | "embedded" | "generating" | "done" | "failed" | "retried";

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

export type RunCounts = { stories: number; tests: number; questions: number };

export type RunState = {
  lastEventId: number;
  events: RunEvent[];
  stages: Record<ChecklistStage, StageState>;
  leaves: Record<string, LeafRuntime>;
  edges: RunEdge[];
  currentSectionId: string | null;
  counts: RunCounts;
  ingestion: Record<string, unknown>;
  structure: Record<string, unknown>;
  knowledge: Record<string, unknown>;
  context: Record<string, unknown>;
  generation: Record<string, unknown>;
  error: string | null;
};

export type RunAction = { type: "reset" } | { type: "event"; event: RunEvent };

const STAGE_KEYS: ChecklistStage[] = [
  "ingestion",
  "structure",
  "knowledge",
  "context",
  "generation",
  "review",
  "export",
];

function emptyStages(): Record<ChecklistStage, StageState> {
  return {
    ingestion: { key: "ingestion", status: "pending", counter: "Waiting" },
    structure: { key: "structure", status: "pending", counter: "Waiting" },
    knowledge: { key: "knowledge", status: "pending", counter: "Waiting" },
    context: { key: "context", status: "pending", counter: "Waiting" },
    generation: { key: "generation", status: "pending", counter: "Waiting" },
    review: { key: "review", status: "pending", counter: "Waiting" },
    export: { key: "export", status: "pending", counter: "Waiting" },
  };
}

export function initialRunState(): RunState {
  return {
    lastEventId: 0,
    events: [],
    stages: emptyStages(),
    leaves: {},
    edges: [],
    currentSectionId: null,
    counts: { stories: 0, tests: 0, questions: 0 },
    ingestion: {},
    structure: {},
    knowledge: {},
    context: {},
    generation: {},
    error: null,
  };
}

function stageKey(stage: RunStage): ChecklistStage | null {
  return STAGE_KEYS.includes(stage as ChecklistStage) ? (stage as ChecklistStage) : null;
}

const asNumber = (value: unknown): number =>
  typeof value === "number" && Number.isFinite(value) ? value : Number(value) || 0;

const asString = (value: unknown): string => (typeof value === "string" ? value : "");

const asRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};

function updateLeaf(
  leaves: Record<string, LeafRuntime>,
  sectionId: string,
  patch: Partial<LeafRuntime>,
): Record<string, LeafRuntime> {
  if (!sectionId) return leaves;
  return {
    ...leaves,
    [sectionId]: { ...(leaves[sectionId] ?? { state: "waiting" }), ...patch },
  };
}

function deriveCounts(leaves: Record<string, LeafRuntime>): RunCounts {
  let stories = 0;
  let tests = 0;
  let questions = 0;
  for (const leaf of Object.values(leaves)) {
    stories += leaf.stories ?? 0;
    tests += leaf.tests ?? 0;
    questions += leaf.questions ?? 0;
  }
  return { stories, tests, questions };
}

function stageCounter(stage: ChecklistStage, data: Record<string, unknown>, fallback: string): string {
  if (!Object.keys(data).length) return fallback;
  if (stage === "ingestion") {
    return `${asNumber(data.headings)} headings, ${asNumber(data.paragraphs)} paragraphs`;
  }
  if (stage === "structure") {
    return `${asNumber(data.sections)} sections, ${asNumber(data.requirements)} requirement leaves`;
  }
  if (stage === "knowledge") {
    return `${asNumber(data.links)} links across ${asNumber(data.sections)} sections`;
  }
  if (stage === "generation") {
    return `${asNumber(data.leaves)} sections queued`;
  }
  return fallback;
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
  let currentSectionId = state.currentSectionId;
  let ingestion = state.ingestion;
  let structure = state.structure;
  let knowledge = state.knowledge;
  let context = state.context;
  let generation = state.generation;
  let error = state.error;

  if (key) {
    const current = stages[key];
    if (event.type === "stage_start") {
      error = null;
      stages = {
        ...stages,
        [key]: {
          ...current,
          status: "active",
          startedAt: current.startedAt ?? event.ts,
          error: undefined,
        },
      };
    } else if (event.type === "stage_end") {
      stages = {
        ...stages,
        [key]: {
          ...current,
          status: "done",
          endedAt: event.ts,
          counter: stageCounter(key, data, current.counter),
        },
      };
    }
  }

  if (event.stage === "ingestion") {
    ingestion = { ...ingestion, ...data };
    if (event.type !== "stage_start") {
      stages = {
        ...stages,
        ingestion: { ...stages.ingestion, counter: stageCounter("ingestion", ingestion, stages.ingestion.counter) },
      };
    }
  }

  if (event.stage === "structure") {
    structure = { ...structure, ...data };
    if (event.type !== "stage_start") {
      stages = {
        ...stages,
        structure: { ...stages.structure, counter: stageCounter("structure", structure, stages.structure.counter) },
      };
    }
  }

  if (event.stage === "knowledge") {
    knowledge = { ...knowledge, ...data };
    if (event.type === "progress") {
      const sectionId = asString(data.section_id);
      if (sectionId) {
        leaves = updateLeaf(leaves, sectionId, { state: "embedded", lastAt: event.ts });
        currentSectionId = sectionId;
      }
    }
    if (event.type === "link_found") {
      const source = asString(data.source_id);
      const target = asString(data.target_id);
      const kind = asString(data.kind) || "similarity";
      if (source && target) {
        const nextEdge: RunEdge = {
          id: `${event.id}:${source}->${target}:${kind}`,
          source,
          target,
          kind,
          score: asNumber(data.score),
          eventId: event.id,
        };
        const at = edges.findIndex(
          (edge) => edge.source === source && edge.target === target && edge.kind === kind,
        );
        edges = at >= 0 ? edges.map((edge, index) => (index === at ? nextEdge : edge)) : [...edges, nextEdge];
      }
    }
    if (event.type !== "stage_start") {
      stages = {
        ...stages,
        knowledge: {
          ...stages.knowledge,
          counter:
            edges.length > 0
              ? `${edges.length} links`
              : stageCounter("knowledge", knowledge, stages.knowledge.counter),
        },
      };
    }
  }

  if (event.stage === "context") {
    context = { ...context, ...data };
  }

  if (event.stage === "generation") {
    if (event.type === "stage_start") {
      generation = { ...generation, ...data };
      currentSectionId = null;
      stages = {
        ...stages,
        generation: {
          ...stages.generation,
          counter: `${asNumber(data.N)} sections queued${data.only_failed ? " · retry" : ""}`,
        },
      };
    }
    if (event.type === "leaf_start") {
      const sectionId = asString(data.section_id) || asString(data.node_id);
      if (sectionId) {
        leaves = updateLeaf(leaves, sectionId, {
          state: "generating",
          index: asNumber(data.i),
          total: asNumber(data.N),
          startedAt: event.ts,
          completedAt: undefined,
          lastAt: event.ts,
          error: undefined,
        });
        currentSectionId = sectionId;
      }
      generation = { ...generation, N: asNumber(data.N) || asNumber(generation.N) };
      stages = {
        ...stages,
        generation: {
          ...stages.generation,
          counter: `${Object.values(leaves).filter((leaf) => ["done", "retried", "failed"].includes(leaf.state)).length}/${asNumber(generation.N)} sections`,
        },
      };
    }
    if (event.type === "leaf_done") {
      const sectionId = asString(data.section_id) || asString(data.node_id);
      const attempts = asNumber(data.attempts) || 1;
      if (sectionId) {
        leaves = updateLeaf(leaves, sectionId, {
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
        if (currentSectionId === sectionId) currentSectionId = null;
      }
      stages = {
        ...stages,
        generation: {
          ...stages.generation,
          counter: `${Object.values(leaves).filter((leaf) => ["done", "retried", "failed"].includes(leaf.state)).length}/${asNumber(generation.N)} sections`,
        },
      };
    }
    if (event.type === "leaf_failed") {
      const sectionId = asString(data.section_id) || asString(data.node_id);
      if (sectionId) {
        leaves = updateLeaf(leaves, sectionId, {
          state: "failed",
          error: asString(data.error),
          attempts: asNumber(data.attempts) || 2,
          completedAt: event.ts,
          lastAt: event.ts,
        });
        if (currentSectionId === sectionId) currentSectionId = null;
      }
    }
    if (event.type === "stage_end") {
      generation = { ...generation, ...data };
      currentSectionId = null;
      stages = {
        ...stages,
        generation: {
          ...stages.generation,
          counter: `${asNumber(data.succeeded)}/${asNumber(data.leaves)} sections · ${asNumber(data.stories)} stories`,
        },
      };
    }
  }

  if (event.type === "error") {
    error = message;
    if (key) stages = { ...stages, [key]: { ...stages[key], error } };
  }

  return {
    ...state,
    lastEventId: event.id,
    events: [...state.events, event],
    stages,
    leaves,
    edges,
    currentSectionId,
    counts: deriveCounts(leaves),
    ingestion,
    structure,
    knowledge,
    context,
    generation,
    error,
  };
}

export type GenerationStats = {
  ok: number;
  retried: number;
  failed: number;
  completed: number;
  total: number;
  stories: number;
  tests: number;
  questions: number;
  averageDurationMs: number | null;
};

export function selectGenerationStats(state: RunState, totalLeaves: number): GenerationStats {
  const total = totalLeaves || asNumber(state.generation.N) || 0;
  let ok = 0;
  let retried = 0;
  let failed = 0;
  let durationMs = 0;
  let durations = 0;
  for (const leaf of Object.values(state.leaves)) {
    if (leaf.state === "done") ok += 1;
    if (leaf.state === "retried") retried += 1;
    if (leaf.state === "failed") failed += 1;
    const completed = ["done", "retried", "failed"].includes(leaf.state);
    if (completed) {
      const measured = leaf.durationMs ?? 0;
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
    stories: state.counts.stories,
    tests: state.counts.tests,
    questions: state.counts.questions,
    averageDurationMs: durations ? durationMs / durations : null,
  };
}
