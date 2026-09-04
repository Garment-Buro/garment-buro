"use client";

import { useEffect } from 'react';

import { registerPartnerVisit } from '@/lib/api/partners';

export const PartnerAttributionBootstrap = ({ slug }: { slug: string }) => {
    useEffect(() => {
        void registerPartnerVisit(slug).catch(() => {
            // The landing remains usable when analytics is temporarily unavailable.
        });
    }, [slug]);

    return null;
};
