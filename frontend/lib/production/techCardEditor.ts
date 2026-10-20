import type { TechCheckpoint } from './assortmentTypes.ts';
import type { TechCardEditorSource } from './techDirectory.ts';
import { compactDecimal } from './numbers.ts';

export type TechCardForm = {
    cardId?: number;
    modelId: number;
    modelName: string;
    code: string;
    expectedLatestRevision?: number;
    name: string;
    description: string;
    checkpoints: TechCheckpoint[];
};
export const newTechCheckpoint = (position: number): TechCheckpoint => ({
    position,
    stage_code: 'tech',
    role_code: 'tech',
    name: '',
    description: null,
    standard_minutes: null,
    labor_cost: '0',
    currency: 'RUB',
});
export const techCardForm = (row?: TechCardEditorSource): TechCardForm => ({
    cardId: row?.id,
    modelId: row?.garment_model_id ?? 0,
    modelName: row?.garment_model_name ?? '',
    code: row?.code ?? '',
    expectedLatestRevision: row?.latest_revision_number,
    name: row?.source?.name_snapshot ?? '',
    description: row?.source?.description_snapshot ?? '',
    checkpoints: row?.source
        ? [...row.source.checkpoints]
              .sort((a, b) => a.position - b.position)
              .map((step, index) => ({
                  ...step,
                  position: index + 1,
                  standard_minutes:
                      step.standard_minutes === null
                          ? null
                          : compactDecimal(step.standard_minutes),
                  labor_cost: compactDecimal(step.labor_cost),
              }))
        : [newTechCheckpoint(1)],
});
/** Preserve stored stage/role codes; combining employee stations is a separate concern. */
export const techCardWrite = (editor: TechCardForm) => {
    const revision = {
        name: editor.name,
        description: editor.description || null,
        checkpoints: editor.checkpoints.map((step, index) => ({
            position: index + 1,
            stage_code: step.stage_code,
            role_code: step.role_code,
            name: step.name,
            description: step.description || null,
            standard_minutes: step.standard_minutes
                ? Number(step.standard_minutes)
                : null,
            labor_cost: Number(step.labor_cost || 0),
            currency: 'RUB',
        })),
    };
    return editor.cardId
        ? {
              path: `tech-cards/${editor.cardId}/revisions`,
              payload: {
                  expected_latest_revision: editor.expectedLatestRevision,
                  revision,
              },
          }
        : {
              path: `models/${editor.modelId}/tech-cards`,
              payload: { code: editor.code, revision },
          };
};
