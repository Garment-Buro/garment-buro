import type { ReactNode } from 'react';
import Image from 'next/image';
import { PiPackage } from 'react-icons/pi';
import styles from './ProductionFlow.module.css';

export function ProductionMark() {
    return (
        <span className={styles.brandMark} aria-hidden="true">
            <Image
                src="/production/production-mark.svg"
                alt=""
                width={48}
                height={48}
                priority
            />
        </span>
    );
}

export function TerminalState({
    title,
    children,
    icon = <PiPackage aria-hidden="true" />,
    loading = false,
}: {
    title?: string;
    children: ReactNode;
    icon?: ReactNode;
    loading?: boolean;
}) {
    return (
        <div
            className={loading ? styles.skeleton : styles.empty}
            role={loading ? 'status' : undefined}
        >
            {!loading && icon}
            {title && <h2>{title}</h2>}
            <p>{children}</p>
        </div>
    );
}
