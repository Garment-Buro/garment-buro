import type { Metadata } from "next";

import { PresentationSurface } from "@/components/presentation/PresentationSurface";

export const metadata: Metadata = {
    title: "Презентация",
};

export default function PresentationPage() {
    return <PresentationSurface />;
}
