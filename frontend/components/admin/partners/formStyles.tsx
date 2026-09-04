import type { ReactNode } from 'react';

export const inputClass = 'h-11 w-full rounded-lg border border-black/15 bg-white px-3 text-sm outline-none transition focus:border-black focus:ring-2 focus:ring-black/10';

export const Field = ({ label, wide = false, children }: { label: string; wide?: boolean; children: ReactNode }) => (
    <label className={wide ? 'block sm:col-span-2' : 'block'}>
        <span className="mb-2 block text-sm font-medium text-black/70">{label}</span>
        {children}
    </label>
);
