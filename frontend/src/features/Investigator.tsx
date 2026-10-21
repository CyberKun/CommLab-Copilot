import { useState } from "react";
import { request, post, download, type Workspace, type Investigation, type Spec, type Evidence } from "../api/client";
import { ConfigForm } from "./ConfigForm";

function Review({item, approve}: {item: Investigation; approve: (specs: Spec[]) => void}) {
  const [specs, setSpecs] = useState(item.plans);
  return <div className="review"><h4>Review experiment plan</h4>
    {specs.map((spec, i) => <ConfigForm key={i} value={spec} onChange={updated => setSpecs(specs.map((s,j) => j===i ? updated : s))}/>)}
    <button onClick={() => approve(specs)}>Approve & run {specs.length} experiment{specs.length > 1 ? "s" : ""}</button></div>;
}

export function Investigator({workspace, items, action}: {workspace: Workspace; items: Investigation[]; action: (fn: () => Promise<unknown>) => Promise<void>}) {
  const [question, setQuestion] = useState("");
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  return <section className="panel investigator">
    <div className="panel-heading"><div><span className="eyebrow">INVESTIGATOR</span><h2>Ask. Test. Understand.</h2></div><span className="badge">Bounded tools</span></div>
    <p className="muted">Use your sources and saved experiments to investigate a question. Every proposed run needs your review.</p>
    <form onSubmit={e => {e.preventDefault(); void action(async () => {await request("/investigations", post({question}), workspace); setQuestion("");});}}>
      <textarea required maxLength={2000} value={question} onChange={e => setQuestion(e.target.value)}
        placeholder="Compare BPSK over AWGN and Rayleigh using this handout. Are the results consistent with theory?"/>
      <button type="submit" disabled={!question.trim()}>Start investigation <span>↗</span></button>
    </form>
    {items.map(item => <article className="conversation" key={item.id}>
      <div className="row"><strong>{item.question}</strong><span className={`status ${item.status}`}>{item.status}</span></div>
      {item.error && <p className="warning">{item.error}</p>}
      {item.answer && <>
        {item.answer.retrieved_facts.length > 0 && <h4>Retrieved evidence</h4>}
        {item.answer.retrieved_facts.map(f => <div className="evidence" key={f.citation}>
          <p>{f.quote}</p><button className="text-button" onClick={() => void action(async () => setEvidence(await request<Evidence>(`/evidence/${f.citation}`, {}, workspace)))}>
            {f.source.title} · {f.source.page ? `page ${f.source.page}` : "text"} · source {f.source.version_id.slice(0,6)} ↗</button>
          {f.warnings.map(w => <p className="warning" key={w}>{w}</p>)}</div>)}
        {item.answer.observed_results.length > 0 && <><h4>Observed tool results</h4>{item.answer.observed_results.map(r => <p key={r.run_id}>Run {r.run_id.slice(0,8)} · {r.status}. {r.findings.map(f => f.message).join(" ")}</p>)}</>}
        {item.answer.comparison && <p>{item.answer.comparison}</p>}
        {item.answer.hypotheses.map((h,i) => <p className="hypothesis" key={i}><strong>Tentative / workflow note:</strong> {h}</p>)}
        {item.answer.unresolved_questions.map(q => <p className="warning" key={q}>{q}</p>)}
      </>}
      {item.status === "review" && <Review item={item} approve={specs => void action(() => request(`/investigations/${item.id}/approve`, post({specs}), workspace))}/>}
      <details><summary>Evidence & tool timeline · {item.activity.length} calls</summary>
        <ol className="timeline">{item.activity.map((a,i) => <li key={i}><strong>{a.tool}</strong> · {a.ok ? "completed" : "rejected"} · {a.elapsed_seconds.toFixed(2)}s
          <details><summary>Tool output</summary><pre>{JSON.stringify(a.data, null, 2)}</pre></details></li>)}</ol>
        <p className="caption">{item.usage.provider} · {item.usage.input_tokens + item.usage.output_tokens} tokens · cost {item.usage.cost_usd === null ? "not available" : `$${item.usage.cost_usd}`}</p>
      </details>
    </article>)}
    {evidence && <div className="modal-backdrop"><div className="modal" role="dialog" aria-modal="true" aria-label="Source evidence">
      <div className="row"><h3>{evidence.source.title}</h3><button className="secondary" onClick={() => setEvidence(null)}>Close</button></div>
      <p className="caption">Version {evidence.source.version_id} · SHA-256 {evidence.source.content_sha256}</p><pre>{evidence.text}</pre>
      <button onClick={() => void action(() => download(workspace, evidence.source.artifact_id, evidence.source.title))}>Download exact source</button>
    </div></div>}
  </section>;
}
