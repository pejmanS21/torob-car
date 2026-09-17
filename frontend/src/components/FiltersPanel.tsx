"use client";
import { CITIES, MODELS } from "@/lib/catalog";
import { fa, num } from "@/lib/format";
import { listingsOfModel } from "@/lib/listings";
import type { Filters, GearFilter } from "@/lib/types";
import styles from "./FiltersPanel.module.css";

const GEARS: GearFilter[] = ["همه", "دنده‌ای", "اتوماتیک"];
const toggle = <T,>(list: T[], item: T): T[] => (list.includes(item) ? list.filter((x) => x !== item) : [...list, item]);

interface Props { filters: Filters; onChange(next: Filters): void; onReset(): void; open: boolean; onClose(): void; resultCount: number; }

export function FiltersPanel({ filters, onChange, onReset, open, onClose, resultCount }: Props) {
  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch });
  return (
    <>
      <aside className={styles.panel} data-open={open}>
        <div className={styles.sheetHead}><span className={styles.grabber} /><div className={styles.sheetTitleRow}><span className={styles.sheetTitle}>فیلترها</span><button className={styles.clear} onClick={onReset}>پاک‌کردن</button></div></div>
        <div className={styles.deskHead}>فیلترها</div>
        <div className={styles.body}>
          <div className={styles.label}>مدل</div>
          <div className={styles.models}>{MODELS.map((m) => (
            <label key={m.id} className={styles.check}><input type="checkbox" checked={filters.models.includes(m.id)} onChange={() => set({ models: toggle(filters.models, m.id) })} />{m.name}<span className={styles.count}>{fa(listingsOfModel(m.id).length)}</span></label>
          ))}</div>
          <div className={styles.label}>شهر</div>
          <div className={styles.cities}>{CITIES.map((c) => <button key={c.name} className={styles.pill} data-on={filters.cities.includes(c.name)} aria-pressed={filters.cities.includes(c.name)} onClick={() => set({ cities: toggle(filters.cities, c.name) })}>{c.name}</button>)}</div>
          <div className={styles.rangeHead}><span>حداکثر قیمت</span><b>{num(filters.maxPrice)} میلیون</b></div>
          <input type="range" min={300} max={1400} step={10} value={filters.maxPrice} onChange={(e) => set({ maxPrice: Number(e.target.value) })} className={styles.range} aria-label="حداکثر قیمت" />
          <div className={styles.rangeHead}><span>حداکثر کارکرد</span><b>{fa(filters.maxKm)} هزار کیلومتر</b></div>
          <input type="range" min={10} max={250} step={5} value={filters.maxKm} onChange={(e) => set({ maxKm: Number(e.target.value) })} className={styles.range} aria-label="حداکثر کارکرد" />
          <div className={styles.label}>گیربکس</div>
          <div className={styles.gears}>{GEARS.map((g) => <button key={g} className={styles.gear} data-on={filters.gear === g} aria-pressed={filters.gear === g} onClick={() => set({ gear: g })}>{g}</button>)}</div>
          <label className={`${styles.check} ${styles.onlyBelow}`}><input type="checkbox" checked={filters.onlyBelow} onChange={() => set({ onlyBelow: !filters.onlyBelow })} />فقط ارزان‌تر از بازار</label>
          <button className={styles.deskReset} onClick={onReset}>پاک‌کردن فیلترها</button>
        </div>
        <div className={styles.sheetFoot}><button className={styles.apply} onClick={onClose}>نمایش {fa(resultCount)} آگهی</button></div>
      </aside>
      {open && <div className={styles.backdrop} onClick={onClose} />}
    </>
  );
}
