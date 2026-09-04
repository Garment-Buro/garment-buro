import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PresentationSurface } from "@/components/presentation/PresentationSurface";
import { PUBLIC_CATALOG_ENABLED } from "@/lib/catalog/public";

export const metadata: Metadata = {
    title: "Презентация",
    robots: { index: false },
};

export default function PresentationPage() {
    if (!PUBLIC_CATALOG_ENABLED) notFound();
    return <PresentationSurface />;
}
