import { calculateCdekDelivery } from '../api/checkout.ts';
import type { DeliveryCalculationRequest, DeliveryCalculationResponse } from './types.ts';

type QuoteState = {
    key: string | null;
    status: 'idle' | 'loading' | 'ready' | 'error';
    quote: DeliveryCalculationResponse | null;
    expiresAt: number;
};
const empty: QuoteState = { key: null, status: 'idle', quote: null, expiresAt: 0 };
export const quoteRequestKey = (request: DeliveryCalculationRequest | null) => request ? JSON.stringify(request) : null;

export class DeliveryQuoteController {
    private state: QuoteState = empty;
    private abort: AbortController | null = null;
    private readonly listeners = new Set<() => void>();
    private readonly now: () => number;

    constructor(now: () => number = Date.now) { this.now = now; }
    getSnapshot = () => this.state;
    subscribe = (listener: () => void) => {
        this.listeners.add(listener);
        return () => { this.listeners.delete(listener); };
    };
    private publish(state: QuoteState) {
        this.state = state;
        this.listeners.forEach(listener => listener());
    }
    cancel = () => {
        this.abort?.abort(); this.abort = null;
        if (this.state !== empty) this.publish(empty);
    };
    expire = () => {
        if (this.state.quote && this.state.expiresAt <= this.now()) this.publish({ ...this.state, status: 'error', quote: null });
    };

    async update(request: DeliveryCalculationRequest | null, active: boolean): Promise<void> {
        this.cancel();
        if (!active || !request) return;
        const abort = new AbortController();
        this.abort = abort;
        const key = quoteRequestKey(request), startedAt = this.now();
        this.publish({ key, status: 'loading', quote: null, expiresAt: 0 });
        try {
            const quote = await calculateCdekDelivery(request, abort.signal);
            if (abort.signal.aborted || this.abort !== abort) return;
            if (!quote.quote_token || !Number.isFinite(quote.delivery_price) || quote.delivery_price < 0
                || !quote.delivery_city || !quote.delivery_address || quote.currency !== 'RUB'
                || (request.delivery_method === 'cdek_pickup' && quote.cdek_point_code !== request.cdek_point_code)) throw new Error();
            // Conservative client refresh, before the server's 15-minute proof expires.
            const expiresAt = startedAt + 14 * 60 * 1000;
            if (expiresAt <= this.now()) throw new Error();
            this.publish({ key, status: 'ready', quote, expiresAt });
        } catch {
            if (!abort.signal.aborted && this.abort === abort) this.publish({ key, status: 'error', quote: null, expiresAt: 0 });
        }
    }
}
