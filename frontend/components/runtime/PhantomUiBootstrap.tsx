"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

export const PhantomUiBootstrap = () => {
    const pathname = usePathname();

    useEffect(() => {
        if (pathname === "/") return;
        void import("@aejkatappaja/phantom-ui");
    }, [pathname]);

    return null;
};
