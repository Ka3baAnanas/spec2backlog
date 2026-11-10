export type RunStage = "ingestion" | "tree" | "graph" | "generation" | "export";

export type RunEventType =
  | "stage_start"
  | "stage_end"
  | "progress"
  | "leaf_start"
  | "leaf_done"
  | "leaf_failed"
  | "link_found"
  | "warning"
  | "error";

export type RunEvent = {
  id: number;
  project_id: string;
  ts: string;
  stage: RunStage;
  type: RunEventType;
  message: string;
  data: Record<string, unknown>;
};

export const RUN_EVENT_TYPES: RunEventType[] = [
  "stage_start",
  "stage_end",
  "progress",
  "leaf_start",
  "leaf_done",
  "leaf_failed",
  "link_found",
  "warning",
  "error",
];

export type TraceNeighbour = {
  node_id: string;
  number: string;
  title: string;
  score: number;
  kind: string;
};

export type GenerationTrace = {
  id: number;
  project_id: string;
  node_id: string;
  prompt: string;
  response_json: unknown;
  neighbours: TraceNeighbour[];
  global_context_ids: string[];
  duration_ms: number;
  attempts: number;
  status: "ok" | "failed" | "retried";
  error: string | null;
  items_created: { epics: number; stories: number; tests: number; questions: number };
};

const B = "/api/v1";

const json = async (response: Response) => {
  if (!response.ok) throw new Error((await response.text()) || `Request failed (${response.status})`);
  return response.json();
};

export function fetchEvents(projectId: string, after = 0, limit = 1000): Promise<RunEvent[]> {
  const query = new URLSearchParams({ after: String(after), limit: String(limit) });
  return fetch(`${B}/projects/${projectId}/events.json?${query.toString()}`).then(json);
}

export async function fetchAllEvents(projectId: string): Promise<RunEvent[]> {
  const events: RunEvent[] = [];
  let after = 0;
  while (true) {
    const batch = await fetchEvents(projectId, after, 5000);
    events.push(...batch);
    if (batch.length < 5000) break;
    after = batch[batch.length - 1]?.id ?? after;
  }
  return events;
}

export function runPipeline(projectId: string, stages = "graph,generate"): Promise<{ run_id: string }> {
  return fetch(`${B}/projects/${projectId}/run?stages=${encodeURIComponent(stages)}`, {
    method: "POST",
  }).then(json);
}

export function retryFailedLeaves(projectId: string): Promise<{ items: number }> {
  return fetch(`${B}/projects/${projectId}/generate?only_failed=true`, {
    method: "POST",
  }).then(json);
}

export function fetchTrace(projectId: string, nodeId: string): Promise<GenerationTrace> {
  return fetch(`${B}/projects/${projectId}/leaves/${nodeId}/trace`).then(json);
}
