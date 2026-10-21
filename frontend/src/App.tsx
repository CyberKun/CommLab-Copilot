import { useEffect, useState } from "react";
import { request, post, download, type Workspace, type Spec, type Comparison } from "./api/client";
import { useWorkspace } from "./features/useWorkspace";
import { ConfigForm, defaultSpec } from "./features/ConfigForm";
import { BerChart } from "./features/BerChart";
import { Investigator } from "./features/Investigator";

export default function App() {
  const [workspace, setWorkspace] = useState<Workspace | null>(() => JSON.parse(sessionStorage.getItem("commlab.workspace") || "null"));
  const [name, setName] = useState("Wireless communications lab");
  const [spec, setSpec] = useState<Spec>(defaultSpec);
  const [selected, setSelected] = useState<string[]>([]);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [settings, setSettings] = useState("");
  const state = useWorkspace(workspace);
  useEffect(() => {
    if (workspace) void request<{llm:string}>("/settings", {}, workspace)
      .then(s => setSettings(s.llm.startsWith("offline_rules") ? "Offline rules · no LLM connected" : `Model: ${s.llm}`))
      .catch(() => setSettings("Provider status unavailable"));
  }, [workspace]);
  const chartRuns = selected.length ? state.runs.filter(r => selected.includes(r.id)) : state.runs.filter(r => r.result).slice(0,1);
  function connect(w: Workspace) {sessionStorage.setItem("commlab.workspace", JSON.stringify(w)); setWorkspace(w);}
  return <div className="shell">
    <aside className="sidebar"><div className="brand"><span className="brand-icon">∿</span><span>CommLab<strong>Copilot</strong></span></div>
      <div className="sidebar-label">EXPERIMENT WORKSPACE</div><a href="#workspace" className="nav active">◈ &nbsp; Wireless lab</a>
      <a href="#sources" className="nav">▤ &nbsp; Reference library</a><a href="#investigator" className="nav">✧ &nbsp; Investigations</a>
      <div className="sidebar-bottom"><span className="dot"/> Research workspace<p>BPSK / AWGN / Rayleigh<br/>Reproducible by design.</p></div>
    </aside>
    <main id="workspace"><header><div><span className="eyebrow">WIRELESS COMMUNICATIONS / LAB 01</span><h1>Evidence meets experiment.</h1>
      <p className="muted">A traceable path from your handout to a verified BER curve.</p></div><span className="version">MVP · 0.1</span></header>
      {state.error && <div role="alert" className="error">{state.error}<button className="text-button" onClick={() => state.setError("")}>Dismiss</button></div>}
      {!workspace ? <section className="panel onboarding"><h2>Open your experiment workspace</h2><p>Create an isolated workspace to upload references, run simulations, and investigate results.</p>
        <form onSubmit={e => {e.preventDefault(); void state.action(async () => connect(await request<Workspace>("/api/workspaces", post({name}))));}}>
          <label>Workspace name<input required maxLength={100} value={name} onChange={e => setName(e.target.value)}/></label><button>Create workspace →</button></form>
        <p className="caption">Your access token is stored for this browser session. Export it after creation to reconnect later.</p>
        <details><summary>Reconnect with a saved workspace credential</summary><input type="file" accept=".json" onChange={e => {
          const file=e.target.files?.[0]; if(file) void state.action(async () => {const w=JSON.parse(await file.text()) as Workspace;
            await request("/runs", {}, w); connect(w);});}}/></details>
      </section> : <>
        <div className="workspace-strip"><strong>{workspace.name}</strong><span className="caption">{workspace.id.slice(0,8)}</span>
          <button className="text-button" onClick={() => {const url=URL.createObjectURL(new Blob([JSON.stringify(workspace)], {type:"application/json"}));
            const a=document.createElement("a"); a.href=url; a.download="commlab-credential.json"; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);}}>Export access credential</button>
          {settings && <span className="badge">{settings}</span>}
        </div>
        <div className="stats"><div><span>REFERENCE MATERIAL</span><strong>{state.sources.filter(s=>s.status==="ready").length}<small>sources ready</small></strong></div>
          <div><span>EXPERIMENT HISTORY</span><strong>{state.runs.length}<small>saved runs</small></strong></div>
          <div><span>EXECUTION</span><strong>{state.runs.filter(r=>["queued","running"].includes(r.status)).length}<small>active jobs</small></strong></div>
          <div><span>SCIENTIFIC SCOPE</span><strong>BPSK<small>2 channel models</small></strong></div></div>
        <div className="experiment-layout"><section className="panel"><div className="panel-heading"><div><span className="eyebrow">01 / CONFIGURE</span><h2>Design a sweep</h2></div></div>
          <form onSubmit={e => {e.preventDefault(); void state.action(async () => {
            const run=await request<{id:string}>("/runs", {...post(spec), headers: {"Idempotency-Key": crypto.randomUUID()}}, workspace); setSelected([run.id]);});}}>
            <ConfigForm value={spec} onChange={setSpec}/><button className="full" type="submit">Run reviewed configuration <span>→</span></button></form></section>
          <section className="panel"><div className="panel-heading"><div><span className="eyebrow">02 / OBSERVE</span><h2>Performance at a glance</h2></div><span className="badge">BER vs Eb/N0</span></div>
            <BerChart runs={chartRuns}/></section></div>
        <section className="panel"><div className="panel-heading"><div><span className="eyebrow">03 / VERIFY</span><h2>Run history</h2></div>
          <button className="secondary" disabled={selected.length!==2} onClick={() => void state.action(async () => setComparison(await request("/compare", post({left:selected[0], right:selected[1]}), workspace)))}>Compare selected ({selected.length}/2)</button></div>
          <div className="table-scroll"><table><thead><tr><th>Select</th><th>Run / channel</th><th>Seed</th><th>Bits / point</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody>{state.runs.map(run => <tr key={run.id}><td><input type="checkbox" aria-label={`Select run ${run.id}`} checked={selected.includes(run.id)}
              onChange={e => {setComparison(null); setSelected(e.target.checked ? [...selected.slice(-1),run.id] : selected.filter(id=>id!==run.id));}}/></td>
              <td><strong>{run.spec.channel.toUpperCase()}</strong><small className="mono">{run.id.slice(0,8)}</small></td><td>{run.spec.seed}</td><td>{run.spec.bits_per_point.toLocaleString()}</td>
              <td><span className={`status ${run.status}`}>{run.status}</span>{["queued","running"].includes(run.status)&&<progress max={1} value={run.progress}/>}
                {run.error && <small className="warning">{run.error.message as string}</small>}</td>
              <td><button className="text-button" onClick={() => {setSpec(run.spec); window.scrollTo({top:0,behavior:"smooth"});}}>Reproduce</button>
                {["queued","running"].includes(run.status)&&<button className="text-button" onClick={() => void state.action(()=>request(`/runs/${run.id}/cancel`,post({}),workspace))}>Cancel</button>}
                {run.artifact_id&&<button className="text-button" onClick={() => void state.action(()=>download(workspace,run.artifact_id!,`run-${run.id}.json`))}>JSON ↓</button>}
                {run.plot_artifact_id&&<button className="text-button" onClick={() => void state.action(()=>download(workspace,run.plot_artifact_id!,`run-${run.id}.svg`))}>SVG ↓</button>}</td></tr>)}</tbody></table></div>
          {!state.runs.length&&<p className="muted">No runs yet. Submit the configuration above to begin.</p>}
          {comparison&&<div className="review"><h3>Side-by-side comparison</h3><div className="table-scroll"><table><thead><tr><th>Parameter</th><th>{comparison.left.id.slice(0,8)}</th><th>{comparison.right.id.slice(0,8)}</th></tr></thead><tbody>
            {(["channel","seed","bits_per_point","ebn0_db","receiver"] as const).map(key=><tr key={key}><td>{({channel:"Channel",seed:"Seed",bits_per_point:"Bits per point",ebn0_db:"Eb/N0 (dB)",receiver:"Receiver"})[key]}{key in comparison.changes ? " · changed" : ""}</td><td>{String(comparison.left.spec[key])}</td><td>{String(comparison.right.spec[key])}</td></tr>)}
          </tbody></table></div><p>{comparison.interpretation}</p></div>}
          {chartRuns.map(run=><details key={run.id} className="results" open><summary>{run.spec.channel.toUpperCase()} · {run.id.slice(0,8)} · measurements & verification</summary>
            {run.findings.map((f,i)=><p className={f.severity==="warning"?"warning":"finding"} key={i}>{String(f.message)}</p>)}
            {run.result&&<div className="table-scroll"><table><thead><tr><th>Eb/N0 (dB)</th><th>Errors / bits</th><th>Measured BER</th><th>Theory</th><th>Exact 95% interval</th></tr></thead><tbody>
              {run.result.points.map(p=><tr key={p.ebn0_db}><td>{p.ebn0_db}</td><td>{p.errors} / {p.bits}</td><td>{p.ber.toExponential(4)}</td><td>{p.theory.toExponential(4)}</td><td>{p.ci_low.toExponential(3)} – {p.ci_high.toExponential(3)}</td></tr>)}</tbody></table>
              <p className="caption">Implementation {run.result.implementation} · {JSON.stringify(run.result.runtime)}</p></div>}</details>)}
        </section>
        <div className="knowledge-layout"><section id="sources" className="panel"><span className="eyebrow">REFERENCE LIBRARY</span><h2>Ground it in evidence.</h2>
          <p className="muted">PDF, Markdown or plain text. Up to 2 MB. Sources remain versioned and downloadable.</p>
          <label className="upload">＋ Upload a handout<input aria-label="Upload reference" type="file" accept=".pdf,.txt,.md" onChange={e => {const file=e.target.files?.[0];
            if(file) void state.action(async () => {const form=new FormData(); form.append("file",file); await request("/sources",{method:"POST",body:form},workspace);}); e.target.value="";}}/></label>
          {state.sources.map(s=><div className="source" key={s.id}><div className="row"><strong>{s.title}</strong><span className={`status ${s.status}`}>{s.status}</span></div>
            {s.error&&<p className="warning">{s.error}</p>}{s.warnings.map(w=><p className="warning" key={w}>{w}</p>)}
            <button className="text-button" onClick={()=>void state.action(()=>download(workspace,s.artifact_id,s.title))}>Open stored source ↓</button></div>)}
        </section><div id="investigator"><Investigator workspace={workspace} items={state.investigations} action={state.action}/></div></div>
      </>}
      <footer>CommLab Copilot <span>Evidence-backed explanations. Deterministic science. Explicit uncertainty.</span></footer>
    </main>
  </div>;
}
