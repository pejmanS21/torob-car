import { Skeleton } from "@/components/Skeleton";

export default function Loading() {
  return (
    <section style={{ display: "grid", gridTemplateColumns: "minmax(0, 2fr) minmax(0, 1fr)", gap: 20, padding: "20px 0" }}>
      <Skeleton lines={[380, 80, 120, 160]} />
      <Skeleton lines={[200, 160, 200]} />
    </section>
  );
}
