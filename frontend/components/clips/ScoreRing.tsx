/** Final score (0–1) as a small ring with the number in the middle. */
export function ScoreRing({ value, size = 40 }: { value: number; size?: number }) {
  const r = size / 2 - 3;
  const c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(1, value));
  const color = v >= 0.65 ? "var(--color-emerald-500, #10b981)" : v >= 0.55 ? "var(--primary)" : "var(--muted-foreground)";
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`Score ${Math.round(v * 100)}`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--muted)" strokeWidth={4} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={4} strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={c * (1 - v)} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" fontSize={size * 0.3} fontWeight={700} fill="currentColor">
        {Math.round(v * 100)}
      </text>
    </svg>
  );
}
