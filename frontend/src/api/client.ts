import type { components } from "./schema";
export type Spec = components["schemas"]["ExperimentSpec"];
export type Run = components["schemas"]["RunView"];
export type Comparison = components["schemas"]["ComparisonView"];
export type Evidence = components["schemas"]["EvidenceChunk"];
export type Workspace = { id: string; name: string; token: string };
export type Source = components["schemas"]["SourceView"];
export type Investigation = components["schemas"]["InvestigationView"];
export async function request<T>(path: string, options: RequestInit = {}, workspace?: Workspace): Promise<T> {
  const response = await fetch(workspace ? `/api/workspaces/${workspace.id}${path}` : path, {
    ...options, headers: {
      ...(options.body instanceof FormData ? {} : {"Content-Type": "application/json"}),
      ...(workspace ? {Authorization: `Bearer ${workspace.token}`} : {}), ...options.headers
    }
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(`${error.message || JSON.stringify(error.detail) || response.statusText}${error.correlation_id ? ` · ${error.correlation_id}` : ""}`);
  }
  if (!response.headers.get("content-type")?.includes("application/json")) {
    throw new Error("The API is unavailable or not configured. A free hosted backend may need a minute to wake up; retry shortly.");
  }
  return response.json();
}
export const post = (body: unknown): RequestInit => ({method: "POST", body: JSON.stringify(body)});
export async function download(workspace: Workspace, id: string, filename: string) {
  const response = await fetch(`/api/workspaces/${workspace.id}/artifacts/${id}`, {headers: {Authorization: `Bearer ${workspace.token}`}});
  if (!response.ok) throw new Error("Artifact unavailable");
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
