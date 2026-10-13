"use client";

import { useState } from "react";
import ScoreBar from "../../../../components/ScoreBar";
import { ApiError, matchBulk, type MatchResult } from "../../../../lib/api";

function toCsv(rows: MatchResult[]): string {
  const head = "resume_id,job_id,final_score,ce_score,skill_score,matched,missing";
  const esc = (s: string) => `"${s.replace(/"/g, '""')}"`;
  return [head, ...rows.map((m) => [m.resume_id, m.job_id, m.final_score.toFixed(4), m.ce_score.toFixed(4), m.skill_score.toFixed(4), esc(m.matched_skills.join(";")), esc(m.missing_skills.join(";"))].join(","))].join("\n");
}

export default function RankPage({ params }: { params: { id: string } }) {
  const [matches, setMatches] = useState<MatchResult[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function rank() {
    setError("");
    setBusy(true);
    try {
      const res = await matchBulk(params.id, 50, 20);
      setMatches(res.matches);
    } catch (err) {
      setError(err instanceof ApiError ? `${err.status}: ${err.message}` : "rank failed");
    } finally {
      setBusy(false);
    }
  }

  function download() {
    const blob = new Blob([toCsv(matches)], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `rank-${params.id}.csv`;
    a.click();
  }

  return (
    <main className="mx-auto max-w-4xl p-8">
      <h1 className="text-2xl font-bold">Rank candidates</h1>
      <p className="mt-1 font-mono text-sm text-slate-500">{params.id}</p>
      <div className="mt-3 flex gap-2">
        <button disabled={busy} onClick={rank} className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50">
          {busy ? "Ranking…" : "Run bulk match"}
        </button>
        {matches.length > 0 && (
          <button onClick={download} className="rounded border px-4 py-2">
            Export CSV
          </button>
        )}
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      <table className="mt-4 w-full text-left text-sm">
        <thead>
          <tr className="border-b">
            <th className="py-2">resume</th>
            <th>score</th>
            <th>matched</th>
            <th>missing</th>
          </tr>
        </thead>
        <tbody>
          {matches.map((m) => (
            <tr key={m.resume_id} className="border-b">
              <td className="py-2 font-mono text-xs">{m.resume_id.slice(0, 8)}</td>
              <td>
                <ScoreBar value={m.final_score} />
              </td>
              <td className="text-emerald-700">{m.matched_skills.join(", ")}</td>
              <td className="text-red-600">{m.missing_skills.join(", ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
