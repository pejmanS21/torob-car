"use client";
import { useState } from "react";
import type { Category, DocumentStatus, FacetCount, Facets, Gearbox, PriceType, Source } from "@/lib/api/types";
import { fa, formatToman } from "@/lib/format";
import { CATEGORY_NAMES, CATEGORY_ORDER, DOCUMENT_STATUS_NAMES, GEARBOX_NAMES, PRICE_TYPE_NAMES, SOURCE_NAMES } from "@/lib/labels";
import { DOCUMENT_STATUSES, GEARBOXES, PRICE_TYPES, SOURCES, activeFilterCount, type SearchOverrides } from "@/lib/search";
import { Icon } from "./Icon";
import styles from "./FiltersPanel.module.css";

const MILLION = 1_000_000;
const PRICE_STEPS = [100, 200, 300, 500, 700, 1_000, 1_500, 2_000, 3_000, 5_000, 10_000, 20_000].map((m) => m * MILLION);
const KM_STEPS = [10_000, 30_000, 50_000, 90_000, 120_000, 150_000, 200_000, 300_000];
const FALLBACK_NEWEST_YEAR = 1405; // only until /facets answers with the real newest year
const YEAR_SPAN = 30;
const MODELS_SHOWN = 6;
const CITIES_SHOWN = 8;
const EXPANDED_SHOWN = 24;
const FROM_QUERY = "از متن جست‌وجو";
const SPARSE_HINT = "آگهی‌هایی که این را ننوشته‌اند هم می‌مانند.";

const kmLabel = (km: number): string => (km >= 1_000 ? `${fa(Math.round(km / 1_000))} هزار` : fa(km));

function toggled<T>(list: T[], item: T): T[] | undefined {
  const next = list.includes(item) ? list.filter((x) => x !== item) : [...list, item];
  return next.length ? next : undefined;
}

const rangeSummary = (min: number | undefined, max: number | undefined, format: (v: number) => string): string =>
  min && max ? `${format(min)} تا ${format(max)}` : min ? `از ${format(min)}` : max ? `تا ${format(max)}` : "";

/** Chosen options first, then the rest by count — so what is on never hides below the fold. */
const ordered = (chosen: string[], counted: string[]): string[] => [...new Set([...chosen, ...counted])];

interface Props { params: SearchOverrides; facets: Facets | null; onChange(next: SearchOverrides): void; onReset(): void; open: boolean; onClose(): void; resultCount: number | null; }

