import type { CrmProjectStatus } from '@/lib/crm/types';

const PROJECT_STATUS_LABELS: Record<CrmProjectStatus, string> = {
    queued: 'В очереди',
    in_progress: 'В работе',
    on_hold: 'Приостановлен',
    completed: 'Завершён',
    cancelled: 'Отменён',
};

export const getCrmProjectStatusLabel = (status: CrmProjectStatus) => (
    PROJECT_STATUS_LABELS[status]
);

export const getCrmProjectStatusClassName = (status: CrmProjectStatus) => {
    if (status === 'in_progress') return 'bg-blue-100 text-blue-800';
    if (status === 'completed') return 'bg-green-100 text-green-800';
    if (status === 'on_hold') return 'bg-amber-100 text-amber-800';
    if (status === 'cancelled') return 'bg-red-100 text-red-800';
    return 'bg-gray-100 text-gray-800';
};

export const formatCrmDate = (value: string) => new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'short',
    timeStyle: 'short',
}).format(new Date(value));
