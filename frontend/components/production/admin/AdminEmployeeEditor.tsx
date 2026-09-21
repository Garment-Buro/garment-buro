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
    availability: 'available',
    is_production_admin: false,
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
        availability: employee.availability ?? 'available',
        is_production_admin: employee.is_production_admin,
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

    useEffect(() => {
        firstInput.current?.focus();
        const closeOnEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape' && !busy) onClose();
        };
        window.addEventListener('keydown', closeOnEscape);
        return () => window.removeEventListener('keydown', closeOnEscape);
    }, [busy, onClose]);

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
        <div
            className={styles.modalBackdrop}
            role="presentation"
            onMouseDown={(event) => {
                if (event.target === event.currentTarget && !busy) onClose();
            }}
        >
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
                            {employee
                                ? 'Изменить сотрудника'
                                : 'Новый сотрудник'}
                        </h2>
                        <p className={styles.modalDescription}>
                            Для входа нужен только личный код. Контактные данные
                            можно добавить позже.
                        </p>
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
                    <fieldset className={styles.formSection}>
                        <legend>Личные данные</legend>
                        <div className={styles.formGrid}>
                            <label>
                                Имя
                                <input
                                    ref={firstInput}
                                    required
                                    maxLength={255}
                                    autoComplete="off"
                                    placeholder="Например, Мария"
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
                                Фамилия (необязательно)
                                <input
                                    maxLength={255}
                                    autoComplete="off"
                                    placeholder="Можно оставить пустой"
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
                                Телефон (необязательно)
                                <input
                                    type="tel"
                                    maxLength={64}
                                    autoComplete="off"
                                    placeholder="Можно оставить пустым"
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
                                Почта (необязательно)
                                <input
                                    type="email"
                                    maxLength={320}
                                    autoComplete="off"
                                    placeholder="name@example.ru"
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
                    </fieldset>

                    <fieldset className={styles.formSection}>
                        <legend>Рабочий доступ</legend>
                        <div className={styles.formGrid}>
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
                                    <option value="active">Доступ открыт</option>
                                    <option value="blocked">Доступ закрыт</option>
                                </select>
                            </label>
                            <label>
                                Доступность
                                <select
                                    value={form.availability}
                                    onChange={(event) =>
                                        setForm((current) => ({
                                            ...current,
                                            availability: event.target
                                                .value as AdminEmployeeWrite['availability'],
                                        }))
                                    }
                                >
                                    <option value="available">Работает</option>
                                    <option value="sick">Болеет</option>
                                    <option value="vacation">В отпуске</option>
                                    <option value="absent">Отсутствует</option>
                                </select>
                                <small>
                                    Вне работы личный код временно не действует.
                                </small>
                            </label>
                        </div>
                        <label className={styles.roleOption}>
                            <input
                                type="checkbox"
                                checked={form.is_production_admin}
                                onChange={(event) =>
                                    setForm({
                                        ...form,
                                        is_production_admin:
                                            event.target.checked,
                                    })
                                }
                            />
                            <span>Производственный администратор</span>
                        </label>
                        <small>
                            Получит отдельный восьмизначный код и доступ только
                            к заказам, этапам производства и проблемам.
                        </small>
                    </fieldset>

                    <fieldset className={styles.roleFieldset}>
                        <legend>Участки производства</legend>
                        <p className={styles.muted}>
                            Выберите один или несколько участков, затем укажите
                            основной. Выбрано: {form.stations.length}.
                        </p>
                        <div className={styles.roleGrid}>
                            {productionStations.map((station) => (
                                <label
                                    key={station}
                                    className={styles.roleOption}
                                >
                                    <input
                                        type="checkbox"
                                        checked={form.stations.includes(
                                            station,
                                        )}
                                        onChange={() => toggleStation(station)}
                                    />
                                    <span>{stationLabels[station]}</span>
                                </label>
                            ))}
                        </div>
                        <label className={styles.primaryStation}>
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
                            <small>
                                Для обычного сотрудника по нему формируется
                                первая цифра кода. Администратору выдаётся код с
                                префиксом 99.
                            </small>
                        </label>
                    </fieldset>

                    {error && (
                        <p role="alert" className={styles.error}>
                            {error}
                        </p>
                    )}
                    <div className={styles.editorActions}>
                        <button type="button" disabled={busy} onClick={onClose}>
                            Отмена
                        </button>
                        {employee &&
                            employee.status === 'active' &&
                            form.availability === 'available' && (
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
                                    Показать новый код
                                </button>
                            )}
                        <button
                            className={styles.primaryButton}
                            type="submit"
                            disabled={busy || !form.first_name.trim()}
                        >
                            {busy ? 'Сохраняем…' : 'Сохранить'}
                        </button>
                    </div>
                </form>
            </section>
        </div>
    );
}
