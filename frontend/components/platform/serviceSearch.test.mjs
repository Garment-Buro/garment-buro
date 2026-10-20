import assert from 'node:assert/strict';
import test from 'node:test';
import { rankServiceItems } from './serviceSearch.ts';

const items = [
    { id: 'cap', name: 'Кепка RGM+', searchTerms: ['головной убор'] },
    { id: 'hoodie', name: 'Худи' },
    { id: 'shoes', name: 'Кеды OG Run' },
    { id: 'top', name: 'Майка Horse Com' },
];
const ids = (query) => rankServiceItems(items, query).map(item => item.id);

test('search promotes title matches and keeps every other card in stable order', () => {
    assert.deepEqual(ids('  МАЙКА  '), ['top', 'cap', 'hoodie', 'shoes']);
    assert.deepEqual(items.map(item => item.id), ['cap', 'hoodie', 'shoes', 'top']);
    assert.deepEqual(ids(''), ['cap', 'hoodie', 'shoes', 'top']);
    assert.deepEqual(ids('  !  '), ['cap', 'hoodie', 'shoes', 'top']);
    assert.deepEqual(ids('несуществующая карточка'), ['cap', 'hoodie', 'shoes', 'top']);
});

test('search ranks synonyms and misspellings without removing non-matches', () => {
    assert.deepEqual(ids('толстовка'), ['hoodie', 'cap', 'shoes', 'top']);
    assert.deepEqual(ids('худди'), ['hoodie', 'cap', 'shoes', 'top']);
    assert.deepEqual(ids('пробежка'), ['shoes', 'cap', 'hoodie', 'top']);
    assert.deepEqual(ids('тёплая'), ['hoodie', 'cap', 'shoes', 'top']);
});

test('each category ranks independently, including people aliases and community topics', () => {
    const communities = [{ id: 'heart', name: 'Сообщество с сердцем' }, { id: 'run', name: 'Light Running' }];
    const people = [{ id: 'member', name: 'Участник сообщества' }, { id: 'liza', name: 'LIZA KUKHARSKAIA', searchTerms: ['Лиза Кухарская', '@moeimyaliza'] }];
    assert.deepEqual(rankServiceItems(communities, 'бег').map(item => item.id), ['run', 'heart']);
    assert.deepEqual(rankServiceItems(people, 'лиза').map(item => item.id), ['liza', 'member']);
    assert.deepEqual(rankServiceItems(people, 'moeimyaliza').map(item => item.id), ['liza', 'member']);
});

test('a direct title match outranks related topics and multi-word queries favor full matches', () => {
    const options = [{ id: 'related', name: 'Кеды' }, { id: 'direct', name: 'Бег' }];
    assert.deepEqual(rankServiceItems(options, 'бег').map(item => item.id), ['direct', 'related']);
    const names = [{ id: 'partial', name: 'Лиза Иванова' }, { id: 'full', name: 'Лиза Кухарская' }];
    assert.deepEqual(rankServiceItems(names, 'лиза кухарская').map(item => item.id), ['full', 'partial']);
});
