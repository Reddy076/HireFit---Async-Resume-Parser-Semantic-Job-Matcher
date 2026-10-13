"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, login, me, register, setToken } from "../../lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("candidate");
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      if (mode === "register") await register(email, password, role);
      const tokens = await login(email, password);
      setToken(tokens.access_token);
      const user = await me();
      router.push(user.role === "recruiter" ? "/recruiter" : "/candidate");
    } catch (err) {
      setError(err instanceof ApiError ? `${err.status}: ${err.message}` : "request failed");
    }
  }

  return (
    <main className="mx-auto max-w-md p-8">
      <h1 className="text-2xl font-bold">{mode === "login" ? "Login" : "Register"}</h1>
      <form onSubmit={submit} className="mt-4 flex flex-col gap-3">
        <input
          className="rounded border p-2"
          placeholder="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          className="rounded border p-2"
          placeholder="password (8+ chars)"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {mode === "register" && (
          <select className="rounded border p-2" value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="candidate">candidate</option>
            <option value="recruiter">recruiter</option>
          </select>
        )}
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button className="rounded bg-slate-900 px-4 py-2 text-white" type="submit">
          {mode === "login" ? "Login" : "Register + Login"}
        </button>
      </form>
      <button className="mt-3 text-sm underline" onClick={() => setMode(mode === "login" ? "register" : "login")}>
        Switch to {mode === "login" ? "register" : "login"}
      </button>
    </main>
  );
}
