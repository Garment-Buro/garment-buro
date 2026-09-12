import { requestJson } from './http';
import type { Command, Employee, Project, Queue } from '@/lib/production/types';

const headers = (token: string): Record<string, string> =>
    token ? { Authorization: `Bearer ${token}` } : {};
export const productionApi = {
    resolveOrder: (token: string, id: number) =>
        requestJson<{ project_id: number }>(
            `/production/orders/${id}/project`,
            {
                headers: headers(token),
                cache: 'no-store',
            },
        ),
    me: (token: string, signal?: AbortSignal) =>
        requestJson<Employee>('/production/me', {
            headers: headers(token),
            cache: 'no-store',
            signal,
        }),
    queue: (token: string, cursor?: number, signal?: AbortSignal) =>
        requestJson<Queue>(
            `/production/projects${cursor ? `?cursor=${cursor}` : ''}`,
            { headers: headers(token), cache: 'no-store', signal },
        ),
    project: (token: string, id: number, signal?: AbortSignal, station?: string) =>
        requestJson<Project>(`/production/projects/${id}${station ? `?station=${station}` : ''}`, {
            headers: headers(token),
            cache: 'no-store',
            signal,
        }),
    command: (
        token: string,
        id: number,
        version: number,
        key: string,
        command: Command,
        station?: string,
    ) =>
        requestJson<{ version: number }>(
            `/production/projects/${id}/commands${station ? `?station=${station}` : ''}`,
            {
                method: 'POST',
                headers: {
                    ...headers(token),
                    'Content-Type': 'application/json',
                    'Idempotency-Key': key,
                },
                body: JSON.stringify({ ...command, expected_version: version }),
            },
        ),
    upload: (token: string, id: number, slot: number, file: File) => {
        const body = new FormData();
        body.append('file', file);
        return requestJson<{
            attachment_id: number;
            checksum_sha256: string;
            size_bytes: number;
            content_type: string;
        }>(`/production/units/${id}/files?slot=${slot}`, {
            method: 'POST',
            headers: headers(token),
            body,
        });
    },
    download: (token: string, id: number, station?: string) =>
        requestJson<{ url: string; filename: string }>(
            `/production/files/${id}/download${station ? `?station=${station}` : ''}`,
            { headers: headers(token), cache: 'no-store' },
        ),
};
