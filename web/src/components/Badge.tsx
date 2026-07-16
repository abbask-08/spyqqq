import type { Posture } from "@/lib/types";

const STATUS_CLASS: Record<Posture, string> = {
  RISK_ON: "bg-status-good text-white",
  NEUTRAL: "bg-status-warning text-[#3a2a00]",
  RISK_OFF: "bg-status-critical text-white",
  unknown: "bg-ink-muted text-white",
};

export function PostureBadge({ posture }: { posture: Posture }) {
  return (
    <span
      className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${STATUS_CLASS[posture] ?? STATUS_CLASS.unknown}`}
    >
      {posture}
    </span>
  );
}
