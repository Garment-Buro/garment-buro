import { actionLabels, type Project } from '@/lib/production/types';
import styles from './ProductionFlow.module.css';
export function ProductionJournal({ project }: { project: Project }) {
    return (
        <details className={styles.journal}>
            <summary>Журнал мешка · {project.events.length}</summary>
            {!project.events.length && <p>Действий пока нет.</p>}
            <ol>
                {project.events.map((event) => (
                    <li key={event.id}>
                        <strong>
                            {actionLabels[event.action] ?? event.action}
                            {event.unit_id ? ` · вещь #${event.unit_id}` : ''}
                        </strong>
                        <small>
                            {new Date(event.at).toLocaleString('ru-RU')} ·
                            сотрудник #{event.actor_id} · версия {event.version}
                        </small>
                        {event.note && <p>{event.note}</p>}
                    </li>
                ))}
            </ol>
        </details>
    );
}
