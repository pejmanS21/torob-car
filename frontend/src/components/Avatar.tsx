"use client";

import { useEffect, useRef, useState } from "react";
import type { AvatarAnimation } from "@/state/AppState";

const DEFINITION_URL = "/strobi.avatar.json";
const DEFAULT_BODY = "#68b828";

interface AvatarProps { size: number; body?: string; animation?: AvatarAnimation; }
interface Controller { play(animation: string): void; destroy(): void; }

function FallbackFace({ color }: { color: string }) {
  return (
    <svg viewBox="-150 -150 300 300" width="100%" height="100%" aria-label="دستیار" role="img">
      <circle r="120" fill={color} />
      <ellipse cx="-35" cy="-7" rx="10" ry="25" fill="#111316" />
      <ellipse cx="35" cy="-7" rx="10" ry="25" fill="#111316" />
    </svg>
  );
}

export function Avatar({ size, body = DEFAULT_BODY, animation = "idle" }: AvatarProps) {
  const boxRef = useRef<HTMLSpanElement>(null);
  const controllerRef = useRef<Controller | null>(null);
  const animationRef = useRef(animation);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function mount() {
      try {
        const [{ createAvatar }, definition] = await Promise.all([
          import("@bible-strong/avatar-web"),
          fetch(DEFINITION_URL).then((r) => { if (!r.ok) throw new Error(`avatar definition ${r.status}`); return r.json(); }),
        ]);
        if (cancelled || !boxRef.current) return;
        controllerRef.current = createAvatar(boxRef.current, {
          definition: { ...definition, colors: { ...definition.colors, body } }, defaultAnimation: animationRef.current, size: "100%", ariaLabel: "دستیار",
        });
      } catch (error) {
        console.warn("[Avatar] falling back to static face", error);
        if (!cancelled) setFailed(true);
      }
    }
    mount();
    return () => { cancelled = true; controllerRef.current?.destroy(); controllerRef.current = null; };
  }, [body]);

  useEffect(() => { animationRef.current = animation; controllerRef.current?.play(animation); }, [animation]);

  return (
    <span ref={boxRef} style={{ display: "block", width: size, height: size, overflow: "hidden", lineHeight: 0, flexShrink: 0 }}>
      {failed && <FallbackFace color={body} />}
    </span>
  );
}
