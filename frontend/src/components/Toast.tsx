"use client";
import { useAppState } from "@/state/AppState";
import styles from "./Toast.module.css";

export function Toast() {
  const { toast } = useAppState();
  return toast ? <output className={styles.toast}>{toast}</output> : null;
}
