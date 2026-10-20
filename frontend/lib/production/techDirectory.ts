import { requestReadJson } from '../api/http.ts';
import {
    isReferenceChoice,
    isReferenceCount,
    isReferenceDecimal,
    isReferenceId,
    readReferencePage,
    requestDirectoryPage,
    type DirectoryQuery,
    type ReferenceChoice,
} from './referenceDirectory.ts';
import type { TechCheckpoint } from './assortmentTypes.ts';

type RevisionStatus = 'draft' | 'published' | 'archived' | 'discarded';
export type TechCardSummary = {
    id: number;
    garment_model_id: number;
    garment_model_name: string;
    code: string;
    is_active: boolean;
    latest_revision_number: number;
    latest_revision_status: RevisionStatus | null;
    latest_revision_name: string | null;
    checkpoint_count: number;
    draft_revision_number: number | null;
};
export type TechCardEditorSource = {
    id: number;
    garment_model_id: number;
    garment_model_name: string;
    code: string;
    latest_revision_number: number;
    draft_revision_number: number | null;
    source: {
        id: number;
        revision_number: number;
        name_snapshot: string;
        description_snapshot: string | null;
        checkpoints: TechCheckpoint[];
    } | null;
};
const nullableText = (value: unknown) =>
    value === null || typeof value === 'string';
const optionalId = (value: unknown) => value === null || isReferenceId(value);
const status = (value: unknown) =>
    value === null ||
    ['draft', 'published', 'archived', 'discarded'].includes(String(value));
export const readTechCardPage = (value: unknown) =>
    readReferencePage<TechCardSummary>(
        value,
        (row) =>
            isReferenceId(row.garment_model_id) &&
            typeof row.garment_model_name === 'string' &&
            typeof row.code === 'string' &&
            typeof row.is_active === 'boolean' &&
            isReferenceId(row.latest_revision_number) &&
            status(row.latest_revision_status) &&
            nullableText(row.latest_revision_name) &&
            isReferenceCount(row.checkpoint_count) &&
            optionalId(row.draft_revision_number) &&
            (row.draft_revision_number === null ||
                row.draft_revision_number <= row.latest_revision_number),
    );
export function readTechCardSource(
    value: unknown,
    id: number,
): TechCardEditorSource {
    const row = value as TechCardEditorSource | null;
    if (
        !row ||
        !isReferenceId(row.id) ||
        row.id !== id ||
        !isReferenceId(row.garment_model_id) ||
        typeof row.garment_model_name !== 'string' ||
        typeof row.code !== 'string' ||
        !isReferenceId(row.latest_revision_number) ||
        !optionalId(row.draft_revision_number) ||
        (row.draft_revision_number !== null &&
            row.draft_revision_number > row.latest_revision_number)
    )
        throw new Error('Сервер вернул неверную техкарту.');
    const source = row.source;
    if (source !== null) {
        if (
            !source ||
            !isReferenceId(source.id) ||
            !isReferenceId(source.revision_number) ||
            source.revision_number > row.latest_revision_number ||
            typeof source.name_snapshot !== 'string' ||
            !nullableText(source.description_snapshot) ||
            !Array.isArray(source.checkpoints) ||
            source.checkpoints.length < 1 ||
            source.checkpoints.length > 200
        )
            throw new Error('Не удалось прочитать исходную версию техкарты.');
        const positions = new Set<number>();
        for (const step of source.checkpoints) {
            if (
                !step ||
                !isReferenceId(step.id) ||
                !isReferenceId(step.position) ||
                positions.has(step.position) ||
                typeof step.stage_code !== 'string' ||
                !step.stage_code ||
                typeof step.role_code !== 'string' ||
                !step.role_code ||
                typeof step.name !== 'string' ||
                !nullableText(step.description) ||
                step.currency !== 'RUB' ||
                !isReferenceDecimal(step.labor_cost) ||
                Number(step.labor_cost) < 0 ||
                !(
                    step.standard_minutes === null ||
                    (isReferenceDecimal(step.standard_minutes) &&
                        Number(step.standard_minutes) > 0)
                )
            )
                throw new Error('Сервер вернул неполную операцию техкарты.');
            positions.add(step.position);
        }
    }
    return row;
}
export const requestTechCardPage = (
    query: DirectoryQuery,
    signal: AbortSignal,
) => requestDirectoryPage('tech-cards', query, readTechCardPage, signal);
export const requestTechCardModels = (
    query: DirectoryQuery,
    signal: AbortSignal,
) =>
    requestDirectoryPage(
        'tech-card-models',
        query,
        (value) => readReferencePage<ReferenceChoice>(value, isReferenceChoice),
        signal,
    );
export const requestTechCardSource = async (id: number, signal: AbortSignal) =>
    readTechCardSource(
        await requestReadJson<unknown>(
            `/production/admin/assortment/tech-cards/${id}/revision-source`,
            { signal, cache: 'no-store' },
        ),
        id,
    );
