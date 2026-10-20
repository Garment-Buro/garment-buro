'use client';

import { requestModelCategories, requestProductCategories } from '@/lib/production/categoryDirectory';
import { usePagedCatalog } from '@/hooks/catalog/usePagedCatalog';
import { PageCursorExpiredError } from '@/lib/catalog/pagedResource';
import {
    requestModelPage,
    requestFabricPage,
    requestRequirementPage,
    referenceSearch,
    type DirectoryQuery,
    type ReferenceChoice,
    type ReferenceKind,
    type ReferencePage,
} from '@/lib/production/referenceDirectory';
import {
    requestAccessoryPage,
    requestBoxPage,
    requestAccessoryCategoryPage,
    requestAccessoryRequirementPage,
    requestPackagingRulePage,
} from '@/lib/production/stockDirectory';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import {
    requestTechCardPage,
    requestTechCardModels,
} from '@/lib/production/techDirectory';
import {
    requestPatternModels,
    requestPatternFiles,
    requestPatternSizes,
} from '@/lib/production/patternDirectory';

type Loader<T> = (
    query: DirectoryQuery,
    signal: AbortSignal,
) => Promise<ReferencePage<T>>;
function productionRead<T>(read: Loader<T>): Loader<T> {
    return (query, signal) =>
        useProductionAuthStore
            .getState()
            .runAuthenticated(() => read(query, signal));
}
const models = productionRead(requestModelPage),
    fabrics = productionRead(requestFabricPage),
    requirements = productionRead(requestRequirementPage);
const accessories = productionRead(requestAccessoryPage),
    boxes = productionRead(requestBoxPage),
    categories = productionRead(requestAccessoryCategoryPage);
const accessoryRequirements = productionRead(requestAccessoryRequirementPage),
    packagingRules = productionRead(requestPackagingRulePage);
const techCards = productionRead(requestTechCardPage),
    techCardModels = productionRead(requestTechCardModels);
const patternModels = productionRead(requestPatternModels),
    patternFiles = productionRead(requestPatternFiles),
    patternSizes = productionRead(requestPatternSizes);
function useDirectory<T extends { id: number }>(
    kind: string,
    query: DirectoryQuery,
    load: Loader<T>,
    enabled = true,
) {
    const epoch = useProductionAuthStore((state) => state.sessionEpoch);
    const authenticated = useProductionAuthStore(
        (state) => state.isAuthenticated,
    );
    const active = enabled && authenticated && epoch !== null;
    const page = usePagedCatalog(
        query,
        `production-directory:${epoch}:${kind}:${referenceSearch(query)}`,
        load,
        active,
    );
    return {
        ...page,
        items: active ? page.items : [],
        loading: active && ['loading', 'idle'].includes(page.status),
        message:
            active && page.error instanceof Error ? page.error.message : '',
        hasMore:
            active &&
            page.nextCursor !== null &&
            !(page.error instanceof PageCursorExpiredError),
    };
}
export const useModelDirectory = (query: DirectoryQuery, enabled = true) =>
    useDirectory('models', query, models, enabled);
export const useFabricDirectory = (query: DirectoryQuery, enabled = true) =>
    useDirectory('fabrics', query, fabrics, enabled);
export const useFabricRequirements = (enabled = true) =>
    useDirectory('fabric-requirements', { limit: 24 }, requirements, enabled);
export const useAccessoryDirectory = (query: DirectoryQuery) =>
    useDirectory('accessories', query, accessories);
export const useBoxDirectory = (query: DirectoryQuery) =>
    useDirectory('boxes', query, boxes);
export const useAccessoryCategories = (query: DirectoryQuery) =>
    useDirectory('accessory-categories', query, categories);
export const useAccessoryRequirements = (query: DirectoryQuery) =>
    useDirectory('accessory-requirements', query, accessoryRequirements);
export const usePackagingRules = (query: DirectoryQuery) =>
    useDirectory('packaging-rules', query, packagingRules);
export const useTechCardDirectory = (query: DirectoryQuery) =>
    useDirectory('tech-cards', query, techCards);
export const usePatternModels = (query: DirectoryQuery) =>
    useDirectory('pattern-models', query, patternModels);
export const usePatternFiles = (query: DirectoryQuery, revision = 0) =>
    useDirectory(`patterns:${revision}`, query, patternFiles);
const modelCategories = productionRead(requestModelCategories), productCategories = productionRead(requestProductCategories);
export const useCategoryDirectory = (kind: 'model-categories' | 'product-categories', query: DirectoryQuery, enabled = true, revision = 0) => useDirectory(`${kind}:${revision}`, query, kind === 'model-categories' ? modelCategories : productCategories, enabled);
const choiceLoads: Record<ReferenceKind, Loader<ReferenceChoice>> = {
    models,
    fabrics,
    accessories,
    boxes,
    'accessory-categories': categories,
    'tech-card-models': techCardModels,
    'pattern-sizes': patternSizes,
    'model-categories': modelCategories,
    'product-categories': productCategories,
};
export const useReferenceChoices = (
    kind: ReferenceKind,
    query: DirectoryQuery,
) => useDirectory<ReferenceChoice>(`choices:${kind}`, query, choiceLoads[kind]);
