'use client';

import Link from 'next/link';
import { ApiError } from '@/lib/api/http';
import type { useLandingEditor } from '@/hooks/partner/useLandingEditor';
import type { LandingDraft } from '@/lib/partners/landingEditor';
import { PartnerProductPicker } from './PartnerProductPicker';
import styles from './PartnerLandingEditor.module.css';

type Editor = ReturnType<typeof useLandingEditor>;
const textFields = [
    ['title', 'Название сообщества / коллекции', 255],
    ['eyebrow', 'Короткая подпись над заголовком', 120],
    ['headline', 'Главный заголовок', 255],
    ['description', 'Описание коллекции', 4000],
    ['cta_label', 'Текст кнопки', 80],
    ['cta_href', 'Куда ведёт кнопка', 2048],
    ['image_url', 'Ссылка на главное изображение', 4096],
] as const;
const contentFields = [
    ['logo_url', 'Логотип', 4096],
    ['secondary_image_url', 'Второе изображение', 4096],
    ['story_title', 'Заголовок истории', 255],
    ['story_body', 'История сообщества', 2000],
    ['model_heading', 'Заголовок коллекции', 255],
    ['proof_line', 'Подпись под коллекцией', 255],
    ['final_heading', 'Заключительный заголовок', 255],
] as const;

