"use client";
import { useState } from "react";
import { BreakdownList } from "@/components/BreakdownList";
import { ErrorBanner } from "@/components/ErrorBanner";
import { EstimateForm, type EstimateInput } from "@/components/EstimateForm";
import { EstimateResultCard } from "@/components/EstimateResultCard";
import { SimilarListings } from "@/components/SimilarListings";
import { ApiError, apiPost } from "@/lib/api/client";
import type { EstimateRequest, EstimateResponse } from "@/lib/api/types";
import { en } from "@/lib/format";
import { estimateBreakdownRows } from "@/lib/pricing";
import { cardOf } from "@/lib/view";
import styles from "./page.module.css";

const INITIAL: EstimateInput = { category: "light", trim: null, year: null, kmThousands: 80, insuranceMonths: 6, bodyCondition: null, asking: "" };
const TOMAN_PER_MILLION = 1_000_000;
const KM_PER_THOUSAND = 1_000;

function toRequest(input: EstimateInput): EstimateRequest | null {
  if (!input.trim || input.year === null) return null;
  const asking = Number.parseFloat(en(input.asking));
  return {
    category: input.category, trim: input.trim, year: input.year, km: input.kmThousands * KM_PER_THOUSAND,
    insurance_months: input.insuranceMonths, body_condition: input.bodyCondition,
    asking_price: Number.isFinite(asking) && asking > 0 ? Math.round(asking * TOMAN_PER_MILLION) : null,
  };
}

export default function EstimatePage() {
  const [input, setInput] = useState<EstimateInput>(INITIAL);
  const [result, setResult] = useState<EstimateResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const request = toRequest(input);

  async function submit() {
    if (!request || busy) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await apiPost<EstimateResponse>("/estimates", request));
    } catch (error_) {
      // 422 (no comparables / unknown trim) shows the backend's message inline; the form stays editable.
      setError(error_ instanceof ApiError ? error_ : new ApiError(0, "network_error", "network failure"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={styles.grid}>
      <EstimateForm input={input} onChange={(patch) => setInput((i) => ({ ...i, ...patch }))} onSubmit={submit} canSubmit={request !== null && !busy} busy={busy} />
      <div className={styles.results}>
        {error && <ErrorBanner error={error} onRetry={submit} />}
        {result && <EstimateResultCard result={result} title={input.trim ?? ""} year={input.year} />}
        {result && <BreakdownList title="چطور حساب شد؟" rows={estimateBreakdownRows(result, request)} />}
        {result && <SimilarListings title="آگهی‌های مشابه الان در بازار" cards={result.similar.map((l) => cardOf(l))} />}
        {!result && !error && <div className={styles.empty}>مدل، سال و کارکرد رو بده تا با آگهی‌های فعال همان تیپ مقایسه کنیم.</div>}
      </div>
    </section>
  );
}
