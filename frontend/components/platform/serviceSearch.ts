export interface ServiceSearchItem {
    name: string;
    searchTerms?: readonly string[];
}

const normalize = (value: string) => value.toLocaleLowerCase('ru').replaceAll('ё', 'е')
    .replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
const words = (value: string) => normalize(value).split(' ').filter(Boolean);
const stem = (value: string) => value.length > 4
    ? value.replace(/(иями|ами|ями|ого|ому|ах|ях|ой|ей|ый|ий|ая|яя|ое|ее|ов|ев|ом|ем|ы|и|а|я|у|ю|е|о)$/u, '') : value;
const topics = [
    ['бег', 'бегать', 'беговой', 'пробежка', 'running', 'run', 'runner', 'runners', 'jogging', 'кроссовки', 'кеды'],
    ['бокс', 'boxing', 'box', 'единоборства'],
    ['сердце', 'сердцем', 'heart', 'любовь'],
    ['кепка', 'кепки', 'cap', 'бейсболка', 'шапка', 'головной'],
    ['майка', 'майки', 'top', 'безрукавка', 'футболка', 'tank'],
    ['худи', 'hoodie', 'толстовка', 'свитшот', 'теплый', 'теплая'],
    ['спорт', 'спортивный', 'тренировка', 'fitness', 'workout'],
].map(topic => new Set(topic.map(stem)));

function editDistance(a: string, b: string): number {
    let previous = Array.from({ length: b.length + 1 }, (_, index) => index);
    for (let i = 1; i <= a.length; i++) {
        const current = [i];
        for (let j = 1; j <= b.length; j++) {
            current[j] = Math.min(current[j - 1] + 1, previous[j] + 1, previous[j - 1] + Number(a[i - 1] !== b[j - 1]));
        }
        previous = current;
    }
    return previous[b.length];
}

function wordScore(query: string, candidate: string): number {
    if (query === candidate) return 100;
    if (query.length >= 2 && candidate.startsWith(query)) return 80;
    const queryStem = stem(query);
    const candidateStem = stem(candidate);
    if (queryStem === candidateStem) return 75;
    if (topics.some(topic => topic.has(queryStem) && topic.has(candidateStem))) return 50;
    if (query.length >= 3 && candidate.length >= 3) {
        const distance = editDistance(query, candidate);
        if (distance <= (query.length > 6 ? 2 : 1)) return 30 - distance;
    }
    return 0;
}

function relevance(item: ServiceSearchItem, query: string): number {
    const name = normalize(item.name);
    const titleWords = words(item.name);
    const relatedWords = (item.searchTerms ?? []).flatMap(words);
    let score = name === query ? 10000 : name.startsWith(query) ? 9000 : name.includes(query) ? 8000 : 0;
    for (const term of words(query)) {
        score += Math.max(0, ...titleWords.map(candidate => wordScore(term, candidate)),
            ...relatedWords.map(candidate => wordScore(term, candidate) * .7));
    }
    return score;
}

export function rankServiceItems<T extends ServiceSearchItem>(items: readonly T[], query: string): T[] {
    const normalizedQuery = normalize(query);
    if (!normalizedQuery) return [...items];
    return items.map((item, index) => ({ item, index, score: relevance(item, normalizedQuery) }))
        .sort((a, b) => b.score - a.score || a.index - b.index)
        .map(({ item }) => item);
}
