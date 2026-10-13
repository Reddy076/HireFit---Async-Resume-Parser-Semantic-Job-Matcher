"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { gateway } from "../lib/api";

const SERVICES = [
  { name: "auth", path: "/api/v1/auth/health" },
  { name: "resumes", path: "/api/v1/resumes/health" },
  { name: "jobs", path: "/api/v1/jobs/health" },
  { name: "embeddings", path: "/api/v1/embeddings/health" },
  { name: "match", path: "/api/v1/match/health" },
  { name: "explain", path: "/api/v1/explain/health" },
];

export default function Home() {
  const [status, setStatus] = useState<Record<string, boolean>>({});
  useEffect(() => {
    SERVICES.forEach(async (s) => {
      try {
        const res = await fetch(`${gateway}${s.path}`);
        setStatus((prev) => ({ ...prev, [s.name]: res.ok }));
      } catch {
        setStatus((prev) => ({ ...prev, [s.name]: false }));
      }
    });
  }, []);

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-3xl font-bold">HireFit</h1>
      <p className="mt-2 text-slate-600">
        Async resume parsing, semantic job matching and RAG explanations across 7 microservices.
      </p>
      <div className="mt-6 flex gap-3">
        <Link href="/login" className="rounded bg-slate-900 px-4 py-2 text-white">
          Login
        </Link>
        <Link href="/candidate" className="rounded border px-4 py-2">
          Candidate
        </Link>
        <Link href="/recruiter" className="rounded border px-4 py-2">
          Recruiter
        </Link>
      </div>
      <h2 className="mt-8 font-semibold">Service status (via Kong :8000)</h2>
      <ul className="mt-2 grid grid-cols-2 gap-2">
        {SERVICES.map((s) => (
          <li key={s.name} className="rounded border bg-white p-2 text-sm">
            <span className={status[s.name] ? "text-green-600" : "text-slate-400"}>
              {status[s.name] === undefined ? "…" : status[s.name] ? "●" : "○"}
            </span>{" "}
            {s.name}
          </li>
        ))}
      </ul>
    </main>
  );
}
