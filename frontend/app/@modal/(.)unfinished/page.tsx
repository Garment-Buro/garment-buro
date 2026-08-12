"use client";

import { useRouter } from "next/navigation";
import { UnfinishedSurface } from "@/components/unfinished/UnfinishedSurface";

export default function UnfinishedOverlay() {
    const router = useRouter();

    return (
        <UnfinishedSurface
            isOverlay
            onClose={() => router.back()}
        />
    );
}
