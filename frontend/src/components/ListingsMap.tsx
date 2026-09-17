"use client";

import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { RED } from "@/lib/catalog";
import { fa, num } from "@/lib/format";
import { verdictOf } from "@/lib/pricing";
import type { Listing } from "@/lib/types";

const TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const SINGLE_ZOOM = 13;
const APPROXIMATE_RADIUS_M = 900;
const BOUNDS_PADDING = 0.3;

export default function ListingsMap({ listings, single = false }: { listings: Listing[]; single?: boolean }) {
  const elementRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    if (!elementRef.current || listings.length === 0) return;
    const map = L.map(elementRef.current, { scrollWheelZoom: !single });
    L.tileLayer(TILE_URL, { attribution: "© OpenStreetMap" }).addTo(map);
    for (const l of listings) {
      L.circleMarker([l.lat, l.lng], { radius: 9, color: "#fff", weight: 2, fillColor: verdictOf(l.diffPct).color, fillOpacity: 0.95 })
        .bindTooltip(`${l.modelName} ${fa(l.year)} · ${num(l.price)} میلیون`, { direction: "top" })
        .on("click", () => router.push(`/listing/${l.id}`)).addTo(map);
    }
    if (single) {
      const [only] = listings;
      L.circle([only.lat, only.lng], { radius: APPROXIMATE_RADIUS_M, color: RED, weight: 1, fillColor: RED, fillOpacity: 0.12 }).addTo(map);
      map.setView([only.lat, only.lng], SINGLE_ZOOM);
    } else {
      map.fitBounds(L.latLngBounds(listings.map((l) => [l.lat, l.lng] as [number, number])).pad(BOUNDS_PADDING));
    }
    return () => { map.remove(); };
  }, [listings, single, router]);

  return <div ref={elementRef} style={{ width: "100%", height: "100%", background: "#eef0f3", position: "relative", zIndex: 0, isolation: "isolate" }} />;
}
