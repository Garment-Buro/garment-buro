import { create } from 'zustand';
import type { CdekOffice } from '@/lib/cdek/types';
import { emptyContact, emptyCourierAddress, type CheckoutContact, type CourierAddress } from '@/lib/checkout/contact';

// Contact details stay in memory, not in long-lived localStorage on shared devices.
type CheckoutDetails = {
    buyer: CheckoutContact;
    recipient: CheckoutContact;
    recipientIsBuyer: boolean;
    courier: CourierAddress;
    point: CdekOffice | null;
    setContacts: (buyer: CheckoutContact, recipient: CheckoutContact, recipientIsBuyer: boolean) => void;
    setCourier: (courier: CourierAddress) => void;
    setPoint: (point: CdekOffice) => void;
    clear: () => void;
};
const initial = { buyer: emptyContact, recipient: emptyContact, recipientIsBuyer: true, courier: emptyCourierAddress, point: null };
export const useCheckoutDetailsStore = create<CheckoutDetails>((set) => ({
    ...initial,
    setContacts: (buyer, recipient, recipientIsBuyer) => set({ buyer, recipient, recipientIsBuyer }),
    setCourier: courier => set({ courier }),
    setPoint: point => set({ point }),
    clear: () => set(initial),
}));
