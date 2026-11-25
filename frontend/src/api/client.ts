export type Checklist = { found: string[]; missing: string[] };

export type Project = {
  id: string;
  name: string;
  status: string;
  error: string | null;
  checklist: Checklist;
  context_approved: boolean;
  created_at: string | null;
};

export type PreviewBlock = { kind: string; text: string; level: number };
export type DocumentBlock = PreviewBlock;

export type DocumentStats = {
  blocks?: number;
  paragraphs?: number;
  tables?: number;
  headings?: number;
  list_items?: number;
  skipped_toc?: number;
  warnings?: number;
  characters?: number;
  preview?: PreviewBlock[];
};

export type ProjectDocument = {
  id: string;
  project_id: string;
  version: number;
  filename: string;
  stats: DocumentStats;
  warnings: string[];
  checklist: Checklist;
  blocks: DocumentBlock[];
  skipped: string[];
  created_at: string | null;
};

export type SectionRole = "requirement" | "context" | "glossary" | "front_matter" | "ignored";

export type Section = {
  id: string;
  project_id: string;
  parent_id: string | null;
  number: string;
  title: string;
  text: string;
  level: number;
  position: number;
  is_leaf: boolean;
  role: SectionRole;
  source: "document" | "manual";
  extra_instructions: string;
  lineage: string[];
};

export type LinkKind = "similarity" | "reference" | "lexical" | "manual";

export type ProjectLink = {
  id: number;
  project_id: string;
  source_id: string;
  target_id: string;
  kind: LinkKind;
  score: number;
  reason: string;
  enabled: boolean;
};

export type ContextSection = {
  section_id: string;
  number: string;
  title: string;
  text: string;
  role: SectionRole;
  source?: "document" | "manual";
  extra_instructions?: string;
  lineage: string[];
};

export type GlossaryItem = { term: string; definition: string; kind: string };

export type ContextData = {
  section: ContextSection;
  lineage: string[];
  text: string;
  links: ContextSection[];
  linked_sections: ContextSection[];
  global_context: ContextSection[];
  glossary: GlossaryItem[];
  dropped?: { linked_sections: string[]; global_context: string[] };
  budget?: { max_tokens: number };
};

export type ContextPack = {
  section_id: string;
  section: ContextSection;
  context: ContextData;
  prompt: string;
  instructions: string;
  tokens: number;
  links: ContextSection[];
};

export type ItemStatus = "proposed" | "approved" | "edited" | "rejected";

export type StoryBody = {
  as_a?: string;
  i_want?: string;
  so_that?: string;
  persona?: string;
  goal?: string;
  benefit?: string;
  description?: string;
  business_rules?: string[];
  acceptance_criteria?: string[];
  priority?: string;
  priority_reason?: string;
  estimate?: string;
  dependencies?: string[];
  source_evidence?: string[];
  ambiguity_flag?: boolean;
  quality?: Record<string, boolean>;
  merged_from?: string[];
  section_id?: string;
  regeneration_instruction?: string;
  [key: string]: unknown;
};

export type TestBody = {
  steps?: string[];
  expected?: string;
  story_title?: string;
  [key: string]: unknown;
};

export type BacklogItem = {
  id: string;
  project_id: string;
  key: string;
  kind: "epic" | "feature" | "story" | "test";
  parent_item_id: string | null;
  source_section_id: string;
  source_sections: string[];
  title: string;
  body: Record<string, unknown>;
  status: ItemStatus;
  confidence: number;
  questions: string[];
};

export type FeatureBody = { summary?: string; [key: string]: unknown };
export type StoryNode = BacklogItem & { body: StoryBody; tests: BacklogItem[] };
export type FeatureNode = BacklogItem & { body: FeatureBody; stories: StoryNode[] };
export type EpicNode = BacklogItem & { body: FeatureBody; features: FeatureNode[]; stories: StoryNode[] };

export type BacklogResponse = {
  project_id: string;
  epics: EpicNode[];
  stats: {
    epics: number;
    features: number;
    stories: number;
    tests: number;
    by_status: Record<string, number>;
    total: number;
  };
};

export type Question = {
  id: string;
  project_id: string;
  section_id: string;
  text: string;
  answer: string;
  status: "open" | "answered" | "ignored";
  priority: "Blocking" | "Important" | "Minor";
  created_at: string | null;
};

export type CoverageStory = {
  id: string;
  key: string;
  title: string;
  status: ItemStatus;
  tests: { id: string; key: string; title: string; status: ItemStatus }[];
};

export type CoverageRow = {
  section_id: string;
  number: string;
  title: string;
  role: SectionRole;
  stories: CoverageStory[];
  covered: boolean;
};

export type Coverage = {
  project_id: string;
  rows: CoverageRow[];
  coverage: number;
  stats: {
    requirement_sections: number;
    covered_sections: number;
    stories: number;
    tests: number;
  };
};

export type AskCitation = {
  section_id: string;
  number: string;
  title: string;
  score: number;
  snippet: string;
};

export type AskResponse = { answer: string; citations: AskCitation[] };

export type PipelineStatus = {
  project_id: string;
  status: string;
  context_approved: boolean;
  error: string | null;
  progress: {
    sections: number;
    requirement_sections: number;
    links: number;
    items: number;
    questions: number;
    traces: number;
  };
  run: {
    run_id: string;
    status: string;
    only_failed: boolean;
    started_at: string;
    finished_at: string | null;
  } | null;
};

