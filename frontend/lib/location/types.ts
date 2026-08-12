export type Coordinates = [number, number];

export type AddressSuggestion = {
    displayName?: string;
    value?: string;
    coords?: Coordinates;
};
