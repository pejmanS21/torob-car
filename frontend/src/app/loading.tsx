import { Skeleton } from "@/components/Skeleton";

export default function Loading() {
  return (
    <section style={{ padding: "48px 0" }}>
      <Skeleton lines={[40, 56, 20]} width="min(680px, 100%)" />
    </section>
  );
}
