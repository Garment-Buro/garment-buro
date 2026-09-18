'use client';

import { useState } from 'react';
import { type AdminEmployeeCodeResponse } from '@/lib/production/adminTypes';
import styles from './ProductionAdmin.module.css';

export function AdminEmployeeAccessCode({
    result,
    onClose,
}: {
    result: AdminEmployeeCodeResponse;
    onClose: () => void;
}) {
    const [copyState, setCopyState] = useState<
        'idle' | 'copied' | 'error'
    >('idle');
    if (!result.code) return null;
    return (
        <div className={styles.modalBackdrop} role="presentation">
            <section
                className={styles.codeDialog}
                role="dialog"
                aria-modal="true"
                aria-labelledby="employee-code-title"
            >
                <p className={styles.eyebrow}>ЛИЧНЫЙ КОД СОТРУДНИКА</p>
                <h2 id="employee-code-title">Передайте код лично</h2>
                <p>
                    Код для {result.employee.name}. После закрытия его нельзя будет
                    посмотреть — только заменить новым.
                </p>
                <div className={styles.accessCodeRow}>
                    <output
                        className={styles.accessCode}
                        aria-label="Код доступа"
                    >
                        {result.code}
                    </output>
                    <button
                        className={styles.copyCodeButton}
                        type="button"
                        aria-label="Скопировать код сотрудника"
                        title="Скопировать код"
                        onClick={async () => {
                            try {
                                await navigator.clipboard.writeText(
                                    result.code || '',
                                );
                                setCopyState('copied');
                            } catch {
                                setCopyState('error');
                            }
                        }}
                    >
                        {copyState === 'copied' ? (
                            <svg
                                viewBox="0 0 24 24"
                                width="24"
                                height="24"
                                fill="none"
                                aria-hidden="true"
                            >
                                <path
                                    d="m5 12 4 4L19 6"
                                    stroke="currentColor"
                                    strokeWidth="2"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                />
                            </svg>
                        ) : (
                            <svg
                                viewBox="0 0 24 24"
                                width="24"
                                height="24"
                                fill="none"
                                aria-hidden="true"
                            >
                                <rect
                                    x="8"
                                    y="8"
                                    width="11"
                                    height="11"
                                    rx="2"
                                    stroke="currentColor"
                                    strokeWidth="2"
                                />
                                <path
                                    d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"
                                    stroke="currentColor"
                                    strokeWidth="2"
                                    strokeLinecap="round"
                                />
                            </svg>
                        )}
                    </button>
                </div>
                <p
                    className={copyState === 'error' ? styles.error : styles.copyStatus}
                    role="status"
                    aria-live="polite"
                >
                    {copyState === 'copied'
                        ? 'Код скопирован.'
                        : copyState === 'error'
                          ? 'Не удалось скопировать. Выделите код вручную.'
                          : 'Нажмите значок рядом с кодом, чтобы скопировать.'}
                </p>
                <div className={styles.editorActions}>
                    <button
                        className={styles.primaryButton}
                        type="button"
                        onClick={onClose}
                    >
                        Я сохранил код
                    </button>
                </div>
            </section>
        </div>
    );
}
