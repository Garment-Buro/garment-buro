const ASSETS = '/service-home';
const asset = (filename: string, width: number, height: number) => ({ src: `${ASSETS}/${filename}`, width, height });

export type ServiceCategory = 'communities' | 'clothing' | 'people';
export const serviceCategoryLabels: Record<ServiceCategory, string> = {
    communities: 'СООБЩЕСТВА', clothing: 'ОДЕЖДА', people: 'ЛЮДИ',
};

export const serviceCommunities = [
    { id: 'runners', name: 'Light Running', image: asset('community-runners.webp', 576, 321), searchTerms: ['бег', 'спорт', 'беговое сообщество'] },
    { id: 'heart', name: 'Сообщество с сердцем', image: asset('community-heart.webp', 512, 640), searchTerms: ['любовь', 'друзья', 'общение'] },
    { id: 'boxing', name: 'Box Club', image: asset('community-boxing.webp', 640, 773), searchTerms: ['бокс', 'спорт', 'тренировки'] },
] as const;

// Original card artwork exported at 3x from Figma node 7010:937.
// Labels and repeated sample rows follow that frame literally.
export const serviceCommunityCards = [
    { id: 'boxing', name: 'BOXING CLUB', artwork: asset('communities/boxing-card.png', 501, 270), searchTerms: ['Box Club', 'бокс', 'спорт', 'тренировки'] },
    { id: 'horse', name: 'HORSE CLUB', artwork: asset('communities/horse-card.png', 501, 270), searchTerms: ['Сообщество с сердцем', 'сердце', 'лошади', 'любовь'] },
    { id: 'dream', name: 'BOXING CLUB — DREAM', artwork: asset('communities/dream-card.png', 501, 270), searchTerms: ['автомобили', 'машины', 'дрифт', 'гонки', 'car'] },
    { id: 'running', name: 'HORSE CLUB — LIGHT RUNNING', artwork: asset('communities/running-card.png', 501, 270), searchTerms: ['Light Running', 'бег', 'спорт', 'пробежка'] },
] as const;

export const serviceCommunityCatalog = [
    ...serviceCommunityCards, ...serviceCommunityCards, ...serviceCommunityCards.slice(0, 2),
].map((card, index) => ({ ...card, instanceId: `${card.id}-${index}` }));

export const servicePeople = [
    { id: 'liza', name: 'LIZA KUKHARSKAIA', subtitle: '@moeimyaliza', image: asset('person-liza.webp', 512, 512), portrait: 'lizaPortrait', searchTerms: ['Лиза Кухарская', 'moeimyaliza', 'мода', 'стиль'] },
    { id: 'member', name: 'УЧАСТНИК СООБЩЕСТВА', subtitle: 'Garment Buro', image: asset('person-man.webp', 320, 400), portrait: 'manPortrait', searchTerms: ['Garment Buro', 'спорт', 'бег', 'бокс'] },
] as const;

export const serviceProducts = [
    { id: 'top', name: 'Майка Horse Com', artwork: 'top', backdrop: 'person-liza', price: 8000, category: 'Майки', color: 'Чёрный', source: 'user', createdOrder: 6, image: asset('clothing-top.webp', 384, 384), searchTerms: ['лето', 'спорт', 'легкая одежда'] },
    { id: 'shoes', name: 'Кеды OG Run', artwork: 'shoes', backdrop: 'person-man', price: 8000, category: 'Аксессуары', color: 'Чёрный', source: 'community', createdOrder: 5, image: asset('clothing-shoes.webp', 384, 273), searchTerms: ['обувь', 'бег', 'спорт'] },
    { id: 'cap', name: 'Кепка RGM+', artwork: 'cap', backdrop: 'person-liza', price: 8000, category: 'Аксессуары', color: 'Серый', source: 'user', createdOrder: 4, image: asset('clothing-cap.webp', 384, 384), searchTerms: ['головной убор', 'лето', 'солнце'] },
    { id: 'hoodie', name: 'Худи', artwork: 'hoodie', backdrop: 'person-man', price: 8000, category: 'Худи', color: 'Чёрный', source: 'community', createdOrder: 3, image: asset('search/search-hoodie.webp', 640, 800), searchTerms: ['теплая одежда', 'толстовка', 'осень', 'зима'] },
    { id: 'top-second', name: 'Майка Horse Com', artwork: 'top', backdrop: 'person-liza', price: 8000, category: 'Майки', color: 'Чёрный', source: 'user', createdOrder: 2, image: asset('clothing-top.webp', 384, 384), searchTerms: ['лето', 'спорт', 'легкая одежда'] },
    { id: 'top-third', name: 'Майка Horse Com', artwork: 'top', backdrop: 'person-man', price: 8000, category: 'Майки', color: 'Чёрный', source: 'community', createdOrder: 1, image: asset('clothing-top.webp', 384, 384), searchTerms: ['лето', 'спорт', 'легкая одежда'] },
] as const;

export const serviceClothing = [serviceProducts[1], serviceProducts[2], serviceProducts[0], serviceProducts[3]];