export function FiltersPanel({ params, facets, onChange, onReset, open, onClose, resultCount }: Props) {
  const [moreModels, setMoreModels] = useState(false);
  const [moreCities, setMoreCities] = useState(false);
  const set = (patch: Partial<SearchOverrides>) => onChange({ ...params, ...patch });

  // What is in force: a ticked filter wins, otherwise whatever the query text implied.
  const applied = facets?.applied;
  const category = params.category ?? applied?.category ?? undefined;
  const models = params.models ?? applied?.models ?? [];
  const cities = params.cities ?? applied?.cities ?? [];
  const gearbox = params.gearbox ?? applied?.gearbox ?? undefined;
  const sources = params.sources ?? applied?.sources ?? [];
  const priceTypes = params.price_types ?? applied?.price_types ?? [];
  const documentStatuses = params.document_statuses ?? applied?.document_statuses ?? [];
  const priceMin = params.price_min ?? applied?.price_min ?? undefined;
  const priceMax = params.price_max ?? applied?.price_max ?? undefined;
  const kmMin = params.km_min ?? applied?.km_min ?? undefined;
  const kmMax = params.km_max ?? applied?.km_max ?? undefined;
  const yearMin = params.year_min ?? applied?.year_min ?? undefined;
  const yearMax = params.year_max ?? applied?.year_max ?? undefined;
  const onlyBelow = params.only_below ?? applied?.only_below_market ?? false;

  const countIn = (rows: FacetCount[] | undefined, value: string): string => (rows ? fa(rows.find((row) => row.value === value)?.count ?? 0) : "");
  const modelCount = (model: string): string => (facets ? fa(facets.models.find((row) => row.model === model)?.count ?? 0) : "");
  const allModels = ordered(models, facets?.models.map((row) => row.model) ?? []);
  const allCities = ordered(cities, facets?.cities.map((row) => row.value) ?? []);
  const shownModels = allModels.slice(0, Math.max(models.length, moreModels ? EXPANDED_SHOWN : MODELS_SHOWN));
  const shownCities = allCities.slice(0, Math.max(cities.length, moreCities ? EXPANDED_SHOWN : CITIES_SHOWN));
  const shownSources = SOURCES.filter((source) => sources.includes(source) || (facets?.sources.some((row) => row.value === source) ?? true));
  // An option that would give nothing is noise — unless it is the one that is on.
  const shownCategories = CATEGORY_ORDER.filter((option) => !facets || option === category || (facets.categories[option] ?? 0) > 0);
  const newestYear = facets?.ranges.year_max ?? FALLBACK_NEWEST_YEAR;
  const years = Array.from({ length: YEAR_SPAN }, (_, i) => newestYear - i);
  const showGearbox = !category || category === "light";
  const activeCount = activeFilterCount(params);

  // Only ticked filters get a chip: what the query implied is already spelled out above
  // the results, and is highlighted in place below.
  const chips: { key: string; label: string; remove(): void }[] = [
    ...(params.category ? [{ key: "category", label: CATEGORY_NAMES[params.category], remove: () => set({ category: undefined, models: undefined, gearbox: undefined }) }] : []),
    ...(params.models ?? []).map((model) => ({ key: `m:${model}`, label: model, remove: () => set({ models: toggled(params.models ?? [], model) }) })),
    ...(params.cities ?? []).map((city) => ({ key: `c:${city}`, label: city, remove: () => set({ cities: toggled(params.cities ?? [], city) }) })),
    ...(params.price_min || params.price_max ? [{ key: "price", label: rangeSummary(params.price_min, params.price_max, formatToman), remove: () => set({ price_min: undefined, price_max: undefined }) }] : []),
    ...(params.year_min || params.year_max ? [{ key: "year", label: `سال ${rangeSummary(params.year_min, params.year_max, fa)}`, remove: () => set({ year_min: undefined, year_max: undefined }) }] : []),
    ...(params.km_min || params.km_max ? [{ key: "km", label: `کارکرد ${rangeSummary(params.km_min, params.km_max, kmLabel)}`, remove: () => set({ km_min: undefined, km_max: undefined }) }] : []),
    ...(params.gearbox ? [{ key: "gearbox", label: GEARBOX_NAMES[params.gearbox], remove: () => set({ gearbox: undefined }) }] : []),
    ...(params.sources ?? []).map((source) => ({ key: `s:${source}`, label: SOURCE_NAMES[source], remove: () => set({ sources: toggled(params.sources ?? [], source) }) })),
    ...(params.price_types ?? []).map((type) => ({ key: `p:${type}`, label: PRICE_TYPE_NAMES[type], remove: () => set({ price_types: toggled(params.price_types ?? [], type) }) })),
    ...(params.document_statuses ?? []).map((status) => ({ key: `d:${status}`, label: DOCUMENT_STATUS_NAMES[status], remove: () => set({ document_statuses: toggled(params.document_statuses ?? [], status) }) })),
    ...(params.only_below ? [{ key: "below", label: "ارزان‌تر از بازار", remove: () => set({ only_below: undefined }) }] : []),
  ];

  return (
    <>
      <aside className={styles.panel} data-open={open}>
        <div className={styles.sheetHead}><span className={styles.grabber} /></div>
        <div className={styles.head}>
          <span className={styles.title}>فیلترها{activeCount > 0 && <span className={styles.badge}>{fa(activeCount)}</span>}</span>
          {activeCount > 0 && <button type="button" className={styles.clear} onClick={onReset}>پاک‌کردن همه</button>}
        </div>
        <div className={styles.body}>
          {chips.length > 0 && (
            <div className={styles.chips}>{chips.map((chip) => (
              <button key={chip.key} type="button" className={styles.chip} onClick={chip.remove} aria-label={`حذف فیلتر ${chip.label}`}>{chip.label}<span aria-hidden="true">×</span></button>
            ))}</div>
          )}
          <label className={styles.switchRow}>
            <input type="checkbox" checked={onlyBelow} onChange={() => set({ only_below: onlyBelow ? undefined : true })} />
            فقط ارزان‌تر از بازار
          </label>

          <Section title="دسته" summary={category ? CATEGORY_NAMES[category] : ""} defaultOpen>
            <div className={styles.pills}>
              <button type="button" className={styles.pill} data-on={!category} aria-pressed={!category} onClick={() => set({ category: undefined, models: undefined, gearbox: undefined })}>همه</button>
              {shownCategories.map((option: Category) => (
                <button key={option} type="button" className={styles.pill} data-on={category === option} data-implied={category === option && !params.category} title={category === option && !params.category ? FROM_QUERY : undefined} aria-pressed={category === option} onClick={() => set({ category: option, models: undefined, gearbox: option === "light" ? params.gearbox : undefined })}>
                  {CATEGORY_NAMES[option]}<span className={styles.count}>{facets ? fa(facets.categories[option] ?? 0) : ""}</span>
                </button>
              ))}
            </div>
          </Section>

          <Section title="مدل" summary={models.join("، ")} defaultOpen>
            <div className={styles.checks}>{shownModels.map((model) => {
              const implied = models.includes(model) && !params.models?.includes(model);
              return (
                <label key={model} className={styles.check} data-implied={implied} title={implied ? FROM_QUERY : undefined}>
                  <input type="checkbox" checked={models.includes(model)} onChange={() => set({ models: toggled(models, model) })} />{model}<span className={styles.count}>{modelCount(model)}</span>
                </label>
              );
            })}</div>
            {allModels.length > shownModels.length || moreModels ? <button type="button" className={styles.more} onClick={() => setMoreModels(!moreModels)}>{moreModels ? "کمتر" : `${fa(Math.min(allModels.length, EXPANDED_SHOWN) - shownModels.length)} مدل دیگر`}</button> : null}
          </Section>

          <Section title="شهر" summary={cities.join("، ")} defaultOpen>
            <div className={styles.pills}>{shownCities.map((city) => {
              const implied = cities.includes(city) && !params.cities?.includes(city);
              return <button key={city} type="button" className={styles.pill} data-on={cities.includes(city)} data-implied={implied} title={implied ? FROM_QUERY : undefined} aria-pressed={cities.includes(city)} onClick={() => set({ cities: toggled(cities, city) })}>{city}<span className={styles.count}>{countIn(facets?.cities, city)}</span></button>;
            })}</div>
            {allCities.length > shownCities.length || moreCities ? <button type="button" className={styles.more} onClick={() => setMoreCities(!moreCities)}>{moreCities ? "کمتر" : `${fa(Math.min(allCities.length, EXPANDED_SHOWN) - shownCities.length)} شهر دیگر`}</button> : null}
          </Section>

          <Section title="قیمت" summary={rangeSummary(priceMin, priceMax, formatToman)} defaultOpen>
            <RangeRow label="قیمت" min={priceMin} max={priceMax} steps={PRICE_STEPS} format={formatToman} reach={[facets?.ranges.price_min, facets?.ranges.price_max]} onChange={(min, max) => set({ price_min: min, price_max: max })} />
          </Section>

          <Section title="سال ساخت" summary={rangeSummary(yearMin, yearMax, fa)} defaultOpen={Boolean(yearMin || yearMax)}>
            <RangeRow label="سال" min={yearMin} max={yearMax} steps={years} format={fa} reach={[facets?.ranges.year_min, facets?.ranges.year_max]} onChange={(min, max) => set({ year_min: min, year_max: max })} />
          </Section>

          <Section title="کارکرد" summary={rangeSummary(kmMin, kmMax, kmLabel)} defaultOpen={Boolean(kmMin || kmMax)}>
            <RangeRow label="کارکرد" min={kmMin} max={kmMax} steps={KM_STEPS} format={kmLabel} unit="کیلومتر" reach={[facets?.ranges.km_min, facets?.ranges.km_max]} onChange={(min, max) => set({ km_min: min, km_max: max })} />
          </Section>

          {showGearbox && (
            <Section title="گیربکس" summary={gearbox ? GEARBOX_NAMES[gearbox] : ""} defaultOpen={Boolean(gearbox)}>
              <div className={styles.pills}>{GEARBOXES.map((option: Gearbox) => (
                <button key={option} type="button" className={styles.pill} data-on={gearbox === option} data-empty={Boolean(facets) && gearbox !== option && !facets?.gearboxes.some((row) => row.value === option)} data-implied={gearbox === option && !params.gearbox} title={gearbox === option && !params.gearbox ? FROM_QUERY : undefined} aria-pressed={gearbox === option} onClick={() => set({ gearbox: params.gearbox === option ? undefined : option })}>
                  {GEARBOX_NAMES[option]}<span className={styles.count}>{countIn(facets?.gearboxes, option)}</span>
                </button>
              ))}</div>
            </Section>
          )}

          <Section title="فروشگاه" summary={sources.map((source) => SOURCE_NAMES[source]).join("، ")} defaultOpen={sources.length > 0}>
            <div className={styles.pills}>{shownSources.map((source: Source) => (
              <button key={source} type="button" className={styles.pill} data-on={sources.includes(source)} aria-pressed={sources.includes(source)} onClick={() => set({ sources: toggled(sources, source) })}>
                {SOURCE_NAMES[source]}<span className={styles.count}>{countIn(facets?.sources, source)}</span>
              </button>
            ))}</div>
          </Section>

          <Section title="نوع قیمت" summary={priceTypes.map((type) => PRICE_TYPE_NAMES[type]).join("، ")} defaultOpen={priceTypes.length > 0}>
            <div className={styles.pills}>{PRICE_TYPES.map((type: PriceType) => (
              <button key={type} type="button" className={styles.pill} data-on={priceTypes.includes(type)} aria-pressed={priceTypes.includes(type)} onClick={() => set({ price_types: toggled(priceTypes, type) })}>{PRICE_TYPE_NAMES[type]}</button>
            ))}</div>
            <div className={styles.hint}>{SPARSE_HINT}</div>
          </Section>

          <Section title="سند" summary={documentStatuses.map((status) => DOCUMENT_STATUS_NAMES[status]).join("، ")} defaultOpen={documentStatuses.length > 0}>
            <div className={styles.pills}>{DOCUMENT_STATUSES.map((status: DocumentStatus) => (
              <button key={status} type="button" className={styles.pill} data-on={documentStatuses.includes(status)} aria-pressed={documentStatuses.includes(status)} onClick={() => set({ document_statuses: toggled(documentStatuses, status) })}>{DOCUMENT_STATUS_NAMES[status]}</button>
            ))}</div>
            <div className={styles.hint}>{SPARSE_HINT}</div>
          </Section>
        </div>
        <div className={styles.sheetFoot}><button type="button" className={styles.apply} onClick={onClose}>{resultCount === null ? "نمایش آگهی‌ها" : `نمایش ${fa(resultCount)} آگهی`}</button></div>
      </aside>
      {open && <div className={styles.backdrop} onClick={onClose} />}
    </>
  );
}

