import type { PublicPartnerLanding } from '@/lib/partners/types';

export const defaultLandingFaq = [
    {
        question: 'Сколько занимает производство?',
        answer: 'Срок производства показывается перед оплатой. Он зависит от модели и выбранных деталей.',
    },
    {
        question: 'Как выбрать размер?',
        answer: 'В конструкторе есть таблица размеров и подсказки по посадке для каждой модели.',
    },
    {
        question: 'Можно сохранить дизайн и вернуться позже?',
        answer: 'Да. После входа дизайн появится в разделе UNFINISHED вашего личного кабинета.',
    },
    {
        question: 'Где будет купленная вещь?',
        answer: 'После оформления изделие и заказ появятся в MY COLLECTION и в истории профиля.',
    },
    {
        question: 'Как работает доставка?',
        answer: 'Способ и стоимость доставки рассчитываются во время оформления заказа.',
    },
    {
        question: 'Куда обратиться с вопросом?',
        answer: 'Напишите в поддержку GARMENT BURO через раздел PROFILE в личном кабинете.',
    },
];

export const getLandingCopy = (landing: PublicPartnerLanding) => ({
    storyTitle: landing.content.story_title || 'Коллекция начинается с идеи автора и заканчивается вашей вещью',
    storyBody: landing.content.story_body || (
        `${landing.partner_name} выбирает направление и модели. `
        + 'Вы настраиваете изделие под себя, а GARMENT BURO отвечает за производство и доставку.'
    ),
    modelHeading: landing.content.model_heading || 'Выберите основу для своего дизайна',
    proofLine: landing.content.proof_line || 'Производство и доставка GARMENT BURO',
    finalHeading: landing.content.final_heading || 'Соберите вещь, которая продолжает идею коллекции',
    faq: landing.content.faq.length ? landing.content.faq : defaultLandingFaq,
});
