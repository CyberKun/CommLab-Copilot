import { ResponsiveContainer, LineChart, CartesianGrid, XAxis, YAxis, Tooltip, Legend, Line } from "recharts";
import type { Run } from "../api/client";

export function BerChart({runs}: {runs: Run[]}) {
  const valid = runs.filter(r => r.result);
  const snrs = [...new Set(valid.flatMap(r => r.result!.points.map(p => p.ebn0_db)))].sort((a,b) => a-b);
  const data = snrs.map(snr => {
    const row: Record<string, number | undefined> = {snr};
    valid.forEach((r, i) => {
      const p = r.result!.points.find(p => p.ebn0_db === snr);
      if (p) { row[`measured${i}`] = p.ber > 0 ? p.ber : undefined; row[`theory${i}`] = p.theory;
        row[`upper${i}`] = p.ber === 0 ? p.ci_high : undefined; }
    });
    return row;
  });
  const colors = ["#0d9488", "#d97706"];
  if (!valid.length) return <div className="chart-empty"><span>↗</span><h3>Your experiment starts here</h3><p>Run a sweep to compare measured BER with theory.</p></div>;
  const minimum = Math.min(...valid.flatMap(r => r.result!.points.flatMap(p => [p.theory, p.ber > 0 ? p.ber : p.ci_high])));
  return <><div className="chart"><ResponsiveContainer width="100%" height="100%">
    <LineChart data={data} margin={{top: 16, right: 24, left: 20, bottom: 30}}>
      <CartesianGrid strokeDasharray="3 5" stroke="#e2e8e8"/>
      <XAxis dataKey="snr" type="number" domain={["dataMin", "dataMax"]} label={{value: "Eb/N0 (dB)", position: "bottom"}}/>
      <YAxis scale="log" domain={[10 ** Math.floor(Math.log10(minimum)), 1]} allowDataOverflow
        tickFormatter={v => Number(v).toExponential(0)} label={{value: "Bit error rate (errors/bit)", angle: -90, position: "insideLeft", offset: -8}}/>
      <Tooltip formatter={v => Number(v).toExponential(4)}/><Legend verticalAlign="top" height={42}/>
      {valid.map((r,i) => <Line key={`m${i}`} name={`${r.spec.channel} measured · ${r.id.slice(0,6)}`} type="linear" dataKey={`measured${i}`} stroke={colors[i%2]} strokeWidth={2} dot={{r:4}} connectNulls={false} isAnimationActive={false}/>)}
      {valid.map((r,i) => <Line key={`t${i}`} name={`${r.spec.channel} theory`} dataKey={`theory${i}`} stroke={colors[i%2]} strokeDasharray="6 4" dot={false} isAnimationActive={false}/>)}
      {valid.map((r,i) => r.result!.points.some(p => p.errors === 0) ? <Line key={`u${i}`} name={`${r.spec.channel} zero-error 95% upper bound`} dataKey={`upper${i}`} stroke={colors[i%2]} strokeWidth={0} dot={{r:6}} isAnimationActive={false}/> : null)}
    </LineChart>
  </ResponsiveContainer></div><p className="caption">Logarithmic BER axis. Zero-error points appear as upper bounds, never as zero. Exact 95% intervals are listed below.</p></>;
}
