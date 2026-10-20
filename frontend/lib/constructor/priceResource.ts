import type { PlacedItemsByView } from "./types.ts";

export type ConstructorPriceRequest = { productId: number; decorations: { uid: string; scale: number }[] };
export type ConstructorPriceQuote = {
    productId: number;
    policyRevision: string;
    decorationBasePrice: number;
    basePrice: number;
    customizationPrice: number;
    totalPrice: number;
    decorations: { uid: string; price: number }[];
};
type Snapshot = {
    key: string | null;
    quote: ConstructorPriceQuote | null;
    status: "idle" | "loading" | "ready" | "error";
    error: unknown;
};
type Transport = (input: ConstructorPriceRequest, signal: AbortSignal) => Promise<unknown>;

export function constructorPriceRequest(
    productId: number | null,
    views: PlacedItemsByView,
): ConstructorPriceRequest | null {
    if (productId === null) return null;
    return { productId, decorations: [...views.front, ...views.back].map(({ uid, scale }) => ({ uid, scale })) };
}
export const priceRequestKey = (input: ConstructorPriceRequest | null) =>
    input === null ? null : JSON.stringify(input);
export const currentPriceQuote = (snapshot: Snapshot, input: ConstructorPriceRequest | null) =>
    snapshot.key === priceRequestKey(input) && snapshot.status === "ready" ? snapshot.quote : null;

function money(value: unknown): number {
    if (typeof value !== "number" && (typeof value !== "string" || !/^\d+(\.\d{1,2})?$/.test(value)))
        throw new Error("Некорректная цена.");
    const price = Number(value);
    if (
        !Number.isFinite(price) ||
        price < 0 ||
        price > 9_999_999_999.99 ||
        Math.abs(price * 100 - Math.round(price * 100)) > 0.001
    )
        throw new Error("Некорректная цена.");
    return price;
}
function readQuote(value: unknown, input: ConstructorPriceRequest): ConstructorPriceQuote {
    if (!value || typeof value !== "object") throw new Error("Не удалось проверить стоимость.");
    const data = value as Record<string, unknown>;
    if (
        data.product_id !== input.productId ||
        typeof data.policy_revision !== "string" ||
        !data.policy_revision ||
        !Array.isArray(data.decorations)
    )
        throw new Error("Ответ стоимости относится к другой модели.");
    const basePrice = money(data.base_price),
        customizationPrice = money(data.customization_price),
        totalPrice = money(data.total_price);
    const expected = new Set(input.decorations.map((d) => d.uid));
    const seen = new Set<string>();
    const decorations = data.decorations.map((d: unknown) => {
        if (
            !d ||
            typeof d !== "object" ||
            !("uid" in d) ||
            typeof d.uid !== "string" ||
            !expected.has(d.uid) ||
            seen.has(d.uid) ||
            !("price" in d)
        )
            throw new Error("Неполный расчёт украшений.");
        seen.add(d.uid);
        return { uid: d.uid, price: money(d.price) };
    });
    if (
        seen.size !== expected.size ||
        decorations.reduce((sum, d) => sum + Math.round(d.price * 100), 0) !== Math.round(customizationPrice * 100) ||
        Math.round(basePrice * 100) + Math.round(customizationPrice * 100) !== Math.round(totalPrice * 100)
    )
        throw new Error("Сумма расчёта не совпадает.");
    return {
        productId: input.productId,
        policyRevision: data.policy_revision,
        decorationBasePrice: money(data.decoration_base_price),
        basePrice,
        customizationPrice,
        totalPrice,
        decorations,
    };
}

function debounce(milliseconds: number, signal: AbortSignal): Promise<void> {
    return new Promise((resolve, reject) => {
        const cancel = () => {
            clearTimeout(timer);
            reject(signal.reason);
        };
        const timer = setTimeout(() => {
            signal.removeEventListener("abort", cancel);
            resolve();
        }, milliseconds);
        signal.addEventListener("abort", cancel, { once: true });
    });
}

/** Only the exact current placement request can supply a purchasable preview. */
export class ConstructorPriceResource {
    private snapshot: Snapshot = { key: null, quote: null, status: "idle", error: null };
    private controller: AbortController | null = null;
    private listeners = new Set<() => void>();
    getSnapshot = () => this.snapshot;
    subscribe = (listener: () => void) => {
        this.listeners.add(listener);
        return () => {
            this.listeners.delete(listener);
        };
    };
    private publish(snapshot: Snapshot) {
        this.snapshot = snapshot;
        this.listeners.forEach((listener) => listener());
    }
    async load(input: ConstructorPriceRequest | null, transport: Transport, delay = 250) {
        this.dispose();
        const key = priceRequestKey(input);
        if (!input) {
            this.publish({ key, quote: null, status: "idle", error: null });
            return;
        }
        const controller = new AbortController();
        this.controller = controller;
        this.publish({ key, quote: null, status: "loading", error: null });
        try {
            if (delay > 0) await debounce(delay, controller.signal);
            controller.signal.throwIfAborted();
            const value = await transport(input, controller.signal);
            if (controller.signal.aborted) return;
            this.publish({ key, quote: readQuote(value, input), status: "ready", error: null });
        } catch (error) {
            if (!controller.signal.aborted) this.publish({ key, quote: null, status: "error", error });
        }
    }
    dispose() {
        this.controller?.abort();
        this.controller = null;
    }
}
