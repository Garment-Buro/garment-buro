import type { Metadata } from "next";

import { PresentationSurface } from "@/components/presentation/PresentationSurface";

export const metadata: Metadata = {
    title: "Презентация",
    robots: { index: false },
};

export default function PresentationPage() {
    return <PresentationSurface />;
}
