const PATHS = {
  search: "M11 3a8 8 0 1 0 0 16 8 8 0 0 0 0-16zm10 18-4.3-4.3",
  bell: "M10.3 21a1.9 1.9 0 0 0 3.4 0M3.3 17A2 2 0 0 0 5 20h14a2 2 0 0 0 1.7-3A11 11 0 0 1 19 11.5V9a7 7 0 0 0-14 0v2.5A11 11 0 0 1 3.3 17",
  sparkles: "M9.9 2.2a.5.5 0 0 1 .9 0l1.5 4.1a4 4 0 0 0 2.4 2.4l4.1 1.5a.5.5 0 0 1 0 .9l-4.1 1.5a4 4 0 0 0-2.4 2.4l-1.5 4.1a.5.5 0 0 1-.9 0l-1.5-4.1a4 4 0 0 0-2.4-2.4L2 11.1a.5.5 0 0 1 0-.9l4.1-1.5a4 4 0 0 0 2.4-2.4zM20 3v4M22 5h-4M4 17v2M5 18H3",
  trendDown: "M16 17h6v-6M22 17l-8.5-8.5-5 5L2 7",
  filter: "M10 20a1 1 0 0 0 .6.9 1 1 0 0 0 1-.1l2-1.5a1 1 0 0 0 .4-.8v-4.6a1 1 0 0 1 .3-.7L20.7 6.3A1 1 0 0 0 20 4.6H4a1 1 0 0 0-.7 1.7l6.4 6.9a1 1 0 0 1 .3.7z",
  chevronDown: "m6 9 6 6 6-6",
  bookmark: "m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z",
  send: "m12 19-7-7 7-7M19 12H5",
  home: "M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8M3 10a2 2 0 0 1 .7-1.5l7-6a2 2 0 0 1 2.6 0l7 6A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  compare: "M5 4h5a2 2 0 0 1 2 2v14H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM14 4h5a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-5z",
  estimate: "M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM6 8h12v3H6zM7 15h1M11.5 15h1M16 15h1",
} as const;

export type IconName = keyof typeof PATHS;

interface IconProps { name?: IconName; d?: string; size?: number; stroke?: string; fill?: string; className?: string; }

export function Icon({ name, d, size = 18, stroke = "currentColor", fill = "none", className }: Readonly<IconProps>) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={fill} stroke={stroke} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true" style={{ flexShrink: 0 }}>
      <path d={d ?? (name ? PATHS[name] : "")} />
    </svg>
  );
}
