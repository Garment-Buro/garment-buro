export type TextRevealDirection = 'start' | 'end' | 'center';

type RandomCharacterOptions = {
    originalChar: string;
    sourceText: string;
    characters: string;
    useOriginalCharsOnly: boolean;
};

export const getRandomTextCharacter = ({
    originalChar,
    sourceText,
    characters,
    useOriginalCharsOnly,
}: RandomCharacterOptions) => {
    const pool = useOriginalCharsOnly
        ? sourceText.replace(/\s/g, '') || originalChar
        : characters;
    return pool[Math.floor(Math.random() * pool.length)];
};

type DecryptedTextFrameOptions = {
    text: string;
    iteration: number;
    totalIterations: number;
    revealDirection: TextRevealDirection;
    sequential: boolean;
    getRandomCharacter: (originalChar: string) => string;
};

export const createDecryptedTextFrame = ({
    text,
    iteration,
    totalIterations,
    revealDirection,
    sequential,
    getRandomCharacter,
}: DecryptedTextFrameOptions) => {
    const textArray = text.split('');
    const centerIndex = (textArray.length - 1) / 2;

    return textArray.map((character, index) => {
        if (character === ' ') return ' ';
        if (!sequential) {
            return iteration >= totalIterations ? character : getRandomCharacter(character);
        }

        const progress = iteration / totalIterations;
        const threshold = revealDirection === 'end'
            ? (textArray.length - 1 - index) / textArray.length
            : revealDirection === 'center'
                ? Math.abs(index - centerIndex) / Math.max(centerIndex, 1)
                : index / textArray.length;

        return progress > threshold ? character : getRandomCharacter(character);
    }).join('');
};

export const randomizeText = (text: string, getRandomCharacter: (originalChar: string) => string) => (
    text.split('').map(character => character === ' ' ? ' ' : getRandomCharacter(character)).join('')
);
