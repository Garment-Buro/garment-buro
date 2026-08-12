import type {
    CheckoutOrderPayload,
    CheckoutOrderResponse,
    DeliveryCalculationRequest,
    DeliveryCalculationResponse,
} from '@/lib/checkout/types';

import { requestJson } from './http';

export const calculateCdekDelivery = (payload: DeliveryCalculationRequest) => requestJson<DeliveryCalculationResponse>('/cdek/calculate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
});

export const createCheckoutOrder = (payload: CheckoutOrderPayload) => requestJson<CheckoutOrderResponse>('/orders', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
});
