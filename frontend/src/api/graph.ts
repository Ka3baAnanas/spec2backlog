export type Edge = {
  source: string;
  target: string;
  kind: string;
  score: number;
};

export function fetchGraph(projectId: string): Promise<Edge[]> {
  return fetch(`/api/v1/projects/${projectId}/graph`).then((response) => {
    if (!response.ok) throw new Error(`Could not load the meaning graph (${response.status})`);
    return response.json() as Promise<Edge[]>;
  });
}
