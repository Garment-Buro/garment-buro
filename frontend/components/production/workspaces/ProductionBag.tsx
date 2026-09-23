/* eslint-disable @next/next/no-img-element -- order snapshots and generated QR */
'use client';
import { useState } from 'react';
import {
    PiCaretDown,
    PiChatCircleDots,
    PiPackage,
    PiPrinter,
} from 'react-icons/pi';
import {
    labels,
    stateLabels,
    type Employee,
    type Project,
    type SendCommand,
    type Station,
} from '@/lib/production/types';
import {
    canAct,
    currentStage,
    orderBlocked,
    safeImage,
} from '@/lib/production/workflow';
import { BagActions } from '../BagActions';
import { ProductionUnit } from '../ProductionUnit';
import { ProductionViews } from './ProductionViews';
import { ProductionJournal } from './ProductionJournal';
import { ProductionTechCard } from './ProductionTechCard';
import { thingsCount } from '@/lib/production/workspaces';
import styles from './ProductionFlow.module.css';

export function ProductionBag({
    project,
    employee,
    station,
    busy,
    send,
    print,
    printing,
    requestedUnit,
}: {
    project: Project;
    employee: Employee;
    station: Station;
    busy: boolean;
    send: SendCommand;
    print: () => void;
    printing: boolean;
    requestedUnit?: number | null;
}) {
    const [opened, setOpened] = useState<number | null>(
        requestedUnit ??
            (project.units.length === 1 ? project.units[0]?.id : null),
    );
    const blocked = orderBlocked(project);
    const wide =
        station === 'tech' || station === 'dtf' || station === 'packing';
    const localStations = canAct(employee.stations, station) ? [station] : [];
    const qr = `/api/qr-code?surface=production&size=256&path=${encodeURIComponent(project.public_token ? `/production/label?token=${project.public_token}` : `/production?project=${project.project_id}`)}`;
    const orderComments = project.units.flatMap((unit) => {
        const raw = unit.source.customization?.comment;
        const comment = typeof raw === 'string' ? raw.trim() : '';
        return comment
            ? [{ unitId: unit.id, title: unit.source.title, comment }]
            : [];
    });
    return (
        <div className={styles.bagBody}>
            <div className={styles.bagSummary}>
                <div>
                    <h2>Мешок {project.customer}</h2>
                    <div
                        className={styles.bagComment}
                        data-empty={!orderComments.length}
                    >
                        <PiChatCircleDots aria-hidden />
                        <div>
                            <strong>Комментарий к заказу</strong>
                            {orderComments.length ? (
                                orderComments.map((item) => (
                                    <p key={item.unitId}>
                                        {project.units_count > 1 && (
                                            <b>{item.title}: </b>
                                        )}
                                        {item.comment}
                                    </p>
                                ))
                            ) : (
                                <p>Комментарий не оставлен</p>
                            )}
                        </div>
                    </div>
                    {project.is_demo && (
                        <p>Тестовый заказ. Не производить и не отправлять.</p>
                    )}
                    <p>
                        Заказ №{project.order_id} ·{' '}
                        {thingsCount(project.units_count)}
                    </p>
                    <div className={styles.meta}>
                        <span>
                            Статус
                            <strong>
                                {
                                    stateLabels[
                                        project.display_state || project.state
                                    ]
                                }
                            </strong>
                        </span>
                    </div>
                    {(station === 'dtf' || station === 'cut') &&
                        canAct(employee.stations, station) && (
                            <button
                                disabled={
                                    busy ||
                                    printing ||
                                    !project.units.every(
                                        (u) => u.specification,
                                    ) ||
                                    (project.flow_version === 2 &&
                                        (station === 'cut'
                                            ? !project.units.some(
                                                  (u) => u.public_token,
                                              )
                                            : !project.units.some(
                                                  (unit) =>
                                                      unit.dtf_ready &&
                                                      unit.public_token,
                                              )))
                                }
                                onClick={print}
                            >
                                <PiPrinter />
                                {printing
                                    ? 'Готовим…'
                                    : 'Печать QR мешков изделий'}
                            </button>
                        )}
                </div>
                {wide &&
                    station !== 'tech' &&
                    (project.flow_version !== 2 || project.public_token) && (
                        <div className={styles.qr}>
                            <img
                                src={qr}
                                alt={`QR мешка заказа ${project.order_id}`}
                                width={112}
                                height={112}
                            />
                            <strong>QR заказа</strong>
                            <small>Мешок №{project.order_id}</small>
                        </div>
                    )}
            </div>
            {blocked && (
                <p className={styles.error} role="alert">
                    Заказ заблокирован для работы. Проверьте оплату и статус
                    заказа у технолога.
                </p>
            )}
            {!canAct(employee.stations, station) && (
                <p className={styles.callout}>
                    Просмотр участка. Изменения доступны сотрудникам этого
                    участка.
                </p>
            )}
            {station === 'tech' && (
                <BagActions
                    key={`${project.project_id}-${station}`}
                    project={project}
                    stations={localStations}
                    send={send}
                    busy={busy || blocked}
                    print={print}
                    printing={printing}
                />
            )}
            {project.units.map((unit) => {
                const stage = currentStage(unit);
                const image = safeImage(unit.source.image);
                const isOpen = opened === unit.id;
                return (
                    <section
                        className={styles.item}
                        key={unit.id}
                        data-problem={!!unit.issue}
                    >
                        <button
                            className={styles.itemToggle}
                            onClick={() => setOpened(isOpen ? null : unit.id)}
                            aria-expanded={isOpen}
                            data-open={isOpen}
                        >
                            <span className={styles.thumb}>
                                {image ? (
                                    <img src={image} alt="" />
                                ) : (
                                    <PiPackage aria-hidden />
                                )}
                                <b>
                                    {unit.number}/{project.units_count}
                                </b>
                            </span>
                            <span>
                                <strong>
                                    {unit.source.title} · {unit.source.size}
                                </strong>
                                <small>
                                    {unit.source.color}
                                    {unit.source.sku
                                        ? ` · ${unit.source.sku}`
                                        : ''}
                                </small>
                                <em
                                    className={styles.pill}
                                    data-tone={
                                        unit.issue
                                            ? 'bad'
                                            : !stage && unit.specification
                                              ? 'good'
                                              : 'work'
                                    }
                                >
                                    {unit.issue
                                        ? 'Проблема'
                                        : stage
                                          ? unit.lane
                                              ? stateLabels[unit.lane]
                                              : labels[stage]
                                          : unit.specification
                                            ? 'Готово'
                                            : 'Нужна техкарта'}
                                </em>
                            </span>
                            <PiCaretDown aria-hidden />
                        </button>
                        {isOpen && (
                            <div className={styles.itemBody} data-wide={wide}>
                                {wide ? (
                                    <>
                                        <ProductionUnit
                                            key={`${unit.id}-${project.version}-${station}`}
                                            unit={unit}
                                            project={project}
                                            station={station}
                                            stations={localStations}
                                            send={send}
                                            busy={busy || blocked}
                                        />
                                        <ProductionViews
                                            unit={unit}
                                            compact={
                                                station === 'tech' ||
                                                station === 'dtf'
                                            }
                                            station={station}
                                        />
                                    </>
                                ) : (
                                    <>
                                        <ProductionTechCard unit={unit} />
                                        <ProductionUnit
                                            key={`${unit.id}-${project.version}-${station}`}
                                            unit={unit}
                                            project={project}
                                            station={station}
                                            stations={localStations}
                                            send={send}
                                            busy={busy || blocked}
                                        />
                                    </>
                                )}
                            </div>
                        )}
                    </section>
                );
            })}
            {['dtf', 'kit', 'packing', 'shipping'].includes(station) && (
                <BagActions
                    key={`${project.project_id}-${station}`}
                    project={project}
                    stations={localStations}
                    send={send}
                    busy={busy || blocked}
                    print={print}
                    printing={printing}
                />
            )}
            {['tech', 'kit', 'packing'].includes(station) && (
                <ProductionJournal project={project} />
            )}
        </div>
    );
}
