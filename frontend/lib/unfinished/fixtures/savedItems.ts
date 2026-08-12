import type { SavedProfileItem } from '@/lib/unfinished/utils/savedItems';

export const DRAFT_PREVIEW_FIXTURES: SavedProfileItem[] = [
    { id: 'draft-001', kind: 'draft', number: '001', name: 'hat: love & murder', imageSrc: '/mock/hoodie.webp', productId: 1, savedAt: 0 },
    { id: 'draft-002', kind: 'draft', number: '002', name: 'hat: love & murder', imageSrc: '/mock/jacket.webp', productId: 2, savedAt: 0 },
    { id: 'draft-003', kind: 'draft', number: '001', name: 'hat: love & murder', imageSrc: '/mock/tshirt.webp', productId: 3, savedAt: 0 },
    { id: 'draft-004', kind: 'draft', number: '002', name: 'hat: love & murder', imageSrc: '/mock/patch.webp', productId: 4, savedAt: 0 },
    { id: 'draft-005', kind: 'draft', number: '001', name: 'hat: love & murder', imageSrc: '/mock/sticker.webp', productId: 1, savedAt: 0 },
    { id: 'draft-006', kind: 'draft', number: '002', name: 'hat: love & murder', imageSrc: '/mock/rivet.webp', productId: 2, savedAt: 0 },
    { id: 'draft-007', kind: 'draft', number: '001', name: 'hat: love & murder', imageSrc: '/mock/button.webp', productId: 3, savedAt: 0 },
    { id: 'draft-008', kind: 'draft', number: '002', name: 'hat: love & murder', imageSrc: '/mock/hoodie.webp', productId: 4, savedAt: 0 },
];

export const COLLECTION_PREVIEW_FIXTURES: SavedProfileItem[] = [
    { id: 'collection-001', kind: 'collection', number: '001', name: 'Night Slim', imageSrc: '/mock/hoodie.webp', productId: 1, savedAt: 0 },
    { id: 'collection-002', kind: 'collection', number: '002', name: 'Cold Oversize', imageSrc: '/mock/jacket.webp', productId: 2, savedAt: 0 },
    { id: 'collection-003', kind: 'collection', number: '003', name: 'Love & Murder', imageSrc: '/mock/tshirt.webp', productId: 3, savedAt: 0 },
    { id: 'collection-004', kind: 'collection', number: '004', name: 'Garment Buro Edition', imageSrc: '/my_collection_template.webp', productId: 4, savedAt: 0 },
];
