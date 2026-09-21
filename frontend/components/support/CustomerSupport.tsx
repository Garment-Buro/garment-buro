"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuthStore } from "@/store/authStore";
import { CreateTicket } from "./CreateTicket";
import { TicketConversation } from "./TicketConversation";
import {
  type TicketSummary,
  ticketStatuses,
  useTicketRequest,
} from "./ticketApi";
import styles from "./Tickets.module.css";

export function CustomerSupport() {
  const signedIn = useAuthStore((s) => s.isAuthenticated);
  const userId = useAuthStore((s) => s.user?.id);
  if (!signedIn)
    return (
      <section className={styles.panel}>
        <h2>Поддержка</h2>
        <p>Войдите, чтобы написать нам и увидеть ответы по своим обращениям.</p>
        <Link href="/login">Войти</Link>
      </section>
    );
  return <CustomerTickets key={userId} />;
}

function CustomerTickets() {
  const request = useTicketRequest("customer");
  const [page, setPage] = useState<{
    items: TicketSummary[];
    next_offset: number | null;
  } | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    void request<{ items: TicketSummary[]; next_offset: number | null }>(
      `/support?offset=${offset}`,
      { cache: "no-store", signal: controller.signal },
    )
      .then((value) => {
        if (!controller.signal.aborted) {
          setPage(value);
          setError("");
        }
      })
      .catch((failure) => {
        if (!controller.signal.aborted)
          setError(
            failure instanceof Error
              ? failure.message
              : "Не удалось загрузить обращения",
          );
      });
    return () => controller.abort();
  }, [request, offset, revision]);
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") setRevision((n) => n + 1);
    }, 30_000);
    return () => window.clearInterval(timer);
  }, []);
  if (selected !== null)
    return (
      <section className={styles.panel}>
        <button
          type="button"
          onClick={() => {
            setSelected(null);
            setRevision((n) => n + 1);
          }}
        >
          Все обращения
        </button>
        <TicketConversation key={selected} id={selected} mode="customer" />
      </section>
    );
  return (
    <section className={styles.panel}>
      <div className={styles.heading}>
        <h2>Поддержка</h2>
        <button type="button" onClick={() => setRevision((n) => n + 1)}>
          Обновить
        </button>
      </div>
      <p>
        Вопросы по заказу, доставке и работе сайта. Вся переписка сохранится
        здесь.
      </p>
      <CreateTicket
        onCreated={(id) => {
          setSelected(id);
          setRevision((n) => n + 1);
        }}
      />
      {error && (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      )}
      {!page && !error && <p role="status">Загружаем обращения…</p>}
      {page && !page.items.length && (
        <p>Обращений пока нет. Создайте тикет, чтобы связаться с поддержкой.</p>
      )}
      <ul className={styles.list}>
        {page?.items.map((item) => (
          <li key={item.id}>
            <button type="button" onClick={() => setSelected(item.id)}>
              <strong>
                №{item.id} · {item.subject}
              </strong>
              <span>
                {ticketStatuses[item.status]}
                {item.order_id && ` · Заказ №${item.order_id}`}
              </span>
              <small>
                Обновлено {new Date(item.updated_at).toLocaleString("ru-RU")}
              </small>
            </button>
          </li>
        ))}
      </ul>
      <div className={styles.heading}>
        {offset > 0 && (
          <button
            type="button"
            onClick={() => setOffset(Math.max(0, offset - 30))}
          >
            Назад
          </button>
        )}
        {page?.next_offset !== null && page?.next_offset !== undefined && (
          <button type="button" onClick={() => setOffset(page.next_offset!)}>
            Далее
          </button>
        )}
      </div>
    </section>
  );
}
