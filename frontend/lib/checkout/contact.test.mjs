import assert from 'node:assert/strict';
import test from 'node:test';
import { validContact, validCourierAddress, formatCourierAddress, emptyCourierAddress } from './contact.ts';

test('checkout validates real buyer and recipient contacts', () => {
    const contact = { name: 'Анна Соколова', phone: '+7 (900) 123-45-67', email: 'anna@example.test' };
    assert.equal(validContact(contact), true);
    for (const invalid of [{ name: ' ' }, { phone: '123' }, { email: 'anna@' }]) {
        assert.equal(validContact({ ...contact, ...invalid }), false);
    }
});

test('courier requires city street and house and retains access instructions', () => {
    assert.equal(validCourierAddress(emptyCourierAddress), false);
    const address = { ...emptyCourierAddress, city: 'Тверь', street: 'Советская', house: '12', apartment: '8', entrance: '2', intercom: '8К', comment: 'Позвонить заранее' };
    assert.equal(validCourierAddress(address), true);
    assert.equal(formatCourierAddress(address), 'Тверь, Советская, дом 12, кв. 8, подъезд 2, домофон 8К, Позвонить заранее');
});
