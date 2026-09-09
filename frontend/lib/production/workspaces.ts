import type { Project, Station } from './types';

export function thingsCount(count: number) {
    const form = new Intl.PluralRules('ru').select(count);
    return `${count} ${form === 'one' ? 'вещь' : form === 'few' ? 'вещи' : 'вещей'}`;
}

export const stationRoles: Record<Station, string> = {
    tech: 'Технолог',
    kit: 'Комплектовщик',
    cut: 'Закройщик',
    dtf: 'DTF-печатник',
    application: 'Нанесение',
    sewing: 'Швея',
    press: 'ВТО',
    qc: 'ОТК',
    packing: 'Упаковщик',
    shipping: 'Отправка',
};
export const stationGuides: Record<Station, { task: string; result: string }> =
    {
        tech: {
            task: 'Проверить заказ, закрепить техкарту и оригиналы. Выпустить QR мешка и листы вещей.',
            result: 'Все вещи одобрены, лекала и QR подготовлены. Мешок передан на комплектовку.',
        },
        kit: {
            task: 'Вложить ткань и комплектующие каждой вещи. Отдельно подтвердить вложение готовой DTF-печати.',
            result: 'Комплектный мешок передан в цех. Ожидание DTF — отдельный карман, а не этап.',
        },
        cut: {
            task: 'Открыть мешок по QR, раскроить вещи по закреплённым лекалам и завернуть крой в лист с QR.',
            result: 'Пачка кроя передана на следующий участок своего маршрута.',
        },
        dtf: {
            task: 'Скачать оригиналы, напечатать и нарезать плёнку. Подписать пакет QR мешка.',
            result: 'Печать готова к забору. Вложение подтверждает комплектовщик, не печатник.',
        },
        application: {
            task: 'Проверить вложение DTF и нанести печать на крой по техкарте.',
            result: 'Нанесение завершено, вещь можно передать в пошив.',
        },
        sewing: {
            task: 'Сшить вещь по закреплённой техкарте и вернуть её в тот же мешок.',
            result: 'Вещь передана на ВТО или следующий участок её маршрута.',
        },
        press: {
            task: 'Выполнить влажно-тепловую обработку изделия.',
            result: 'Изделие подготовлено к проверке качества.',
        },
        qc: {
            task: 'Выполнить все проверки ОТК. При дефекте описать проблему и назначить переделку.',
            result: 'Качество подтверждено либо вещь возвращена на нужный участок.',
        },
        packing: {
            task: 'Упаковать каждую вещь, сверить полный состав мешка.',
            result: 'Все вещи готовы, весь заказ упакован.',
        },
        shipping: {
            task: 'Сверить получателя, доставку и трек-номер. Подтвердить физическую передачу перевозчику.',
            result: 'Передача записана в журнале. Доставка отслеживается отдельно.',
        },
    };

export function bagCanMove(project: Project): boolean {
    if (
        !project.units.length ||
        project.units.some(
            (u) => !u.specification || u.issue || u.blockers.length,
        )
    )
        return false;
    if (project.state === 'kitting')
        return project.units.every((u) =>
            u.specification!.components.every((c) => u.checks[c.key]),
        );
    if (project.state === 'waiting_dtf')
        return project.units.every(
            (u) =>
                !u.specification!.route.includes('application') ||
                u.dtf_inserted,
        );
    return false;
}

/** Never fall back to the first order for invalid scanner input. */
export function parseBagReference(
    value: string,
    origin: string,
): { kind: 'project' | 'order'; id: number; unit?: number } | null {
    const number = value.trim().replace(/^#/, '');
    if (/^[1-9]\d*$/.test(number) && Number.isSafeInteger(Number(number)))
        return { kind: 'order', id: Number(number) };
    try {
        const url = new URL(value.trim(), origin);
        if (
            url.origin !== origin ||
            !['/production', '/production/floor'].includes(url.pathname)
        )
            return null;
        const id = Number(url.searchParams.get('project'));
        const unit = Number(url.searchParams.get('unit'));
        if (!Number.isSafeInteger(id) || id <= 0) return null;
        return {
            kind: 'project',
            id,
            ...(Number.isSafeInteger(unit) && unit > 0 ? { unit } : {}),
        };
    } catch {
        return null;
    }
}
