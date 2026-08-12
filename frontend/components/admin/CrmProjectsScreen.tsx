'use client';

import { AdminPageShell } from '@/components/admin/AdminPageShell';
import { CrmProjectsTable } from '@/components/admin/CrmProjectsTable';
import { Text } from '@/components/shared/Text';
import { useCrmProjects } from '@/hooks/admin/useCrmProjects';
import { useIdentityAccess } from '@/hooks/auth/useIdentityAccess';

type ActionButtonProps = {
    label: string;
    onClick: () => void;
    disabled?: boolean;
};

const ActionButton = ({ label, onClick, disabled = false }: ActionButtonProps) => (
    <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        className="rounded-md bg-black px-4 py-2 text-white transition hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
    >
        {label}
    </button>
);

export function CrmProjectsScreen() {
    const identityAccess = useIdentityAccess();
    const projects = useCrmProjects(identityAccess.hasCrmAccess);

    let content;
    if (!identityAccess.isSessionReady) {
        content = <Text size={16} className="text-gray-500">Проверяем доступ...</Text>;
    } else if (!identityAccess.isAuthenticated) {
        content = (
            <Text size={16} className="text-gray-600">
                Войдите в личный кабинет под учётной записью сотрудника.
            </Text>
        );
    } else if (identityAccess.status === 'idle' || identityAccess.status === 'loading') {
        content = <Text size={16} className="text-gray-500">Проверяем доступ...</Text>;
    } else if (identityAccess.status === 'error') {
        content = (
            <div className="space-y-4">
                <Text size={16} className="text-red-700">
                    Не удалось проверить права доступа. Повторите запрос.
                </Text>
                <ActionButton label="Повторить" onClick={identityAccess.retry} />
            </div>
        );
    } else if (!identityAccess.hasCrmAccess) {
        content = (
            <Text size={16} className="text-red-700">
                У этой учётной записи нет доступа к производственному кабинету.
            </Text>
        );
    } else if (projects.isLoading) {
        content = <Text size={16} className="text-gray-500">Загружаем проекты...</Text>;
    } else if (projects.hasError && projects.projects.length === 0) {
        content = (
            <div className="space-y-4">
                <Text size={16} className="text-red-700">
                    Не удалось загрузить проекты. Данные не изменены.
                </Text>
                <ActionButton label="Повторить" onClick={projects.retry} />
            </div>
        );
    } else {
        content = (
            <div className="space-y-4">
                {projects.hasError ? (
                    <div className="flex items-center justify-between gap-4 rounded-md bg-red-50 p-4">
                        <Text size={14} className="text-red-700">
                            Следующая страница не загрузилась. Уже полученные данные сохранены.
                        </Text>
                        <ActionButton label="Обновить" onClick={projects.retry} />
                    </div>
                ) : null}
                <CrmProjectsTable projects={projects.projects} />
                {projects.nextCursor !== null ? (
                    <ActionButton
                        label={projects.isLoadingMore ? 'Загружаем...' : 'Показать ещё'}
                        onClick={projects.loadMore}
                        disabled={projects.isLoadingMore}
                    />
                ) : null}
            </div>
        );
    }

    return (
        <AdminPageShell activeSection="crm" title="Производственные проекты">
            {content}
        </AdminPageShell>
    );
}
