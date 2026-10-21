import { useEffect, useState } from "react";
import type { Spec } from "../api/client";
export const defaultSpec: Spec = {schema_version: 1, capability: "bpsk.ber", channel: "awgn",
  ebn0_db: [0, 2, 4, 6, 8], bits_per_point: 100000, seed: 42, receiver: "coherent_perfect_csi",
  bit_energy: 1, noise_convention: "N0/2_per_real_component"};

export function ConfigForm({value, onChange}: {value: Spec; onChange: (spec: Spec) => void}) {
  const [sweep, setSweep] = useState((value.ebn0_db ?? []).join(", "));
  useEffect(() => setSweep((value.ebn0_db ?? []).join(", ")), [value.ebn0_db]);
  return <div className="config-grid">
    <label>Channel<select value={value.channel} onChange={e => onChange({...value, channel: e.target.value as Spec["channel"]})}>
      <option value="awgn">AWGN</option><option value="rayleigh">Flat Rayleigh</option></select></label>
    <label>Seed<input type="number" min="0" max="4294967295" value={value.seed} onChange={e => onChange({...value, seed: Number(e.target.value)})}/></label>
    <label>Bits / Eb/N0 point<input type="number" min="1000" max="2000000" step="1000" value={value.bits_per_point}
      onChange={e => onChange({...value, bits_per_point: Number(e.target.value)})}/></label>
    <label>Eb/N0 sweep (dB, comma separated)<input value={sweep} onChange={e => setSweep(e.target.value)}
      onBlur={() => onChange({...value, ebn0_db: sweep.split(",").map(Number)})}/></label>
    <p className="assumption">Coherent BPSK · Eb = Es = 1 · noise variance N0/2 per real component.
      Rayleigh uses independent CN(0,1) fading per symbol and perfect receiver CSI.</p>
  </div>;
}