export type ItemTrace = {
  item_id: string;
  section_id: string;
  prompt: string;
  response_json: unknown;
  links: ContextSection[];
  global_context_ids: string[];
  duration_ms: number;
  attempts: number;
  status: string;
  error: string | null;
  items_created: Record<string, number>;
};

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

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(await serverError(response));
  return response.json() as Promise<T>;
}

const B = "/api/v1";

export const api = {
  projects: (): Promise<Project[]> => fetch(`${B}/projects`).then((r) => json(r)),
  project: (id: string): Promise<Project> => fetch(`${B}/projects/${id}`).then((r) => json(r)),
  upload: (name: string, file: File): Promise<Project> => {
    const form = new FormData();
    form.append("name", name);
    form.append("file", file);
    return fetch(`${B}/projects`, { method: "POST", body: form }).then((r) => json(r));
  },
  deleteProject: (id: string): Promise<{ deleted: boolean }> =>
    fetch(`${B}/projects/${id}`, { method: "DELETE" }).then((r) => json(r)),

  document: (id: string): Promise<ProjectDocument> =>
    fetch(`${B}/projects/${id}/document`).then((r) => json(r)),
  sections: (id: string): Promise<Section[]> =>
    fetch(`${B}/projects/${id}/sections`).then((r) => json(r)),
  patchSection: (
    id: string,
    patch: { role?: SectionRole; title?: string; extra_instructions?: string },
  ): Promise<Section> =>
    fetch(`${B}/sections/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }).then((r) => json(r)),

  createManualContext: (projectId: string, payload: { title: string; text: string }): Promise<Section> =>
    fetch(`${B}/projects/${projectId}/manual-context`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then((r) => json(r)),
  updateManualContext: (
    sectionId: string,
    payload: { title?: string; text?: string },
  ): Promise<Section> =>
    fetch(`${B}/sections/${sectionId}/manual-context`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then((r) => json(r)),
  deleteManualContext: (sectionId: string): Promise<{ deleted: boolean; id: string }> =>
    fetch(`${B}/sections/${sectionId}/manual-context`, { method: "DELETE" }).then((r) => json(r)),

  links: (id: string): Promise<ProjectLink[]> =>
    fetch(`${B}/projects/${id}/links`).then((r) => json(r)),
  patchLink: (id: number, patch: { enabled?: boolean; reason?: string; score?: number }): Promise<ProjectLink> =>
    fetch(`${B}/links/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }).then((r) => json(r)),

  context: (sectionId: string): Promise<ContextPack> =>
    fetch(`${B}/sections/${sectionId}/context`).then((r) => json(r)),

  prepare: (id: string): Promise<Record<string, unknown>> =>
    fetch(`${B}/projects/${id}/pipeline/prepare`, { method: "POST" }).then((r) => json(r)),
  approveContext: (id: string): Promise<Record<string, unknown>> =>
    fetch(`${B}/projects/${id}/pipeline/approve-context`, { method: "POST" }).then((r) => json(r)),
  generate: (id: string): Promise<{ run_id: string; status: string }> =>
    fetch(`${B}/projects/${id}/pipeline/generate`, { method: "POST" }).then((r) => json(r)),
  retryFailed: (id: string): Promise<{ run_id: string; status: string }> =>
    fetch(`${B}/projects/${id}/pipeline/retry-failed`, { method: "POST" }).then((r) => json(r)),
  pipelineStatus: (id: string): Promise<PipelineStatus> =>
    fetch(`${B}/projects/${id}/pipeline/status`).then((r) => json(r)),

  eventsHistory: (id: string, after = 0): Promise<unknown[]> =>
    fetch(`${B}/projects/${id}/events/history?after=${after}`).then((r) => json(r)),

  backlog: (id: string): Promise<BacklogResponse> =>
    fetch(`${B}/projects/${id}/backlog`).then((r) => json(r)),
  patchItem: (
    id: string,
    patch: { title?: string; body?: Record<string, unknown>; status?: ItemStatus; by?: string },
  ): Promise<BacklogItem> =>
    fetch(`${B}/items/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }).then((r) => json(r)),
  regenerateItem: (id: string, instruction: string): Promise<BacklogItem> =>
    fetch(`${B}/items/${id}/regenerate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instruction }),
    }).then((r) => json(r)),
  itemTrace: (id: string): Promise<ItemTrace> =>
    fetch(`${B}/items/${id}/trace`).then((r) => json(r)),
  approveBacklog: (id: string): Promise<{ approved: number; status: string }> =>
    fetch(`${B}/projects/${id}/backlog/approve`, { method: "POST" }).then((r) => json(r)),

  questions: (id: string): Promise<Question[]> =>
    fetch(`${B}/projects/${id}/questions`).then((r) => json(r)),
  patchQuestion: (
    id: string,
    patch: { answer?: string; status?: "open" | "answered" | "ignored" },
  ): Promise<Question> =>
    fetch(`${B}/questions/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }).then((r) => json(r)),

  coverage: (id: string): Promise<Coverage> =>
    fetch(`${B}/projects/${id}/coverage`).then((r) => json(r)),

  exportUrl: (id: string, format: "xlsx" | "docx" | "csv" | "jira" | "azure" = "xlsx"): string =>
    `${B}/projects/${id}/export?format=${format}`,
  exportFile: async (id: string, format: "xlsx" | "docx" | "csv"): Promise<Blob> => {
    const response = await fetch(`${B}/projects/${id}/export?format=${format}`);
    if (!response.ok) throw new Error(await serverError(response));
    return response.blob();
  },

  ask: (id: string, question: string): Promise<AskResponse> =>
    fetch(`${B}/projects/${id}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }).then((r) => json(r)),
};
