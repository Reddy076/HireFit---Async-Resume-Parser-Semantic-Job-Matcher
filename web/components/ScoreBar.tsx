export default function ScoreBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-40 overflow-hidden rounded bg-slate-200">
        <div className="h-full bg-emerald-600" style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} />
      </div>
      <span className="text-sm tabular-nums">{pct}%</span>
    </div>
  );
}
