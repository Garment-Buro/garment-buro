"use client";

import { useState } from 'react';
import {
    PiArrowSquareOut,
    PiCaretDown,
    PiChatCircleDots,
    PiFiles,
    PiSignOut,
} from 'react-icons/pi';

import styles from './PartnerDashboard.module.css';

const DOCUMENTS = [
    { href: 'https://garment-buro.ru/offer', label: 'Публичная оферта' },
    { href: 'https://garment-buro.ru/policy', label: 'Политика обработки данных' },
    { href: 'https://garment-buro.ru/consent', label: 'Согласие на обработку данных' },
];

export const PartnerResources = ({ onLogout }: { onLogout: () => void }) => {
    const [documentsOpen, setDocumentsOpen] = useState(false);

    return (
        <section className={styles.resourceSection} aria-labelledby="partner-help-title">
            <h2 className={styles.screenReaderOnly} id="partner-help-title">
                Документы и поддержка
            </h2>
            <div className={styles.resourceList}>
                <div>
                    <button
                        type="button"
                        className={styles.resourceRow}
                        onClick={() => setDocumentsOpen(value => !value)}
                        aria-expanded={documentsOpen}
                        aria-controls="partner-documents"
                    >
                        <span className={styles.resourceCopy}>
                            <span className={styles.resourceIcon} aria-hidden="true">
                                <PiFiles size={20} />
                            </span>
                            <span>
                                <span className={styles.resourceTitle}>Правовые документы</span>
                                <span className={styles.resourceDescription}>Оферта, политика и согласие</span>
                            </span>
                        </span>
                        <PiCaretDown
                            size={18}
                            className={`${styles.summaryIcon} ${documentsOpen ? styles.summaryIconOpen : ''}`}
                            aria-hidden="true"
                        />
                    </button>
                    {documentsOpen && (
                        <div className={styles.documentList} id="partner-documents">
                            {DOCUMENTS.map(document => (
                                <a
                                    key={document.href}
                                    className={styles.documentLink}
                                    href={document.href}
                                    target="_blank"
                                    rel="noreferrer"
                                >
                                    {document.label}
                                    <PiArrowSquareOut size={18} aria-hidden="true" />
                                </a>
                            ))}
                        </div>
                    )}
                </div>

                <a
                    className={styles.resourceRow}
                    href="mailto:tverfactoryhelp@gmail.com?subject=Поддержка партнёра Garment Buro"
                >
                    <span className={styles.resourceCopy}>
                        <span className={styles.resourceIcon} aria-hidden="true">
                            <PiChatCircleDots size={20} />
                        </span>
                        <span>
                            <span className={styles.resourceTitle}>Написать в поддержку</span>
                            <span className={styles.resourceDescription}>Ответим на почту партнёра</span>
                        </span>
                    </span>
                    <PiArrowSquareOut size={18} aria-hidden="true" />
                </a>

                <button type="button" className={styles.logoutButton} onClick={onLogout}>
                    <span className={styles.resourceCopy}>
                        <span className={styles.resourceIcon} aria-hidden="true">
                            <PiSignOut size={20} />
                        </span>
                        <span className={styles.resourceTitle}>Выйти из кабинета</span>
                    </span>
                    <PiArrowSquareOut size={18} aria-hidden="true" />
                </button>
            </div>
        </section>
    );
};
