import { useCallback, useEffect, useState } from "react";
import { request, type Workspace, type Run, type Source, type Investigation } from "../api/client";

export function useWorkspace(workspace: Workspace | null) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    if (!workspace) return;
    try {
      const [r, s, i] = await Promise.all([
        request<Run[]>("/runs", {}, workspace), request<Source[]>("/sources", {}, workspace),
        request<Investigation[]>("/investigations", {}, workspace)
      ]);
      setRuns(r); setSources(s); setInvestigations(i);
    } catch (e) { setError(String(e)); }
  }, [workspace]);
  useEffect(() => { void refresh(); const timer = setInterval(() => void refresh(), 2000); return () => clearInterval(timer); }, [refresh]);
  async function action(fn: () => Promise<unknown>) {
    try { setError(""); await fn(); await refresh(); } catch (e) { setError(String(e)); }
  }
  return {runs, sources, investigations, error, setError, refresh, action};
}
