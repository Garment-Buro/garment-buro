"use client";

import { useSearchParams } from "next/navigation";

import { PresentationSurface } from "./PresentationSurface";

export function CatalogPresentationOverlay() {
    const searchParams = useSearchParams();

    if (searchParams.get("presentation") !== "open") return null;

    return <PresentationSurface isOverlay />;
}
