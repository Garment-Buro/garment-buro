import type { ReactNode } from 'react';

import styles from './ServiceHome.module.css';

/** A manually scrollable preview rail. */
export function ServicePreviewRail({ children, className, label, resetKey }: {
    children: ReactNode;
    className: string;
    label: string;
    resetKey?: string;
}) {
    return <div key={resetKey} className={`${styles.rail} ${className}`} tabIndex={0} role="group" aria-label={label}>
        {children}
    </div>;
}
