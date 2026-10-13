"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiError, createJob, listJobs } from "../../lib/api";

export default function RecruiterPage() {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [skills, setSkills] = useState("");
  const [error, setError] = useState("");
  const jobsQuery = useQuery({ queryKey: ["jobs"], queryFn: () => listJobs() });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await createJob(title, description, skills.split(",").map((s) => s.trim()).filter(Boolean));
      setTitle("");
      setDescription("");
      setSkills("");
      jobsQuery.refetch();
    } catch (err) {
      setError(err instanceof ApiError ? `${err.status}: ${err.message}` : "create failed");
    }
  }

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-2xl font-bold">Recruiter</h1>

      <section className="mt-4 rounded border bg-white p-4">
        <h2 className="font-semibold">Post a job</h2>
        <form onSubmit={submit} className="mt-2 flex flex-col gap-2">
          <input className="rounded border p-2" placeholder="title" value={title} onChange={(e) => setTitle(e.target.value)} required />
          <textarea className="rounded border p-2" placeholder="description" value={description} onChange={(e) => setDescription(e.target.value)} required />
          <input className="rounded border p-2" placeholder="skills, comma separated" value={skills} onChange={(e) => setSkills(e.target.value)} />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button className="rounded bg-slate-900 px-4 py-2 text-white" type="submit">
            Post
          </button>
        </form>
      </section>

      <section className="mt-4 rounded border bg-white p-4">
        <h2 className="font-semibold">Jobs</h2>
        {jobsQuery.isLoading && <p className="text-sm">Loading…</p>}
        {jobsQuery.isError && <p className="text-sm text-red-600">Login as recruiter to list jobs.</p>}
        <ul className="mt-2 flex flex-col gap-2">
          {(jobsQuery.data ?? []).map((j) => (
            <li key={j.id} className="rounded border p-2 text-sm">
              <Link href={`/recruiter/jobs/${j.id}`} className="font-medium underline">
                {j.title}
              </Link>
              <span className="ml-2 text-slate-500">{j.skills.join(", ")}</span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
