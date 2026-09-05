export type CheckoutContact = { name: string; phone: string; email: string };
export type CourierAddress = { city: string; street: string; house: string; apartment: string; entrance: string; floor: string; intercom: string; comment: string };
export const emptyContact: CheckoutContact = { name: '', phone: '', email: '' };
export const emptyCourierAddress: CourierAddress = { city: '', street: '', house: '', apartment: '', entrance: '', floor: '', intercom: '', comment: '' };
export const validContact = (contact: CheckoutContact) => contact.name.trim().length >= 2
    && /^\+?\d{7,15}$/.test(contact.phone.replace(/[\s()-]/g, ''))
    && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(contact.email.trim());
export const validCourierAddress = (address: CourierAddress) => [address.city, address.street, address.house].every(value => value.trim().length > 0);
export const formatCourierAddress = (address: CourierAddress) => [
    address.city.trim(), address.street.trim(), `дом ${address.house.trim()}`,
    address.apartment && `кв. ${address.apartment}`, address.entrance && `подъезд ${address.entrance}`,
    address.floor && `этаж ${address.floor}`, address.intercom && `домофон ${address.intercom}`,
    address.comment,
].filter(Boolean).join(', ');
