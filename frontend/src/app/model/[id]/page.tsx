import { notFound } from "next/navigation";
import { ModelScreen } from "@/components/ModelScreen";
import { MODELS, findModel } from "@/lib/catalog";

export const generateStaticParams = () => MODELS.map((m) => ({ id: m.id }));

export default async function ModelPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!findModel(id)) notFound();
  return <ModelScreen modelId={id} />;
}
