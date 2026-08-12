import type { Metadata } from "next";

import { LightRunningIntro } from "@/components/light-running/LightRunningIntro";

export const metadata: Metadata = {
    title: "Light Running",
};

export default function LightRunningPage() {
    return <LightRunningIntro />;
}
