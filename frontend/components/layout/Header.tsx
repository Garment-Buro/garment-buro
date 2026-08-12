"use client";

import React from "react";
import { usePathname } from "next/navigation";
import { AdaptiveHeader } from "@/components/layout/AdaptiveHeader";
import { isSiteChromeHidden } from "@/lib/browser/utils/pageChrome";

export const Header = () => {
    const pathname = usePathname();

    if (isSiteChromeHidden(pathname)) return null;

    return (
        <AdaptiveHeader
            variant="catalog"
            withBackdrop
            fixed
            topOffset={20}
        />
    );
};
