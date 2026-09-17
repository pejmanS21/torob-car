import { Icon } from "./Icon";
import type { Verdict } from "@/lib/types";
import styles from "./VerdictBadge.module.css";

export function VerdictBadge({ verdict, size = "md" }: { verdict: Verdict; size?: "sm" | "md" | "lg" }) {
  return (
    <span className={`${styles.badge} ${styles[size]}`} style={{ background: verdict.color }}>
      <Icon d={verdict.icon} size={14} stroke="#fff" />
      {verdict.label}
    </span>
  );
}
