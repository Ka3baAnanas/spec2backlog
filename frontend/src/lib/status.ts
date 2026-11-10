import type { ChipTone } from "../components/Chip";

type Meta = { label: string; tone: ChipTone };

export function projectStatusMeta(status: string): Meta {
  switch (status) {
    case "uploaded":
      return { label: "Uploaded", tone: "default" };
    case "parsed":
      return { label: "Parsed", tone: "blue" };
    case "structured":
      return { label: "Structured", tone: "blue" };
    case "linked":
      return { label: "Linked", tone: "blue" };
    case "awaiting_context_approval":
      return { label: "Context to approve", tone: "yellow" };
    case "generating":
      return { label: "Generating", tone: "amber" };
    case "generated":
      return { label: "Generated", tone: "amber" };
    case "in_review":
      return { label: "In review", tone: "yellow" };
    case "approved":
      return { label: "Approved", tone: "green" };
    case "exported":
      return { label: "Exported", tone: "green" };
    case "failed":
      return { label: "Failed", tone: "red" };
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

export type RoleMeta = Meta & { description: string };

export function roleMeta(role: string): RoleMeta {
  switch (role) {
    case "requirement":
      return { label: "Requirement", tone: "yellow", description: "Generated into backlog items" };
       case "context":
      return { label: "Context", tone: "blue", description: "Sent as global context" };
    case "glossary":
      return { label: "Glossary", tone: "green", description: "Terms and actors" };
    case "front_matter":
      return { label: "Front matter", tone: "outline", description: "Never sent to the model" };
    case "ignored":
      return { label: "Ignored", tone: "default", description: "Skipped by generation" };
    default:
      return { label: role, tone: "default", description: "" };
  }
}

const PROJECT_ORDER = [
  "uploaded",
  "parsed",
  "structured",
  "linked",
  "awaiting_context_approval",
  "generating",
  "generated",
  "in_review",
  "approved",
  "exported",
];

export function projectRank(status: string): number {
  const index = PROJECT_ORDER.indexOf(status);
  return index < 0 ? 0 : index;
}

export function isTerminalStatus(status: string): boolean {
  return ["generated", "in_review", "approved", "exported", "failed"].includes(status);
}

