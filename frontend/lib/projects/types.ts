import type {
    ConstructorCustomization,
    ConstructorDecoration,
    ConstructorDraftState,
    GarmentFit,
} from '../constructor/types.ts';

export type ProjectKind = 'draft' | 'collection';
export type ImageReference = { mediaId: number };
export type ProjectSnapshot = Omit<ConstructorDraftState, 'customization'> & {
    schemaVersion: 1;
    customization: Omit<
        ConstructorCustomization,
        'modelImages' | 'decorations' | 'fit' | 'comment' | 'geometry'
    > & {
        fit?: GarmentFit | null;
        comment?: string | null;
        modelImages: { front: ImageReference; back: ImageReference };
        decorations: Array<
            Omit<
                ConstructorDecoration,
                'image' | 'text' | 'categoryId' | 'originalWidth' | 'originalHeight'
            > & {
                image: ImageReference;
                text?: ConstructorDecoration['text'] | null;
                categoryId?: ConstructorDecoration['categoryId'] | null;
                originalWidth?: number | null;
                originalHeight?: number | null;
            }
        >;
    };
};
export interface ProjectWrite {
    kind: ProjectKind;
    title: string;
    snapshot: ProjectSnapshot;
}
export interface ProjectCreate extends ProjectWrite {
    client_key: string;
    product_id: number;
}
export interface ProjectUpdate extends ProjectWrite {
    expected_version: number;
}
export interface ProjectSummary {
    id: number;
    product_id: number | null;
    kind: ProjectKind;
    title: string;
    version: number;
    created_at: string;
    updated_at: string;
}
export interface ProjectDetail extends ProjectSummary {
    snapshot: ProjectSnapshot;
}
export interface ProjectPage {
    items: ProjectSummary[];
    next_cursor: number | null;
}
export interface ProjectImage {
    id: number;
    content_type: string;
    size_bytes: number;
}
export interface ResolvedProjectImage extends ProjectImage {
    url: string;
    expires_in: number | null;
}
export interface ProjectImages {
    version: number;
    items: ResolvedProjectImage[];
}
