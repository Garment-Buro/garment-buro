export type CrmProjectStatus = (
    'queued'
    | 'in_progress'
    | 'on_hold'
    | 'completed'
    | 'cancelled'
);

export interface CrmProjectSummary {
    id: number;
    order_id: number;
    status: CrmProjectStatus;
    version: number;
    items_count: number;
    units_count: number;
    assigned_to_user_id: number | null;
    paid_at: string;
    started_at: string | null;
    closed_at: string | null;
    created_at: string;
    updated_at: string;
}

export interface CrmProjectPage {
    items: CrmProjectSummary[];
    next_cursor: number | null;
    limit: number;
}

export interface CrmProjectQuery {
    status?: CrmProjectStatus;
    assignedToUserId?: number;
    cursor?: number;
    limit?: number;
}
