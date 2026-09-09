import type { Project, Station, Unit } from './types';
export const currentStage = (unit: Unit) =>
    unit.specification?.route[unit.stage_index] ?? null;
export const canAct = (stations: Station[], station: Station) =>
    stations.includes('tech') || stations.includes(station);
export const orderBlocked = (project: Project) =>
    (!project.is_demo && project.payment_status !== 'paid') ||
    project.order_status !== 'processing' ||
    ['cancelled', 'on_hold'].includes(project.project_status);
export const matchesStation = (unit: Unit, station: Station) =>
    station === 'tech' ||
    station === 'kit' ||
    station === 'shipping' ||
    (station === 'dtf'
        ? Boolean(unit.specification?.print_file_ids.length)
        : currentStage(unit) === station);
export function safeImage(value: unknown): string | null {
    if (typeof value !== 'string' || !value) return null;
    if (value.startsWith('/') && !value.startsWith('//')) return value;
    try {
        const url = new URL(value);
        return url.protocol === 'https:' ? url.href : null;
    } catch {
        return null;
    }
}
