'use client';

import { useEffect, useRef, useState } from 'react';
import { requestJson } from '@/lib/api/http';
import {
    type AdminEmployee,
    type AdminEmployeeCodeResponse,
    type AdminEmployeeWrite,
    type ProductionStation,
    productionStations,
    stationLabels,
} from '@/lib/production/adminTypes';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import styles from './ProductionAdmin.module.css';

const emptyEmployee: AdminEmployeeWrite = {
    first_name: '',
    last_name: '',
    email: null,
    phone: null,
    status: 'active',
    stations: ['tech'],
    primary_station: 'tech',
};

function values(employee: AdminEmployee | null): AdminEmployeeWrite {
    if (!employee) return emptyEmployee;
    return {
        first_name: employee.first_name,
        last_name: employee.last_name,
        email: employee.email,
        phone: employee.phone,
        status: employee.status,
        stations: employee.stations,
        primary_station: employee.primary_station,
    };
}

export function AdminEmployeeEditor({
    employee,
    onClose,
    onSaved,
}: {
    employee: AdminEmployee | null;
    onClose: () => void;
    onSaved: (result: AdminEmployeeCodeResponse, message: string) => void;
}) {
    const [form, setForm] = useState<AdminEmployeeWrite>(() =>
        values(employee),
    );
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const firstInput = useRef<HTMLInputElement>(null);
    const run = useProductionAuthStore((state) => state.runAuthenticated);

    useEffect(() => firstInput.current?.focus(), []);

    const toggleStation = (station: ProductionStation) => {
        setForm((current) => {
            const selected = current.stations.includes(station);
            if (selected && current.stations.length === 1) return current;
            const stations = selected
                ? current.stations.filter((item) => item !== station)
                : [...current.stations, station];
            return {
                ...current,
                stations,
                primary_station: stations.includes(current.primary_station)
                    ? current.primary_station
                    : stations[0],
            };
        });
    };

    const save = async () => {
        const body: AdminEmployeeWrite = {
            ...form,
            first_name: form.first_name.trim(),
            last_name: form.last_name.trim(),
            email: form.email?.trim() || null,
            phone: form.phone?.trim() || null,
        };
        const result = await run(() =>
            requestJson<AdminEmployeeCodeResponse>(
                employee
                    ? `/production/admin/employees/${employee.id}`
                    : '/production/admin/employees',
                {
                    method: employee ? 'PUT' : 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                },
            ),
        );
        onSaved(
            result,
            employee ? 'Данные сотрудника сохранены.' : 'Сотрудник добавлен.',
        );
    };

    const rotate = async () => {
        if (!employee) return;
        const result = await run(() =>
            requestJson<AdminEmployeeCodeResponse>(
                `/production/admin/employees/${employee.id}/code`,
                { method: 'POST' },
            ),
        );
        onSaved(result, 'Новый код выдан. Старый код больше не работает.');
    };

    return (
        <div className={styles.modalBackdrop} role="presentation">
            <section
                className={styles.employeeEditor}
                role="dialog"
                aria-modal="true"
                aria-labelledby="employee-editor-title"
            >
                <div className={styles.sectionHeading}>
                    <div>
                        <p className={styles.eyebrow}>ДОСТУП К ТЕРМИНАЛУ</p>
                        <h2 id="employee-editor-title">
                            {employee ? 'Изменить сотрудника' : 'Новый сотрудник'}
                        </h2>
                    </div>
                    <button type="button" disabled={busy} onClick={onClose}>
                        Закрыть
                    </button>
                </div>
                <form
                    onSubmit={async (event) => {
                        event.preventDefault();
                        if (busy) return;
                        setBusy(true);
                        setError('');
                        try {
                            await save();
                        } catch (failure) {
                            setError(
                                failure instanceof Error
                                    ? failure.message
                                    : 'Не удалось сохранить сотрудника',
                            );
                        } finally {
                            setBusy(false);
                        }
                    }}
                >
                    <div className={styles.formGrid}>
                        <label>
                            Имя
                            <input
                                ref={firstInput}
                                required
                                maxLength={255}
                                autoComplete="off"
                                value={form.first_name}
                                onChange={(event) =>
                                    setForm({
                                        ...form,
                                        first_name: event.target.value,
                                    })
                                }
                            />
                        </label>
                        <label>
                            Фамилия
                            <input
                                maxLength={255}
                                autoComplete="off"
                                value={form.last_name}
                                onChange={(event) =>
                                    setForm({
                                        ...form,
                                        last_name: event.target.value,
                                    })
                                }
                            />
                        </label>
                        <label>
                            Телефон
                            <input
                                type="tel"
                                maxLength={64}
                                autoComplete="off"
                                value={form.phone || ''}
                                onChange={(event) =>
                                    setForm({
                                        ...form,
                                        phone: event.target.value || null,
                                    })
                                }
                            />
                        </label>
                        <label>
                            Почта — необязательно
                            <input
                                type="email"
                                maxLength={320}
                                autoComplete="off"
                                value={form.email || ''}
                                onChange={(event) =>
                                    setForm({
                                        ...form,
                                        email: event.target.value || null,
                                    })
                                }
                            />
                        </label>
                    </div>

                    <fieldset className={styles.roleFieldset}>
                        <legend>Доступные участки</legend>
                        <p className={styles.muted}>
                            Можно выбрать несколько участков. Административная роль
                            здесь не выдаётся.
                        </p>
                        <div className={styles.roleGrid}>
                            {productionStations.map((station) => (
                                <label key={station} className={styles.roleOption}>
                                    <input
                                        type="checkbox"
                                        checked={form.stations.includes(station)}
                                        onChange={() => toggleStation(station)}
                                    />
                                    <span>{stationLabels[station]}</span>
                                </label>
                            ))}
                        </div>
                    </fieldset>

                    <div className={styles.formGrid}>
                        <label>
                            Основной участок
                            <select
                                value={form.primary_station}
                                onChange={(event) =>
                                    setForm({
                                        ...form,
                                        primary_station: event.target
                                            .value as ProductionStation,
                                    })
                                }
                            >
                                {form.stations.map((station) => (
                                    <option key={station} value={station}>
                                        {stationLabels[station]}
                                    </option>
                                ))}
                            </select>
                            <small>По нему формируется первая цифра личного кода.</small>
                        </label>
                        <label>
                            Доступ
                            <select
                                value={form.status}
                                onChange={(event) =>
                                    setForm({
                                        ...form,
                                        status: event.target.value as
                                            | 'active'
                                            | 'blocked',
                                    })
                                }
                            >
                                <option value="active">Активен</option>
                                <option value="blocked">Заблокирован</option>
                            </select>
                            <small>Блокировка сразу отзывает код и текущие сессии.</small>
                        </label>
                    </div>

                    {error && (
                        <p role="alert" className={styles.error}>
                            {error}
                        </p>
                    )}
                    <div className={styles.editorActions}>
                        <button type="submit" disabled={busy || !form.first_name.trim()}>
                            {busy ? 'Сохраняем…' : 'Сохранить'}
                        </button>
                        {employee && employee.status === 'active' && (
                            <button
                                type="button"
                                disabled={busy}
                                onClick={async () => {
                                    if (busy) return;
                                    setBusy(true);
                                    setError('');
                                    try {
                                        await rotate();
                                    } catch (failure) {
                                        setError(
                                            failure instanceof Error
                                                ? failure.message
                                                : 'Не удалось заменить код',
                                        );
                                    } finally {
                                        setBusy(false);
                                    }
                                }}
                            >
                                Выдать новый код
                            </button>
                        )}
                    </div>
                </form>
            </section>
        </div>
    );
}
