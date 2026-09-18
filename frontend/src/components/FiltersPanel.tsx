"use client";
import type { Category, Facets, Gearbox } from "@/lib/api/types";
import { fa, formatToman } from "@/lib/format";
import { CATEGORY_NAMES, CATEGORY_ORDER, GEARBOX_NAMES } from "@/lib/labels";
import type { SearchOverrides } from "@/lib/search";
import styles from "./FiltersPanel.module.css";

const MILLION = 1_000_000;
const PRICE_CAPS = [200, 300, 500, 700, 1_000, 1_500, 2_000, 3_000, 5_000].map((m) => m * MILLION);
const KM_CAPS = [30_000, 50_000, 90_000, 120_000, 150_000, 200_000, 300_000];
const CURRENT_YEAR = 1405;
const YEARS = Array.from({ length: 26 }, (_, i) => CURRENT_YEAR - i);
const TOP_MODELS = 12;
const TOP_CITIES = 12;
const toggle = (list: string[] | undefined, item: string): string[] | undefined => {
  const next = list?.includes(item) ? list.filter((x) => x !== item) : [...(list ?? []), item];
  return next.length ? next : undefined;
};

interface Props { params: SearchOverrides; facets: Facets | null; onChange(next: SearchOverrides): void; onReset(): void; open: boolean; onClose(): void; resultCount: number | null; }

export function FiltersPanel({ params, facets, onChange, onReset, open, onClose, resultCount }: Props) {
  const set = (patch: Partial<SearchOverrides>) => onChange({ ...params, ...patch });
  const models = [...new Set([...(params.models ?? []), ...(facets?.models.slice(0, TOP_MODELS).map((m) => m.model) ?? [])])];
  const cities = [...new Set([...(params.cities ?? []), ...(facets?.cities.slice(0, TOP_CITIES).map((c) => c.value) ?? [])])];
  const countOf = (list: { model?: string; value?: string; count: number }[] | undefined, name: string): string =>
    list?.find((item) => (item.model ?? item.value) === name)?.count.toString() ?? "";
  const showGearbox = !params.category || params.category === "light";
  return (
    <>
      <aside className={styles.panel} data-open={open}>
        <div className={styles.sheetHead}><span className={styles.grabber} /><div className={styles.sheetTitleRow}><span className={styles.sheetTitle}>فیلترها</span><button className={styles.clear} onClick={onReset}>پاک‌کردن</button></div></div>
        <div className={styles.deskHead}>فیلترها</div>
        <div className={styles.body}>
          <div className={styles.label}>دسته</div>
          <div className={styles.cities}>
            <button className={styles.pill} data-on={!params.category} aria-pressed={!params.category} onClick={() => set({ category: undefined, models: undefined, gearbox: undefined })}>همه</button>
            {CATEGORY_ORDER.map((category: Category) => (
              <button key={category} className={styles.pill} data-on={params.category === category} aria-pressed={params.category === category} onClick={() => set({ category, models: undefined, gearbox: category === "light" ? params.gearbox : undefined })}>
                {CATEGORY_NAMES[category]}{!params.category && facets?.categories[category] ? ` (${fa(facets.categories[category] ?? 0)})` : ""}
              </button>
            ))}
          </div>
          <div className={styles.label}>مدل</div>
          <div className={styles.models}>{models.map((model) => (
            <label key={model} className={styles.check}><input type="checkbox" checked={params.models?.includes(model) ?? false} onChange={() => set({ models: toggle(params.models, model) })} />{model}<span className={styles.count}>{fa(countOf(facets?.models, model))}</span></label>
          ))}</div>
          <div className={styles.label}>شهر</div>
          <div className={styles.cities}>{cities.map((city) => <button key={city} className={styles.pill} data-on={params.cities?.includes(city) ?? false} aria-pressed={params.cities?.includes(city) ?? false} onClick={() => set({ cities: toggle(params.cities, city) })}>{city} <span className={styles.count}>{fa(countOf(facets?.cities, city))}</span></button>)}</div>
          <label className={styles.label}>حداکثر قیمت
            <select className={styles.select} value={params.price_max ?? ""} onChange={(e) => set({ price_max: e.target.value ? Number(e.target.value) : undefined })} aria-label="حداکثر قیمت">
              <option value="">بدون سقف</option>
              {PRICE_CAPS.map((cap) => <option key={cap} value={cap}>{formatToman(cap)}</option>)}
            </select>
          </label>
          <label className={styles.label}>حداکثر کارکرد
            <select className={styles.select} value={params.km_max ?? ""} onChange={(e) => set({ km_max: e.target.value ? Number(e.target.value) : undefined })} aria-label="حداکثر کارکرد">
              <option value="">بدون سقف</option>
              {KM_CAPS.map((cap) => <option key={cap} value={cap}>{fa(cap / 1000)} هزار کیلومتر</option>)}
            </select>
          </label>
          <label className={styles.label}>مدل (سال)
            <select className={styles.select} value={params.year ?? ""} onChange={(e) => set({ year: e.target.value ? Number(e.target.value) : undefined })} aria-label="سال">
              <option value="">همهٔ سال‌ها</option>
              {YEARS.map((year) => <option key={year} value={year}>{fa(year)}</option>)}
            </select>
          </label>
          {showGearbox && (
            <>
              <div className={styles.label}>گیربکس</div>
              <div className={styles.gears}>
                <button className={styles.gear} data-on={!params.gearbox} aria-pressed={!params.gearbox} onClick={() => set({ gearbox: undefined })}>همه</button>
                {(["manual", "automatic"] as Gearbox[]).map((g) => <button key={g} className={styles.gear} data-on={params.gearbox === g} aria-pressed={params.gearbox === g} onClick={() => set({ gearbox: g })}>{GEARBOX_NAMES[g]}</button>)}
              </div>
            </>
          )}
          <label className={`${styles.check} ${styles.onlyBelow}`}><input type="checkbox" checked={params.only_below ?? false} onChange={() => set({ only_below: params.only_below ? undefined : true })} />فقط ارزان‌تر از بازار</label>
          <button className={styles.deskReset} onClick={onReset}>پاک‌کردن فیلترها</button>
        </div>
        <div className={styles.sheetFoot}><button className={styles.apply} onClick={onClose}>{resultCount === null ? "نمایش آگهی‌ها" : `نمایش ${fa(resultCount)} آگهی`}</button></div>
      </aside>
      {open && <div className={styles.backdrop} onClick={onClose} />}
    </>
  );
}
