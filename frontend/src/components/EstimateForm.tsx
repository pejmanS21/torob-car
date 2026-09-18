"use client";
import { useState } from "react";
import { apiGet } from "@/lib/api/client";
import type { BodyCondition, CatalogSuggestion, Category, ModelStats } from "@/lib/api/types";
import { useApi } from "@/lib/api/useApi";
import { fa } from "@/lib/format";
import { BODY_CONDITION_CATEGORIES, BODY_NAMES, CATEGORY_NAMES } from "@/lib/labels";
import styles from "./EstimateForm.module.css";

export interface EstimateInput {
  category: Category; trim: string | null; year: number | null; kmThousands: number; insuranceMonths: number;
  bodyCondition: BodyCondition | null; asking: string;
}

interface Props { input: EstimateInput; onChange(patch: Partial<EstimateInput>): void; onSubmit(): void; canSubmit: boolean; busy: boolean; }

const ESTIMATED_CATEGORIES: Category[] = ["light", "motorcycle"];
const BODY_CONDITIONS = Object.keys(BODY_NAMES) as BodyCondition[];
const MAX_INSURANCE_MONTHS = 12;
const yearsBetween = (stats: ModelStats | null): number[] =>
  stats && stats.year_min !== null && stats.year_max !== null ? Array.from({ length: stats.year_max - stats.year_min + 1 }, (_, i) => (stats.year_max as number) - i) : [];

export function EstimateForm({ input, onChange, onSubmit, canSubmit, busy }: Props) {
  const [typed, setTyped] = useState("");
  const [model, setModel] = useState<string | null>(null);
  // Type-ahead: every keystroke is a new key, so a stale response can never win.
  const suggestions = useApi(input.trim ? null : `suggest:${input.category}:${typed}`, (signal) => apiGet<CatalogSuggestion[]>("/catalog/suggest", { q: typed, category: input.category }, signal));
  // The year select spans the chosen model's real range.
  const stats = useApi(model ? `stats:${model}` : null, (signal) => apiGet<ModelStats>(`/models/${encodeURIComponent(model as string)}/stats`, {}, signal));
  const years = yearsBetween(stats.data);
  const showBody = BODY_CONDITION_CATEGORIES.includes(input.category);

  function pick(suggestion: CatalogSuggestion) {
    setModel(suggestion.model);
    setTyped(suggestion.trim);
    onChange({ trim: suggestion.trim, year: null });
  }
  function clearTrim() { setModel(null); onChange({ trim: null, year: null }); }

  return (
    <form className={styles.card} onSubmit={(event) => { event.preventDefault(); onSubmit(); }}>
      <h1 className={styles.title}>این قیمت منصفانه‌ست؟</h1>
      <p className={styles.lead}>مشخصات ماشین رو بده؛ با آگهی‌های فعال همان تیپ مقایسه می‌کنیم.</p>
      <div className={styles.fields}>
        <label className={styles.field}>
          دسته
          <select className={styles.select} value={input.category} onChange={(event) => { clearTrim(); setTyped(""); onChange({ category: event.target.value as Category, bodyCondition: null }); }}>
            {ESTIMATED_CATEGORIES.map((category) => <option key={category} value={category}>{CATEGORY_NAMES[category]}</option>)}
          </select>
        </label>
        <label className={styles.field}>
          برند و مدل
          <input type="text" className={styles.asking} dir="rtl" value={typed} placeholder="مثلاً: پژو ۲۰۶" aria-label="برند و مدل"
            onChange={(event) => { setTyped(event.target.value); if (input.trim) clearTrim(); }} />
          {!input.trim && suggestions.data && suggestions.data.length > 0 && (
            <ul className={styles.suggestions} role="listbox">
              {suggestions.data.map((s) => (
                <li key={s.trim}><button type="button" className={styles.suggestion} onClick={() => pick(s)}>{s.trim} <span className={styles.count}>{fa(s.count)} آگهی</span></button></li>
              ))}
            </ul>
          )}
          {!input.trim && suggestions.data && suggestions.data.length === 0 && typed && <span className={styles.hint}>مدلی با این نام نداریم.</span>}
        </label>
        <label className={styles.field}>
          سال ساخت
          <select className={styles.select} value={input.year ?? ""} disabled={!years.length} onChange={(event) => onChange({ year: event.target.value ? Number(event.target.value) : null })}>
            <option value="">{stats.loading ? "…" : input.trim ? "انتخاب کن" : "اول مدل رو انتخاب کن"}</option>
            {years.map((year) => <option key={year} value={year}>{fa(year)}</option>)}
          </select>
        </label>
        <label className={styles.field}>
          <span className={styles.kmHead}>
            کارکرد
            <b>{fa(input.kmThousands)} هزار کیلومتر</b>
          </span>
          <input type="range" min={0} max={300} step={5} value={input.kmThousands} onChange={(event) => onChange({ kmThousands: Number(event.target.value) })} className={styles.range} />
        </label>
        <label className={styles.field}>
          <span className={styles.kmHead}>
            بیمهٔ شخص ثالث
            <b>{fa(input.insuranceMonths)} ماه</b>
          </span>
          <input type="range" min={0} max={MAX_INSURANCE_MONTHS} step={1} value={input.insuranceMonths} onChange={(event) => onChange({ insuranceMonths: Number(event.target.value) })} className={styles.range} />
        </label>
        {showBody && (
          <label className={styles.field}>
            وضعیت بدنه
            <select className={styles.select} value={input.bodyCondition ?? ""} onChange={(event) => onChange({ bodyCondition: (event.target.value || null) as BodyCondition | null })}>
              <option value="">نامشخص</option>
              {BODY_CONDITIONS.map((body) => <option key={body} value={body}>{BODY_NAMES[body]}</option>)}
            </select>
          </label>
        )}
        <label className={styles.field}>
          قیمت پیشنهادی فروشنده (اختیاری)
          <div className={styles.askingRow}>
            <input type="text" inputMode="numeric" dir="ltr" value={input.asking} onChange={(event) => onChange({ asking: event.target.value })} placeholder="مثلاً ۶۵۰" className={styles.asking} />
            <span>میلیون</span>
          </div>
        </label>
        <button type="submit" className={styles.submit} disabled={!canSubmit}>{busy ? "در حال محاسبه…" : "تخمین بزن"}</button>
      </div>
    </form>
  );
}
