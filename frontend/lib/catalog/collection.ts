export interface CollectionProduct {
    id: number;
    title: string;
    price: string;
    description: string | null;
    image_url: string | null;
    image_alt: string | null;
}

export type CollectionModelsState = {status:'ready'; items:CollectionProduct[]} | {status:'error'};
