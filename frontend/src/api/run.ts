export type RunStage =
  | "ingestion"
  | "structure"
  | "knowledge"
  | "context"
  | "generation"
  | "review"
  | "export";

export type RunEventType =
  | "stage_start"
  | "stage_end"
  | "progress"
  | "leaf_start"
  | "leaf_done"
  | "leaf_failed"
  | "link_found"
  | "warning"
  | "error"
  | "info";

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
  "info",
];

const B = "/api/v1";

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error((await response.text()) || `Request failed (${response.status})`);
  return response.json() as Promise<T>;
}

export function fetchEvents(projectId: string, after = 0, limit = 1000): Promise<RunEvent[]> {
  const query = new URLSearchParams({ after: String(after), limit: String(limit) });
  return fetch(`${B}/projects/${projectId}/events/history?${query.toString()}`).then((r) =>
    json<RunEvent[]>(r),
  );
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
