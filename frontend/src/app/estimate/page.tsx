"use client";
import { useMemo, useState } from "react";
import { BreakdownList } from "@/components/BreakdownList";
import { EstimateForm } from "@/components/EstimateForm";
import { EstimateResultCard } from "@/components/EstimateResultCard";
import { SimilarListings } from "@/components/SimilarListings";
import { estimate, type EstimateInput } from "@/lib/estimate";
import { LISTINGS } from "@/lib/listings";
import { cardOf } from "@/lib/view";
import styles from "./page.module.css";

const INITIAL: EstimateInput = { modelId: "206", year: 1401, kmThousands: 80, bodyIndex: 0, gear: "دنده‌ای", asking: "" };

export default function EstimatePage() {
  const [input, setInput] = useState<EstimateInput>(INITIAL);
  const result = useMemo(() => estimate(input, LISTINGS), [input]);
  return (
    <section className={styles.grid}>
      <EstimateForm input={input} result={result} onChange={(patch) => setInput((i) => ({ ...i, ...patch }))} />
      <div className={styles.results}>
        <EstimateResultCard result={result} />
        <BreakdownList title="چطور حساب شد؟" rows={result.breakdown} />
        <SimilarListings title="آگهی‌های مشابه الان در بازار" cards={result.similar.map(cardOf)} />
      </div>
    </section>
  );
}