/** A collapsible group. Collapsed, its summary still says what is chosen inside. */
function Section({ title, summary, defaultOpen, children }: { title: string; summary: string; defaultOpen: boolean; children: React.ReactNode }) {
  return (
    <details className={styles.section} open={defaultOpen}>
      <summary className={styles.summary}>
        <span className={styles.sectionTitle}>{title}</span>
        {summary && <span className={styles.summaryValue}>{summary}</span>}
        <Icon name="chevronDown" stroke="#98a2b3" size={16} className={styles.chev} />
      </summary>
      <div className={styles.sectionBody}>{children}</div>
    </details>
  );
}

interface RangeRowProps {
  label: string; min: number | undefined; max: number | undefined; steps: number[]; format(value: number): string; unit?: string;
  reach: [number | null | undefined, number | null | undefined]; onChange(min: number | undefined, max: number | undefined): void;
}

/** «از … تا …». Each end only offers values that keep the range valid, and a bound the
 * query text set (say «زیر ۷۵۰ میلیون») joins the steps so it shows as selected. */
function RangeRow({ label, min, max, steps, format, unit, reach, onChange }: RangeRowProps) {
  const options = [...new Set([...steps, ...(min ? [min] : []), ...(max ? [max] : [])])].sort((a, b) => a - b);
  const [low, high] = reach;
  const pick = (value: string): number | undefined => (value ? Number(value) : undefined);
  return (
    <>
      <div className={styles.range}>
        <select className={styles.select} value={min ?? ""} onChange={(event) => onChange(pick(event.target.value), max)} aria-label={`حداقل ${label}`}>
          <option value="">از</option>
          {options.filter((step) => !max || step < max).map((step) => <option key={step} value={step}>{format(step)}</option>)}
        </select>
        <span className={styles.rangeDash}>تا</span>
        <select className={styles.select} value={max ?? ""} onChange={(event) => onChange(min, pick(event.target.value))} aria-label={`حداکثر ${label}`}>
          <option value="">بدون سقف</option>
          {options.filter((step) => !min || step > min).map((step) => <option key={step} value={step}>{format(step)}</option>)}
        </select>
      </div>
      {low != null && high != null && <div className={styles.hint}>در این جست‌وجو: {format(low)} تا {format(high)}{unit ? ` ${unit}` : ""}</div>}
    </>
  );
}
