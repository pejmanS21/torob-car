"use client";
import type { SortKey } from "@/lib/api/types";
import { SORT_NAMES } from "@/lib/labels";
import { SORTS } from "@/lib/search";
import { useAppState } from "@/state/AppState";
import { Icon } from "./Icon";
import styles from "./ResultsToolbar.module.css";

interface Props {
  countFa: string;
  subtitle: string;
  filtersLabel: string;
  onOpenFilters(): void;
  sort: SortKey;
  onSort(sort: SortKey): void;
  onSave(): void;
}

export function ResultsToolbar({ countFa, subtitle, filtersLabel, onOpenFilters, sort, onSort, onSave }: Props) {
  const { loggedIn } = useAppState();
  const saveLabel = loggedIn ? "ذخیره و هشدار قیمت" : "هشدار قیمت (ورود)";

  return (
    <div className={styles.toolbar}>
      <button className={styles.filterBtn} onClick={onOpenFilters}>
        <Icon name="filter" />
        {filtersLabel}
      </button>
      <h2 className={styles.count}>{countFa} آگهی</h2>
      <span className={styles.subtitle}>{subtitle}</span>
      <div className={styles.toolRight}>
        <button className={styles.saveBtn} title={saveLabel} onClick={onSave}>
          <Icon name="bookmark" />
          <span className={styles.saveLabel}>{saveLabel}</span>
        </button>
        <span className={styles.sortWrap}>
          <select value={sort} onChange={(event) => onSort(event.target.value as SortKey)} className={styles.select} aria-label="مرتب‌سازی">
            {SORTS.map((key) => <option key={key} value={key}>{SORT_NAMES[key]}</option>)}
          </select>
          <Icon name="chevronDown" stroke="#667085" className={styles.sortChev} />
        </span>
      </div>
    </div>
  );
}
