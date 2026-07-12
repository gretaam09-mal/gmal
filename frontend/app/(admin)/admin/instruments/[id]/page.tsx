import { InstrumentWorkbench } from "@/features/admin/components/InstrumentWorkbench";

export default function InstrumentDetailPage({ params }: { params: { id: string } }) {
  return <InstrumentWorkbench instrumentId={params.id} />;
}
