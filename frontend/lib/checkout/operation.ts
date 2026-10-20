import { ApiError } from '../api/http.ts';
import { createCheckoutOrder, retryCheckoutPayment } from '../api/checkout.ts';
import type { CheckoutActor, CheckoutOrderPayload, CheckoutOrderResponse, CheckoutRequestContext } from './types.ts';

export type PurchaseIdentity = { owner: string; generation: string; actor: CheckoutActor };
export type PendingPurchase = {
    version: 1;
    owner: string;
    idempotencyKey: string;
    guestToken: string | null;
    payload: CheckoutOrderPayload;
    status: 'pending' | 'rejected' | 'review' | 'complete';
    orderId?: number;
    paymentKey?: string;
    result?: CheckoutOrderResponse;
};
type PurchaseStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;
type Dependencies = {
    storage: PurchaseStorage;
    getIdentity: () => PurchaseIdentity | null;
    createOrder?: typeof createCheckoutOrder;
    retryPayment?: typeof retryCheckoutPayment;
};

const prefix = 'garment-checkout-operation-v1:';
const maxBytes = 512 * 1024;
const positiveId = (id: unknown): id is number => Number.isSafeInteger(id) && (id as number) > 0;
const canonical = (value: unknown): string => JSON.stringify(value, (_, part) => part && typeof part === 'object' && !Array.isArray(part)
    ? Object.fromEntries(Object.keys(part).sort().map(key => [key, part[key]])) : part);
const semanticPayload = (payload: CheckoutOrderPayload) => canonical({ ...payload, delivery_quote_token: undefined });
const capability = () => btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(32))))
    .replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '');

export function parsePendingPurchase(raw: string | null, owner: string): PendingPurchase | null {
    if (!raw) return null;
    try {
        const record = JSON.parse(raw) as PendingPurchase;
        if (raw.length > maxBytes || record.version !== 1 || record.owner !== owner
            || !/^[A-Za-z0-9_-]{16,128}$/.test(record.idempotencyKey)
            || !['pending', 'rejected', 'review', 'complete'].includes(record.status)
            || !Array.isArray(record.payload?.items) || !record.payload.buyer || !record.payload.recipient
            || (owner === 'guest' && !/^[A-Za-z0-9_-]{43}$/.test(record.guestToken ?? ''))
            || (owner !== 'guest' && record.guestToken !== null)
            || (record.paymentKey !== undefined && !/^[A-Za-z0-9_-]{16,128}$/.test(record.paymentKey))
            || (record.orderId !== undefined && !positiveId(record.orderId))
            || (['review', 'rejected'].includes(record.status) && !positiveId(record.orderId))
            || (record.status === 'complete' && !positiveId(record.result?.order_id))) throw new Error();
        return record;
    } catch {
        throw new Error('Не удалось прочитать незавершённое оформление. Новая покупка остановлена, чтобы не создать второй заказ.');
    }
}

/** A tab-scoped recovery journal, never the authoritative order store. */
export class CheckoutOperationController {
    private readonly deps: Dependencies;
    private readonly listeners = new Set<() => void>();
    private readonly inFlight = new Map<string, Promise<CheckoutOrderResponse>>();

    constructor(deps: Dependencies) { this.deps = deps; }

    subscribe = (listener: () => void) => {
        this.listeners.add(listener);
        return () => { this.listeners.delete(listener); };
    };

    raw(owner: string): string | null { return this.deps.storage.getItem(prefix + owner); }

    pending(): PendingPurchase | null {
        const identity = this.deps.getIdentity();
        return identity ? parsePendingPurchase(this.raw(identity.owner), identity.owner) : null;
    }

    private identity(): PurchaseIdentity {
        const identity = this.deps.getIdentity();
        if (!identity) throw new Error('Дождитесь проверки входа в аккаунт.');
        return identity;
    }

    private write(record: PendingPurchase): void {
        try {
            const raw = JSON.stringify(record);
            if (new TextEncoder().encode(raw).length > maxBytes) throw new Error();
            this.deps.storage.setItem(prefix + record.owner, raw);
        } catch {
            throw new Error('Не удалось сохранить операцию в этой вкладке. Разрешите хранение данных браузера и попробуйте снова.');
        }
        this.listeners.forEach(listener => listener());
    }

    purchase(payload: CheckoutOrderPayload): Promise<CheckoutOrderResponse> {
        return this.prepare(() => {
            const identity = this.identity();
            let record = this.pending();
            if (record && semanticPayload(record.payload) !== semanticPayload(payload)) {
                throw new Error('Есть незавершённое оформление с другими данными. Сначала продолжите исходный заказ.');
            }
            if (!record) {
                record = {
                    version: 1, owner: identity.owner, idempotencyKey: crypto.randomUUID(),
                    guestToken: identity.owner === 'guest' ? capability() : null,
                    payload: JSON.parse(JSON.stringify(payload)) as CheckoutOrderPayload, status: 'pending',
                };
                this.write(record); // Must succeed before the first network side effect.
            }
            return this.send(record, identity);
        });
    }