export function PartnerLandingEditor({ editor }: { editor: Editor }) {
    const state = editor.state;
    if (!state?.editing) return null;
    const { draft, record } = state,
        busy = state.status !== 'ready',
        disabled = busy || state.conflict,
        published = record?.status === 'published';
    const error = state.conflict
        ? record
            ? 'Лендинг изменён в другой вкладке. Ваши правки остались в форме. Загрузите актуальную версию, чтобы продолжить.'
            : 'Этот адрес уже занят. Выберите другой адрес и сохраните черновик.'
        : state.error instanceof ApiError && state.error.status === 422
          ? 'Проверьте поля и состав коллекции. Публикуются только доступные модели каталога.'
          : state.error instanceof ApiError && state.error.status === 404
            ? 'Лендинг или доступ владельца больше не доступны.'
            : state.error
              ? 'Не удалось выполнить действие. Ваши правки остались в форме; повторите попытку.'
              : null;
    const close = () => {
        if (!editor.dirty || window.confirm('Закрыть редактор и потерять несохранённые изменения?'))
            editor.close();
    };
    const field = (key: keyof LandingDraft, value: string) => editor.setField(key, value);
    return (
        <form
            className={styles.editor}
            aria-label="Редактор сообщества"
            onSubmit={(event) => {
                event.preventDefault();
                void editor.save();
            }}
        >
            <div className={styles.heading}>
                <h3>{record ? 'Редактировать сообщество' : 'Новое сообщество'}</h3>
                <button type="button" disabled={busy} onClick={close}>
                    Закрыть
                </button>
            </div>
            <p>
                Создайте страницу о своём сообществе и подберите коллекцию. Сохранённый черновик
                виден только вам; публикация — отдельное действие.
            </p>
            <p role="status">
                {published
                    ? 'Лендинг опубликован'
                    : record?.status === 'archived'
                      ? 'Лендинг в архиве'
                      : 'Черновик — скрыт от посетителей'}
            </p>
            <fieldset className={styles.fields} disabled={busy}>
                <label className={styles.field}>
                    Адрес страницы
                    <input
                        name="slug"
                        value={draft.slug}
                        disabled={Boolean(record)}
                        required
                        minLength={3}
                        maxLength={96}
                        pattern="[a-z0-9][a-z0-9\-]{2,95}"
                        autoCapitalize="none"
                        spellCheck={false}
                        onChange={(event) => field('slug', event.target.value)}
                    />
                    <small>
                        /p/{draft.slug || 'ваше-сообщество'} · латиница, цифры, дефис. После
                        создания адрес сохраняется.
                    </small>
                </label>
                {textFields.map(([key, label, max]) => (
                    <label className={styles.field} key={key}>
                        {label}
                        {key === 'description' ? (
                            <textarea
                                name={key}
                                required
                                maxLength={max}
                                rows={5}
                                value={draft[key]}
                                onChange={(event) => field(key, event.target.value)}
                            />
                        ) : (
                            <input
                                name={key}
                                required={!['eyebrow', 'image_url'].includes(key)}
                                maxLength={max}
                                value={draft[key] ?? ''}
                                onChange={(event) => field(key, event.target.value)}
                            />
                        )}
                        {key === 'cta_href' && (
                            <small>Страница внутри GARMENT BURO, например /catalog/products.</small>
                        )}
                        {key === 'image_url' && (
                            <small>Путь к изображению на сайте или HTTPS-ссылка.</small>
                        )}
                    </label>
                ))}
                <details>
                    <summary>История, дополнительные изображения и вопросы</summary>
                    <div className={styles.fields}>
                        {contentFields.map(([key, label, max]) => (
                            <label className={styles.field} key={key}>
                                {label}
                                {key === 'story_body' ? (
                                    <textarea
                                        rows={5}
                                        maxLength={max}
                                        value={draft.content[key] ?? ''}
                                        onChange={(event) =>
                                            editor.setField('content', {
                                                ...draft.content,
                                                [key]: event.target.value,
                                            })
                                        }
                                    />
                                ) : (
                                    <input
                                        maxLength={max}
                                        value={draft.content[key] ?? ''}
                                        onChange={(event) =>
                                            editor.setField('content', {
                                                ...draft.content,
                                                [key]: event.target.value,
                                            })
                                        }
                                    />
                                )}
                            </label>
                        ))}
                        {draft.content.faq.map((item, index) => (
                            <div className={styles.faq} key={index}>
                                <label className={styles.field}>
                                    Вопрос {index + 1}
                                    <input
                                        required
                                        maxLength={255}
                                        value={item.question}
                                        onChange={(event) =>
                                            editor.setField('content', {
                                                ...draft.content,
                                                faq: draft.content.faq.map((entry, i) =>
                                                    i === index
                                                        ? { ...entry, question: event.target.value }
                                                        : entry,
                                                ),
                                            })
                                        }
                                    />
                                </label>
                                <label className={styles.field}>
                                    Ответ
                                    <textarea
                                        required
                                        maxLength={1000}
                                        rows={3}
                                        value={item.answer}
                                        onChange={(event) =>
                                            editor.setField('content', {
                                                ...draft.content,
                                                faq: draft.content.faq.map((entry, i) =>
                                                    i === index
                                                        ? { ...entry, answer: event.target.value }
                                                        : entry,
                                                ),
                                            })
                                        }
                                    />
                                </label>
                                <button
                                    type="button"
                                    onClick={() =>
                                        editor.setField('content', {
                                            ...draft.content,
                                            faq: draft.content.faq.filter((_, i) => i !== index),
                                        })
                                    }
                                >
                                    Удалить вопрос {index + 1}
                                </button>
                            </div>
                        ))}
                        <button
                            type="button"
                            disabled={draft.content.faq.length >= 12}
                            onClick={() =>
                                editor.setField('content', {
                                    ...draft.content,
                                    faq: [...draft.content.faq, { question: '', answer: '' }],
                                })
                            }
                        >
                            Добавить вопрос
                        </button>
                    </div>
                </details>
            </fieldset>
            <PartnerProductPicker
                ids={draft.product_ids}
                disabled={busy}
                onChange={editor.setProducts}
            />
            {error && (
                <p role="alert" className={styles.error}>
                    {error}
                </p>
            )}
            {state.conflict && record && (
                <button type="button" disabled={busy} onClick={() => void editor.reload()}>
                    Загрузить актуальную версию и сбросить мои правки
                </button>
            )}
            {state.saved && <p role="status">Изменения сохранены.</p>}
            {busy && <p role="status">Выполняем действие…</p>}
            <div className={styles.actions}>
                <button className={styles.primary} type="submit" disabled={disabled}>
                    {record ? 'Сохранить изменения' : 'Сохранить черновик'}
                </button>
                <button
                    type="button"
                    disabled={
                        disabled ||
                        !record ||
                        (!published && (editor.dirty || !record.product_ids.length))
                    }
                    onClick={() => void editor.publish(!published)}
                >
                    {published ? 'Снять с публикации' : 'Опубликовать'}
                </button>
                {published && record && (
                    <Link
                        href={`/p/${encodeURIComponent(record.slug)}`}
                        prefetch={false}
                        target="_blank"
                        rel="noreferrer"
                    >
                        Посмотреть страницу ↗
                    </Link>
                )}
            </div>
            {editor.dirty && (
                <p>
                    {published
                        ? 'Сохранение сразу изменит опубликованную страницу. Можно сначала снять её с публикации — правки останутся в форме.'
                        : 'Перед публикацией сохраните изменения и выберите хотя бы одну модель.'}
                </p>
            )}
        </form>
    );
}
