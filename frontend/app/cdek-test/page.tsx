"use client";

import { CdekLabHeader } from '@/components/cdek/CdekLabHeader';
import { CdekOfficeResults } from '@/components/cdek/CdekOfficeResults';
import { CdekSelectedOffice } from '@/components/cdek/CdekSelectedOffice';
import { useCdekTestPage } from '@/hooks/cdek/useCdekTestPage';

export default function CdekTestPage() {
    const controller = useCdekTestPage();

    return (
        <main className="min-h-screen bg-[#F2F2F2] px-4 py-8 text-black md:px-8 md:py-12">
            <div className="mx-auto flex w-full max-w-[1180px] flex-col gap-6">
                <CdekLabHeader controller={controller} />
                <section className="grid gap-5 lg:grid-cols-[1fr_380px]">
                    <CdekOfficeResults controller={controller} />
                    <CdekSelectedOffice controller={controller} />
                </section>
            </div>
        </main>
    );
}