    resume(): Promise<CheckoutOrderResponse> {
        return this.prepare(() => {
            const identity = this.identity(), record = this.pending();
            if (!record) throw new Error('Незавершённое оформление не найдено.');
            return this.send(record, identity);
        });
    }

    retryPayment(): Promise<CheckoutOrderResponse> {
        return this.prepare(() => {
            const identity = this.identity(), record = this.pending();
            if (!record || record.status !== 'rejected' || !record.orderId) {
                throw new Error('Сначала проверьте состояние предыдущей оплаты.');
            }
            const next: PendingPurchase = { ...record, status: 'pending', paymentKey: crypto.randomUUID() };
            this.write(next);
            return this.send(next, identity);
        });
    }

    /** Archive an identified order only through an explicit new-purchase action. */
    finish(): void {
        const record = this.pending();
        if (!record || !['complete', 'review'].includes(record.status)) throw new Error('Сначала завершите проверку заказа.');
        this.deps.storage.removeItem(prefix + record.owner);
        this.listeners.forEach(listener => listener());
    }

    guestTokenForOrder(orderId: number): string | null {
        // Guest capabilities are never offered while a customer account is active.
        if (this.deps.getIdentity()?.owner !== 'guest') return null;
        return this.deps.storage.getItem(`${prefix}guest-order:${orderId}`);
    }

    private prepare(action: () => Promise<CheckoutOrderResponse>): Promise<CheckoutOrderResponse> {
        try { return action(); } catch (error) { return Promise.reject(error); }
    }

    private send(record: PendingPurchase, identity: PurchaseIdentity): Promise<CheckoutOrderResponse> {
        const running = this.inFlight.get(identity.owner);
        if (running) return running;
        if (record.status === 'complete' && record.result) return Promise.resolve(record.result);
        if (record.status === 'review' && record.orderId) return Promise.resolve({ order_id: record.orderId });
        if (record.status === 'rejected') return Promise.reject(new Error('Оплата отклонена. Повторите оплату существующего заказа.'));
        const context: CheckoutRequestContext = {
            idempotencyKey: record.paymentKey ?? record.idempotencyKey,
            actor: record.guestToken ? { kind: 'guest', token: record.guestToken } : identity.actor,
        };
        const operation = (async () => {
            try {
                const result = record.paymentKey && record.orderId
                    ? await (this.deps.retryPayment ?? retryCheckoutPayment)(record.orderId, context)
                    : await (this.deps.createOrder ?? createCheckoutOrder)(record.payload, context);
                if (!positiveId(result.order_id) || (result.payment_url && new URL(result.payment_url).protocol !== 'https:')) {
                    throw new Error('Сервер вернул неполный ответ. Продолжите проверку исходного заказа.');
                }
                const completed: PendingPurchase = { ...record, status: 'complete', orderId: result.order_id, result };
                this.rememberGuest(completed);
                this.write(completed);
                const current = this.deps.getIdentity();
                if (current?.owner !== identity.owner || current.generation !== identity.generation) {
                    throw new DOMException('Purchase account changed', 'AbortError');
                }
                return result;
            } catch (error) {
                if (error instanceof ApiError && error.code === 'payment_requires_review' && error.orderId) {
                    const review: PendingPurchase = { ...record, status: 'review', orderId: error.orderId };
                    this.rememberGuest(review); this.write(review);
                } else if (error instanceof ApiError && error.code === 'payment_rejected' && error.orderId) {
                    const rejected: PendingPurchase = { ...record, status: 'rejected', orderId: error.orderId };
                    this.rememberGuest(rejected); this.write(rejected);
                } else if (error instanceof ApiError && error.orderId) {
                    const retained = { ...record, orderId: error.orderId };
                    this.rememberGuest(retained); this.write(retained);
                } else if (error instanceof ApiError && !record.orderId && (
                    [400, 422].includes(error.status)
                    || (error.status === 409 && ['checkout_stock_unavailable', 'checkout_catalog_unavailable', 'checkout_delivery_unavailable', 'checkout_price_changed', 'checkout_design_unavailable'].includes(error.code ?? ''))
                )) {
                    this.deps.storage.removeItem(prefix + record.owner);
                    this.listeners.forEach(listener => listener());
                }
                throw error;
            } finally { this.inFlight.delete(identity.owner); }
        })();
        this.inFlight.set(identity.owner, operation);
        return operation;
    }

    private rememberGuest(record: PendingPurchase): void {
        if (record.guestToken && record.orderId) {
            this.deps.storage.setItem(`${prefix}guest-order:${record.orderId}`, record.guestToken);
        }
    }
}
