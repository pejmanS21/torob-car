import { Skeleton } from "@/components/Skeleton";

export default function Loading() {
  return (
    <section style={{ padding: "20px 0" }}>
      <Skeleton lines={[20, 48, 220, 320]} />
    </section>
  );
}
