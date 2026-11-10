export type Project = { id: string; name: string; status: string; checklist: { found: string[]; missing: string[] } };
export type Node = { id: string; parent_id: string | null; number: string; title: string; level: number; is_leaf: boolean; is_global: boolean; is_front_matter: boolean; lineage: string[]; text: string };
export type Item = { id: string; kind: "epic" | "story" | "test"; title: string; parent_item_id: string | null; source_node_id: string; status: string; body: any; questions: string[] };

async function serverError(response: Response): Promise<string> {
  const fallback = `Request failed (${response.status})`;
  let text = "";
  try {
    text = await response.text();
  } catch {
    return fallback;
  }
  if (!text.trim()) return fallback;
  try {
    const payload = JSON.parse(text) as Record<string, unknown>;
    const detail = payload.detail ?? payload.error ?? payload.message;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((entry) => {
          if (typeof entry === "string") return entry;
          if (entry && typeof entry === "object" && "msg" in entry) {
            return String((entry as { msg: unknown }).msg);
          }
          return JSON.stringify(entry);
        })
        .join("; ");
    }
  } catch {
    // Plain-text proxy/server errors are already useful as-is.
  }
  return text;
}

const j = async (r: Response) => {
  if (!r.ok) throw new Error(await serverError(r));
  return r.json();
};
const B = "/api/v1";
export const api = {
  projects: (): Promise<Project[]> => fetch(`${B}/projects`).then(j),
  upload: (name: string, file: File): Promise<Project> => { const f = new FormData(); f.append("name", name); f.append("file", file); return fetch(`${B}/projects/upload`, { method: "POST", body: f }).then(j); },
  tree: (id: string): Promise<Node[]> => fetch(`${B}/projects/${id}/tree`).then(j),
  buildGraph: (id: string) => fetch(`${B}/projects/${id}/graph`, { method: "POST" }).then(j),
  generate: (id: string) => fetch(`${B}/projects/${id}/generate`, { method: "POST" }).then(j),
  items: (id: string): Promise<Item[]> => fetch(`${B}/projects/${id}/items`).then(j),
  review: (iid: string, patch: Partial<Item>) => fetch(`${B}/items/${iid}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) }).then(j),
  exportUrl: (id: string) => `${B}/projects/${id}/export.xlsx`,
};
