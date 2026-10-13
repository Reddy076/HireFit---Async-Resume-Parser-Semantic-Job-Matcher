export default function Home() {
  return (
    <main style={{ padding: 32, fontFamily: "system-ui" }}>
      <h1>HireFit (Cycle 0)</h1>
      <p>Gateway: http://localhost:8000 | Consul: http://localhost:8500</p>
      <ul>
        <li>GET /api/v1/auth/health</li>
        <li>GET /api/v1/resumes/health</li>
      </ul>
    </main>
  );
}
