'use client';

import Link from 'next/link';
import { usePublicProfileEditor } from '@/hooks/people/usePublicProfileEditor';
import { personHref } from '@/lib/catalog/people';
import { ApiError } from '@/lib/api/http';
import { PublicAvatar } from './PublicAvatar';
import styles from './PublicPerson.module.css';

export function PublicProfileEditor() {
    const editor = usePublicProfileEditor();
    const state = editor.state;
    let body;
    if (!editor.sessionReady) body = <p role="status">Восстанавливаем сессию…</p>;
    else if (!editor.authenticated) body = <div className={styles.message}><p>Войдите, чтобы создать или изменить свой публичный профиль.</p><Link className={styles.back} href="/profile" prefetch={false}>Войти в аккаунт</Link></div>;
    else if (!state || !state.loaded) body = state?.error ? <div role="alert"><p>Не удалось загрузить ваш профиль.</p><button className={styles.retry} onClick={() => void editor.reload()}>Повторить</button></div> : <p role="status">Загружаем профиль…</p>;
    else {
        const busy = state.status !== 'ready';
        const disabled = busy || state.conflict;
        const published = state.profile?.is_published ?? false;
        const error = state.conflict ? 'Профиль изменён в другой вкладке или адрес занят. Ваш текст сохранён в форме. Загрузите актуальную версию, чтобы продолжить.'
            : state.error instanceof RangeError ? state.error.message
            : state.error instanceof ApiError && state.error.status === 422 ? 'Проверьте адрес, имя и описание. Фото должно быть JPEG, PNG или WebP до 8 МБ.'
            : state.error instanceof ApiError && state.error.status === 413 ? 'Выберите фото размером до 8 МБ.'
            : state.error ? 'Не удалось сохранить изменения. Текст остался в форме; повторите попытку.' : null;
        body = <form className={styles.editor} aria-label="Редактор публичного профиля" onSubmit={event => { event.preventDefault(); void editor.save(); }}>
            <p className={styles.explanation}>Эти поля видят другие люди после публикации. Контакты и личные данные аккаунта сюда не добавляются.</p>
            <p role="status">{published ? 'Профиль опубликован' : 'Черновик — виден только вам'}</p>
            <div className={styles.photoSection}>
                <PublicAvatar src={state.avatarUrl} name={state.draft.display_name || 'Пользователь'} className={styles.editorAvatar} eager />
                <div>
                    <label className={styles.field}>
                        <span>Фото профиля</span>
                        <input type="file" accept="image/jpeg,image/png,image/webp" disabled={disabled || !state.profile} onChange={event => {
                            const file = event.target.files?.[0]; event.target.value = '';
                            if (file) void editor.upload(file);
                        }} />
                    </label>
                    <p className={styles.hint}>JPEG, PNG или WebP до 8 МБ. {state.profile ? 'Фото сохраняется отдельно от текста.' : 'Сначала сохраните черновик.'}</p>
                    {state.avatarError && <p role="alert">Фото временно недоступно. Остальные поля можно редактировать.</p>}
                    {state.profile?.avatar_id && <button className={styles.secondary} type="button" disabled={disabled} onClick={() => void editor.removeAvatar()}>Удалить фото</button>}
                </div>
            </div>
            <label className={styles.field}><span id="public-slug-label">Публичный адрес</span>
                <input name="slug" required minLength={3} maxLength={64} pattern="[a-z0-9][a-z0-9\-]{2,63}" autoCapitalize="none" autoComplete="off" spellCheck={false} disabled={busy}
                    aria-labelledby="public-slug-label" aria-describedby="public-slug-hint" value={state.draft.slug} onChange={event => editor.setField('slug', event.target.value)} />
                <span className={styles.hint} id="public-slug-hint">От 3 до 64 символов: строчные латинские буквы, цифры и дефис. Адрес: /people/{state.draft.slug || 'ваш-адрес'}</span>
            </label>
            <label className={styles.field}><span>Публичное имя</span>
                <input name="display_name" required maxLength={120} autoComplete="off" disabled={busy} value={state.draft.display_name} onChange={event => editor.setField('display_name', event.target.value)} />
            </label>
            <div className={styles.field}><label htmlFor="public-profile-bio">О себе</label>
                <textarea id="public-profile-bio" name="bio" rows={6} maxLength={2000} disabled={busy} value={state.draft.bio} onChange={event => editor.setField('bio', event.target.value)} />
            </div>
            {error && <p role="alert">{error}</p>}
            {state.conflict && <button className={styles.secondary} type="button" disabled={busy} onClick={() => void editor.reload()}>Загрузить актуальную версию и сбросить мой текст</button>}
            {state.saved && <p role="status">Изменения сохранены.</p>}
            {busy && <p role="status">Сохраняем изменения…</p>}
            <div className={styles.actions}>
                <button className={styles.retry} type="submit" disabled={disabled}>{state.profile ? 'Сохранить текст' : 'Сохранить черновик'}</button>
                <button className={styles.secondary} type="button" disabled={disabled || !state.profile || !published && editor.dirty} onClick={() => void editor.publish(!published)}>{published ? 'Снять с публикации' : 'Опубликовать профиль'}</button>
                {published && state.profile && <Link className={styles.secondary} href={personHref(state.profile.slug)} prefetch={false}>Посмотреть публичную страницу</Link>}
            </div>
            {editor.dirty && <p className={styles.hint}>{published ? 'Сохранённые изменения сразу видны в опубликованном профиле. Можно сначала снять профиль с публикации — текст останется в форме.' : 'Сохраните текст перед публикацией.'}</p>}
        </form>;
    }
    return <section className={styles.page} aria-labelledby="public-editor-title">
        <Link className={styles.back} href="/profile" prefetch={false}>← Личный кабинет</Link>
        <h1 id="public-editor-title" className={styles.editorTitle}>Мой публичный профиль</h1>
        {body}
    </section>;
}
