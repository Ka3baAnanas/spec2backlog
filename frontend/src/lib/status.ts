import type { ChipTone } from "../components/Chip";

type Meta = { label: string; tone: ChipTone };

export function projectStatusMeta(status: string): Meta {
  switch (status) {
    case "created":
      return { label: "Draft", tone: "default" };
    case "ingested":
      return { label: "Ingested", tone: "blue" };
    case "graph_built":
      return { label: "Graph built", tone: "blue" };
    case "generated":
      return { label: "Generated", tone: "amber" };
    case "validated":
      return { label: "Validated", tone: "green" };
    case "exported":
      return { label: "Exported", tone: "green" };
    default:
      return { label: status.replace(/_/g, " "), tone: "default" };
  }
}

export function itemStatusMeta(status: string): Meta {
  switch (status) {
    case "approved":
      return { label: "Approved", tone: "green" };
    case "edited":
      return { label: "Edited", tone: "amber" };
    case "rejected":
      return { label: "Rejected", tone: "red" };
    case "proposed":
      return { label: "Proposed", tone: "yellow" };
    default:
      return { label: status, tone: "default" };
  }
}

export function kindMeta(kind: string): Meta {
  switch (kind) {
    case "epic":
      return { label: "Epic", tone: "yellow" };
    case "story":
      return { label: "Story", tone: "blue" };
    case "test":
      return { label: "Test", tone: "outline" };
    default:
      return { label: kind, tone: "default" };
  }
}

const PROJECT_ORDER = ["created", "ingested", "graph_built", "generated", "validated", "exported"];

export function projectRank(status: string): number {
  const index = PROJECT_ORDER.indexOf(status);
  return index < 0 ? 0 : index;
}
