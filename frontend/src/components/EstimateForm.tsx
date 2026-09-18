"use client";
import { BODIES, MODELS } from "@/lib/catalog";
import type { EstimateInput, EstimateResult } from "@/lib/estimate";
import { fa } from "@/lib/format";
import styles from "./EstimateForm.module.css";

interface Props { input: EstimateInput; result: EstimateResult; onChange(patch: Partial<EstimateInput>): void; }

export function EstimateForm({ input, result, onChange }: Props) {
  return (
    <div className={styles.card}>
      <h1 className={styles.title}>این قیمت منصفانه‌ست؟</h1>
      <p className={styles.lead}>مشخصات ماشین رو بده؛ با آگهی‌های فعال همان مدل مقایسه می‌کنیم.</p>
      <div className={styles.fields}>
        <label className={styles.field}>
          مدل
          <select className={styles.select} value={input.modelId} onChange={(event) => onChange({ modelId: event.target.value })}>
            {MODELS.map((model) => (
              <option key={model.id} value={model.id}>{model.name}</option>
            ))}
          </select>
        </label>
        <label className={styles.field}>
          سال ساخت
          <select className={styles.select} value={result.year} onChange={(event) => onChange({ year: Number(event.target.value) })}>
            {result.years.map((year) => (
              <option key={year} value={year}>{fa(year)}</option>
            ))}
          </select>
        </label>
        <label className={styles.field}>
          <span className={styles.kmHead}>
            کارکرد
            <b>{fa(input.kmThousands)} هزار کیلومتر</b>
          </span>
          <input
            type="range"
            min={0}
            max={300}
            step={5}
            value={input.kmThousands}
            onChange={(event) => onChange({ kmThousands: Number(event.target.value) })}
            className={styles.range}
          />
        </label>
        <label className={styles.field}>
          وضعیت بدنه
          <select className={styles.select} value={input.bodyIndex} onChange={(event) => onChange({ bodyIndex: Number(event.target.value) })}>
            {BODIES.map((body, index) => (
              <option key={body.name} value={index}>{body.name}</option>
            ))}
          </select>
        </label>
        <label className={styles.field}>
          گیربکس
          <div className={styles.gears}>
            {result.model.gears.map((gear) => (
              <button key={gear} type="button" className={styles.gear} data-on={gear === result.gear} onClick={() => onChange({ gear })}>
                {gear}
              </button>
            ))}
          </div>
        </label>
        <label className={styles.field}>
          قیمت پیشنهادی فروشنده (اختیاری)
          <div className={styles.askingRow}>
            <input
              type="text"
              inputMode="numeric"
              dir="ltr"
              value={input.asking}
              onChange={(event) => onChange({ asking: event.target.value })}
              placeholder="مثلاً ۶۵۰"
              className={styles.asking}
            />
            <span>میلیون</span>
          </div>
        </label>
      </div>
    </div>
  );
}
