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
    const [copied, setCopied] = useState(false);
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
                <output className={styles.accessCode} aria-label="Код доступа">
                    {result.code}
                </output>
                <div className={styles.editorActions}>
                    <button
                        type="button"
                        onClick={async () => {
                            await navigator.clipboard.writeText(result.code || '');
                            setCopied(true);
                        }}
                    >
                        {copied ? 'Скопировано' : 'Скопировать код'}
                    </button>
                    <button type="button" onClick={onClose}>
                        Я сохранил код
                    </button>
                </div>
            </section>
        </div>
    );
}
