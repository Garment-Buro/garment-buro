'use client';

import dynamic from 'next/dynamic';
import { useState } from 'react';
import { Popup } from '@/components/shared/Popup';
import type { ConstructorPageController } from '@/hooks/constructor/useConstructorPageController';

const AuthPopup = dynamic(() => import('@/components/auth/AuthPopup').then(module => module.AuthPopup), { ssr: false });

export function ConstructorProjectStatus({ controller }: { controller: ConstructorPageController }) {
    const { projectSession: project, productError, retryProduct } = controller;
    const [dismissed, setDismissed] = useState<unknown>(null);
    const error = project.invalidId ? 'invalid-project-id' : project.error || productError;
    const status = error && typeof error === 'object' && 'status' in error ? error.status : null;
    const conflict = project.error && status === 409;
    const message = project.invalidId ? 'Неверный адрес проекта.'
        : conflict ? 'Проект изменён на другом устройстве. Ваши правки остаются здесь. Загрузка сохранённой версии заменит текущие изменения.'
        : status === 404 ? 'Проект или товар недоступен этому аккаунту либо удалён.'
        : error instanceof TypeError ? 'Нет связи с сервером. Изменения остаются в редакторе. Повторите сохранение после восстановления связи.'
        : error instanceof Error && !(error && typeof error === 'object' && 'status' in error) ? error.message
        : 'Не удалось выполнить действие. Изменения остаются в редакторе. Попробуйте ещё раз.';
    const loadingProject = project.status === 'loading'
        || (project.isExisting && project.account.userId !== null && !project.restored && !project.error && !project.invalidId);
    const busy = project.status === 'saving' || loadingProject;
    return <>
        {controller.cartPreparation.isPreparing && <Popup onClose={controller.cartPreparation.cancel} showClose={false} maxWidth={420}>
            <div className="flex flex-col gap-4 p-6 text-center font-manrope">
                <p role="status" aria-live="polite">Сохраняем изображения для корзины…</p>
                <button type="button" className="rounded-lg border p-3" onClick={controller.cartPreparation.cancel}>Отмена</button>
            </div>
        </Popup>}
        {controller.isSignInOpen && project.account.userId === null && <AuthPopup isOpen onClose={() => controller.setIsSignInOpen(false)} />}
        {busy && <Popup onClose={() => {}} showClose={false} maxWidth={420}>
            <p className="p-6 text-center font-manrope" role="status" aria-live="polite">
                {project.status === 'saving' ? 'Сохраняем проект в аккаунте…' : 'Загружаем сохранённый проект…'}
            </p>
        </Popup>}
        {!busy && Boolean(error) && error !== dismissed && <Popup onClose={() => setDismissed(error)} maxWidth={420}>
            <div className="flex flex-col gap-4 p-6 pt-16 font-manrope">
                <p role="alert">{message}</p>
                {conflict ? <button type="button" onClick={() => void project.reload()} className="rounded-lg border p-3">
                    Загрузить сохранённую версию и заменить правки
                </button> : productError ? <button type="button" onClick={retryProduct} className="rounded-lg border p-3">Повторить загрузку товара</button>
                    : project.isExisting && !project.document && !project.invalidId ? <button type="button" onClick={() => void project.reload()} className="rounded-lg border p-3">Повторить загрузку проекта</button> : null}
                <button type="button" onClick={() => setDismissed(error)} className="rounded-lg border p-3">Вернуться в редактор</button>
            </div>
        </Popup>}
    </>;
}

export function ConstructorProjectNotice({ controller }: { controller: ConstructorPageController }) {
    const project = controller.projectSession;
    if (project.status !== 'idle') return null;
    return <aside className="relative z-40 mx-3 shrink-0 rounded-lg bg-white/95 px-3 py-2 text-center text-sm font-manrope" aria-live="polite">
            {!project.account.sessionReady ? <span>Восстанавливаем сессию…</span>
                : project.isExisting && project.account.userId === null ? <button type="button" onClick={() => controller.setIsSignInOpen(true)}>Войдите, чтобы открыть проект</button>
                    : project.document?.product_id === null ? <span>Товар удалён. Проект сохранён в аккаунте; редактирование пока недоступно.</span>
                        : controller.product && controller.pricing.error ? <span role="alert">Не удалось рассчитать стоимость. <button type="button" className="underline" onClick={controller.pricing.retry}>Повторить расчёт</button></span>
                                : controller.product && !controller.pricing.quote ? <span role="status">Рассчитываем стоимость…</span>
                                : controller.product && !controller.selectionAvailable ? <span role="status">Выбранный вариант недоступен. <button type="button" className="underline" onClick={() => controller.setIsSizeModalOpen(true)}>Выбрать размер и цвет</button></span>
                                : controller.saveNotice ? <span role="status">{controller.saveNotice}</span>
                                : controller.isProductExpected && !controller.product && !controller.productError ? <span role="status">Загружаем товар…</span>
                                : project.document ? <span>Открыт проект №{project.document.id}</span>
                                    : <span>Проект ещё не сохранён в аккаунте.</span>}
        </aside>;
}
