import type {
    Accessory,
    AccessoryCategory,
    AccessoryRequirement,
    PackagingBox,
    PackagingRule,
} from './assortmentTypes.ts';
import {
    isReferenceChoice,
    isReferenceCount,
    isReferenceDecimal,
    isReferenceId,
    readReferencePage,
    requestDirectoryPage,
    type DirectoryQuery,
} from './referenceDirectory.ts';

export type AccessoryCard = Accessory & {
    category_name: string;
    model_count: number;
};
export type AccessoryRequirementCard = AccessoryRequirement & {
    garment_model_name: string;
    accessory_name: string;
};
export type PackagingRuleCard = PackagingRule & {
    garment_model_name: string;
    box_name: string;
    box_capacity: number;
};
const optionalId = (value: unknown) => value === null || isReferenceId(value);
const optionalText = (value: unknown) =>
    value === null || typeof value === 'string';
const money = (value: unknown) =>
    isReferenceDecimal(value) && Number(value) >= 0;
const stock = (row: Accessory | PackagingBox) =>
    isReferenceChoice(row) &&
    isReferenceId(row.version) &&
    money(row.unit_cost) &&
    row.currency === 'RUB' &&
    isReferenceCount(row.stock_quantity) &&
    isReferenceCount(row.minimum_stock_quantity) &&
    optionalId(row.photo_media_object_id);
export const readAccessoryPage = (value: unknown) =>
    readReferencePage<AccessoryCard>(
        value,
        (row) =>
            stock(row) &&
            isReferenceId(row.category_id) &&
            typeof row.category_name === 'string' &&
            isReferenceCount(row.model_count),
    );
export const readBoxPage = (value: unknown) =>
    readReferencePage<PackagingBox>(
        value,
        (row) =>
            stock(row) &&
            isReferenceId(row.max_items) &&
            [
                row.inner_length_cm,
                row.inner_width_cm,
                row.inner_height_cm,
            ].every((value) => isReferenceDecimal(value) && Number(value) > 0),
    );
export const readAccessoryCategoryPage = (value: unknown) =>
    readReferencePage<AccessoryCategory>(
        value,
        (row) =>
            isReferenceChoice(row) &&
            isReferenceId(row.version) &&
            optionalText(row.description),
    );
export const readAccessoryRequirementPage = (value: unknown) =>
    readReferencePage<AccessoryRequirementCard>(
        value,
        (row) =>
            isReferenceId(row.version) &&
            isReferenceId(row.garment_model_id) &&
            isReferenceId(row.accessory_id) &&
            isReferenceDecimal(row.quantity_per_unit) &&
            Number(row.quantity_per_unit) > 0 &&
            typeof row.is_optional === 'boolean' &&
            optionalText(row.notes) &&
            typeof row.garment_model_name === 'string' &&
            typeof row.accessory_name === 'string',
    );
export const readPackagingRulePage = (value: unknown) =>
    readReferencePage<PackagingRuleCard>(
        value,
        (row) =>
            isReferenceId(row.version) &&
            isReferenceId(row.garment_model_id) &&
            isReferenceId(row.box_id) &&
            isReferenceId(row.max_items) &&
            isReferenceCount(row.priority) &&
            typeof row.garment_model_name === 'string' &&
            typeof row.box_name === 'string' &&
            isReferenceId(row.box_capacity),
    );
export const requestAccessoryPage = (
    query: DirectoryQuery,
    signal: AbortSignal,
) => requestDirectoryPage('accessories', query, readAccessoryPage, signal);
export const requestBoxPage = (query: DirectoryQuery, signal: AbortSignal) =>
    requestDirectoryPage('boxes', query, readBoxPage, signal);
export const requestAccessoryCategoryPage = (
    query: DirectoryQuery,
    signal: AbortSignal,
) =>
    requestDirectoryPage(
        'accessory-categories',
        query,
        readAccessoryCategoryPage,
        signal,
    );
export const requestAccessoryRequirementPage = (
    query: DirectoryQuery,
    signal: AbortSignal,
) =>
    requestDirectoryPage(
        'accessory-requirements',
        query,
        readAccessoryRequirementPage,
        signal,
    );
export const requestPackagingRulePage = (
    query: DirectoryQuery,
    signal: AbortSignal,
) =>
    requestDirectoryPage(
        'packaging-rules',
        query,
        readPackagingRulePage,
        signal,
    );
