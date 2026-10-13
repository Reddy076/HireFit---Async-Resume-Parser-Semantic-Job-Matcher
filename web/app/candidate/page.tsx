"use client";

import { useEffect, useState } from "react";
import ScoreBar from "../../components/ScoreBar";
import { ApiError, explain, getResume, matchSingle, uploadResume, type ExplainResult, type MatchResult, type ResumeStatus } from "../../lib/api";

export default function CandidatePage() {
  const [file, setFile] = useState<File | null>(null);
  const [resume, setResume] = useState<ResumeStatus | null>(null);
  const [jobId, setJobId] = useState("");
  const [match, setMatch] = useState<MatchResult | null>(null);
  const [kind, setKind] = useState("explain");
  const [generation, setGeneration] = useState<ExplainResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  async function doUpload() {
    if (!file) return;
    setError("");
    setBusy("upload");
    try {
      const { resume_id } = await uploadResume(file);
      setBusy("parse");
      for (let i = 0; i < 60; i++) {
        const status = await getResume(resume_id);
        setResume(status);
        if (status.status === "parsed" || status.status === "needs_ocr") break;
        await new Promise((r) => setTimeout(r, 2000));
      }
    } catch (err) {
      setError(err instanceof ApiError ? `${err.status}: ${err.message}` : "upload failed");
    } finally {
      setBusy("");
    }
  }

  async function doMatch() {
    if (!resume || !jobId) return;
    setError("");
    try {
      setMatch(await matchSingle(resume.resume_id, jobId.trim()));
      setGeneration(null);
    } catch (err) {
      setError(err instanceof ApiError ? `${err.status}: ${err.message}` : "match failed");
    }
  }

  async function doExplain() {
    if (!resume || !jobId) return;
    setGeneration(await explain(resume.resume_id, jobId.trim(), kind));
  }

  useEffect(() => {
    document.title = "HireFit — Candidate";
  }, []);

  const sections = resume?.parsed ? Object.entries(resume.parsed).filter(([k]) => !k.startsWith("_")) : [];

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-2xl font-bold">Candidate</h1>

      <section className="mt-4 rounded border bg-white p-4">
        <h2 className="font-semibold">1. Upload resume (PDF)</h2>
        <div className="mt-2 flex gap-2">
          <input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <button disabled={!file || !!busy} onClick={doUpload} className="rounded bg-slate-900 px-3 py-1 text-white disabled:opacity-50">
            {busy === "parse" ? "Parsing…" : "Upload"}
          </button>
        </div>
        {resume && <p className="mt-2 text-sm">Status: <b>{resume.status}</b> · {resume.filename}</p>}
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </section>

      {sections.length > 0 && (
        <section className="mt-4 rounded border bg-white p-4">
          <h2 className="font-semibold">2. Parsed sections</h2>
          {sections.map(([name, body]) => (
            <details key={name} className="mt-2 text-sm">
              <summary className="cursor-pointer font-medium">[{name}]</summary>
              <pre className="mt-1 whitespace-pre-wrap text-slate-600">{body.slice(0, 1200)}</pre>
            </details>
          ))}
        </section>
      )}

      <section className="mt-4 rounded border bg-white p-4">
        <h2 className="font-semibold">3. Match against a job</h2>
        <div className="mt-2 flex gap-2">
          <input className="flex-1 rounded border p-2" placeholder="job_id" value={jobId} onChange={(e) => setJobId(e.target.value)} />
          <button disabled={!resume || !jobId} onClick={doMatch} className="rounded bg-slate-900 px-3 py-1 text-white disabled:opacity-50">
            Score
          </button>
        </div>
        {match && (
          <div className="mt-3 text-sm">
            <ScoreBar value={match.final_score} />
            <p className="mt-1">rerank {match.ce_score.toFixed(2)} · skills {match.skill_score.toFixed(2)}</p>
            <p className="mt-1">Matched: {match.matched_skills.join(", ") || "none"}</p>
            <p>Missing: {match.missing_skills.join(", ") || "none"}</p>
          </div>
        )}
      </section>

      {match && (
        <section className="mt-4 rounded border bg-white p-4">
          <h2 className="font-semibold">4. AI explanation</h2>
          <div className="mt-2 flex gap-2">
            {(["explain", "gaps", "rewrite"] as const).map((k) => (
              <button
                key={k}
                onClick={() => setKind(k)}
                className={`rounded border px-3 py-1 text-sm ${kind === k ? "bg-slate-900 text-white" : ""}`}
              >
                {k}
              </button>
            ))}
            <button onClick={doExplain} className="rounded bg-slate-900 px-3 py-1 text-sm text-white">
              Generate
            </button>
          </div>
          {generation && (
            <div className="mt-3 text-sm">
              <p className="text-slate-500">model: {generation.model} · cites: {generation.citations.map((c) => `[${c}]`).join(" ")}</p>
              <pre className="mt-1 whitespace-pre-wrap">{generation.output}</pre>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
