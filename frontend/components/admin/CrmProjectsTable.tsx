import type { CrmProjectSummary } from '@/lib/crm/types';
import {
    formatCrmDate,
    getCrmProjectStatusClassName,
    getCrmProjectStatusLabel,
} from '@/lib/crm/utils/projectFormatting';

type CrmProjectsTableProps = {
    projects: CrmProjectSummary[];
};

export function CrmProjectsTable({ projects }: CrmProjectsTableProps) {
    return (
        <div className="overflow-x-auto rounded-md border border-black/10 bg-white text-black shadow-sm">
            <table className="w-full min-w-[820px] border-collapse text-left">
                <thead>
                    <tr className="border-b border-black/10 bg-gray-50">
                        <th className="p-4 font-semibold">Проект</th>
                        <th className="p-4 font-semibold">Заказ</th>
                        <th className="p-4 font-semibold">Статус</th>
                        <th className="p-4 font-semibold">Единицы</th>
                        <th className="p-4 font-semibold">Ответственный</th>
                        <th className="p-4 font-semibold">Обновлён</th>
                    </tr>
                </thead>
                <tbody>
                    {projects.length > 0 ? projects.map(project => (
                        <tr key={project.id} className="border-b border-black/5 hover:bg-gray-50">
                            <td className="p-4 font-medium">#{project.id}</td>
                            <td className="p-4">#{project.order_id}</td>
                            <td className="p-4">
                                <span className={`rounded px-2 py-1 text-sm ${getCrmProjectStatusClassName(project.status)}`}>
                                    {getCrmProjectStatusLabel(project.status)}
                                </span>
                            </td>
                            <td className="p-4">{project.units_count}</td>
                            <td className="p-4">
                                {project.assigned_to_user_id
                                    ? `Пользователь #${project.assigned_to_user_id}`
                                    : 'Не назначен'}
                            </td>
                            <td className="p-4">{formatCrmDate(project.updated_at)}</td>
                        </tr>
                    )) : (
                        <tr>
                            <td colSpan={6} className="p-6 text-center text-gray-500">
                                Производственных проектов пока нет
                            </td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    );
}
