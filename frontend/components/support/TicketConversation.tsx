"use client";

import { useCallback, useEffect, useState } from "react";
import {
  type TicketDetail,
  type TicketMode,
  ticketStatuses,
  useTicketRequest,
} from "./ticketApi";
import styles from "./Tickets.module.css";

const authors: Record<string, string> = {
  customer: "Клиент",
  admin: "Поддержка",
  employee: "Сотрудник",
  system: "Событие",
};
const date = (value: string) => new Date(value).toLocaleString("ru-RU");

export function TicketConversation({
  id,
  mode,
  projectId,
  onChanged,
}: {
  id: number;
  mode: TicketMode;
  projectId?: number;
  onChanged?: () => void;
}) {
  const request = useTicketRequest(mode);
  const path =
    mode === "admin"
      ? `/production/admin/tickets/${id}`
      : mode === "employee"
        ? `/production/projects/${projectId}/tickets/${id}`
        : `/support/${id}`;
  const [data, setData] = useState<TicketDetail | null>(null);
  const [message, setMessage] = useState("");
  const [visibility, setVisibility] = useState("public");
  const [target, setTarget] = useState("resume");
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision((n) => n + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    void request<TicketDetail>(path, {
      cache: "no-store",
      signal: controller.signal,
    })
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((failure) => {
        if (!controller.signal.aborted)
          setError(
            failure instanceof Error
              ? failure.message
              : "Не удалось загрузить тикет",
          );
      });
    return () => controller.abort();
  }, [request, path, revision]);
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (
        document.visibilityState === "visible" &&
        !busy &&
        !message &&
        !comment
      )
        reload();
    }, 30_000);
    return () => window.clearInterval(timer);
  }, [reload, busy, message, comment]);

  async function submit(action: "messages" | "route") {
    if (!data || busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await request(`${path}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          action === "messages"
            ? {
                expected_version: data.version,
                message: message.trim(),
                visibility,
              }
            : {
                expected_version: data.version,
                target,
                comment: comment.trim(),
              },
        ),
      });
      if (action === "messages") setMessage("");
      else setComment("");
      setNotice(
        action === "messages"
          ? "Сообщение отправлено"
          : "Решение сохранено, изделие передано",
      );
      reload();
      onChanged?.();
    } catch (failure) {
      setError(
        failure instanceof Error ? failure.message : "Не удалось сохранить",
      );
      reload();
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={styles.panel} aria-label={`Переписка по тикету ${id}`}>
      <div className={styles.heading}>
        <h3>
          Тикет №{id}
          {data && ` · ${ticketStatuses[data.status]}`}
        </h3>
        <button type="button" disabled={busy} onClick={reload}>
          Обновить
        </button>
      </div>
      {!data && !error && <p role="status">Загружаем переписку…</p>}
      {data && (
        <>
          {mode === "admin" && data.order && (
            <aside className={styles.context}>
              <strong>
                Заказ №{data.order.id} ·{" "}
                {data.order.customer || "Имя не указано"}
              </strong>
              <p>
                {[data.order.email, data.order.phone]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
              {data.order.items.map((item, i) => (
                <p key={i}>
                  {item.title} · {item.size} · {item.color} · {item.quantity}{" "}
                  шт.
                </p>
              ))}
            </aside>
          )}
          <h4>{data.subject}</h4>
          <ol className={styles.messages} aria-label="История сообщений">
            <li>
              <small>
                {authors[data.initial_author]} · {date(data.created_at)}
              </small>
              <p>{data.message}</p>
            </li>
            {data.messages.map((entry) => (
              <li
                key={entry.id}
                data-internal={entry.visibility === "internal"}
              >
                <small>
                  {authors[entry.author_role]} · {date(entry.created_at)}
                  {entry.visibility === "internal" && " · Внутренняя заметка"}
                </small>
                <p>{entry.body}</p>
              </li>
            ))}
          </ol>
          {data.next_after !== null && (
            <button
              type="button"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  const next = await request<TicketDetail>(
                    `${path}?after=${data.next_after}`,
                    { cache: "no-store" },
                  );
                  setData({
                    ...next,
                    messages: [...data.messages, ...next.messages],
                  });
                } catch (failure) {
                  setError(
                    failure instanceof Error
                      ? failure.message
                      : "Не удалось загрузить сообщения",
                  );
                } finally {
                  setBusy(false);
                }
              }}
            >
              Следующие сообщения
            </button>
          )}
          <form
            className={styles.form}
            onSubmit={(event) => {
              event.preventDefault();
              void submit("messages");
            }}
          >
            {mode === "admin" && (
              <label>
                Видимость сообщения
                <select
                  disabled={busy}
                  value={visibility}
                  onChange={(event) => setVisibility(event.target.value)}
                >
                  <option value="public">Ответ участнику тикета</option>
                  <option value="internal">Только администраторам</option>
                </select>
              </label>
            )}
            <label>
              {visibility === "internal" ? "Внутренняя заметка" : "Сообщение"}
              <textarea
                required
                minLength={1}
                maxLength={5000}
                rows={3}
                disabled={busy}
                value={message}
                onChange={(event) => setMessage(event.target.value)}
              />
            </label>
            {mode === "customer" &&
              ["closed", "resolved"].includes(data.status) && (
                <small>Новое сообщение снова откроет обращение.</small>
              )}
            <button
              className={styles.primary}
              disabled={busy || !message.trim()}
              type="submit"
            >
              {busy ? "Сохраняем…" : "Отправить сообщение"}
            </button>
          </form>
          {mode === "admin" && !!data.routing_targets?.length && (
            <form
              className={styles.form}
              onSubmit={(event) => {
                event.preventDefault();
                void submit("route");
              }}
            >
              <h4>Решение по производству</h4>
              <label>
                Куда передать изделие
                <select
                  value={target}
                  disabled={busy}
                  onChange={(event) => setTarget(event.target.value)}
                >
                  {data.routing_targets.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Комментарий для сотрудников
                <textarea
                  required
                  minLength={3}
                  maxLength={1000}
                  rows={3}
                  disabled={busy}
                  value={comment}
                  onChange={(event) => setComment(event.target.value)}
                />
              </label>
              <small>
                Решение закроет проблему и возобновит работу этого изделия.
                Сотрудники увидят комментарий в тикете и журнале.
              </small>
              <button
                className={styles.primary}
                type="submit"
                disabled={busy || comment.trim().length < 3}
              >
                Передать изделие и решить тикет
              </button>
            </form>
          )}
        </>
      )}
      {notice && <p role="status">{notice}</p>}
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
