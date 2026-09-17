"use client";
import { useAppState } from "@/state/AppState";
import styles from "./Toast.module.css";

export function Toast() {
  const { toast } = useAppState();
  return toast ? <div className={styles.toast} role="status">{toast}</div> : null;
}
