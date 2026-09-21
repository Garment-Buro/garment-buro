"use client";
import { useState } from "react";
import { type TicketSummary, useTicketRequest } from "./ticketApi";
import styles from "./Tickets.module.css";

export function CreateTicket({
  admin = false,
  orderId,
  onCreated,
}: {
  admin?: boolean;
  orderId?: number;
  onCreated: (id: number) => void;
}) {
  const request = useTicketRequest(admin ? "admin" : "customer");
  const [open, setOpen] = useState(false);
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [order, setOrder] = useState(orderId ? String(orderId) : "");
  const [customer, setCustomer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <section className={styles.panel}>
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)}>
        {open
          ? "Свернуть форму"
          : admin
            ? "Написать клиенту"
            : "Создать обращение"}
      </button>
      {open && (
        <form
          className={styles.form}
          onSubmit={async (event) => {
            event.preventDefault();
            if (busy) return;
            setBusy(true);
            setError("");
            try {
              const item = await request<TicketSummary>(
                admin ? "/production/admin/tickets" : "/support",
                {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    subject: subject.trim(),
                    message: message.trim(),
                    order_id: order ? Number(order) : null,
                    ...(admin
                      ? { customer_user_id: customer ? Number(customer) : null }
                      : {}),
                  }),
                },
              );
              setMessage("");
              setSubject("");
              setOpen(false);
              onCreated(item.id);
            } catch (failure) {
              setError(
                failure instanceof Error
                  ? failure.message
                  : "Не удалось создать тикет",
              );
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            Тема
            <input
              required
              maxLength={255}
              value={subject}
              disabled={busy}
              onChange={(event) => setSubject(event.target.value)}
            />
          </label>
          <label>
            Номер заказа {admin ? "" : "(необязательно)"}
            <input
              type="number"
              min={1}
              step={1}
              value={order}
              disabled={busy || !!orderId}
              onChange={(event) => setOrder(event.target.value)}
            />
          </label>
          {admin && !orderId && (
            <label>
              Номер клиента (если нет заказа)
              <input
                type="number"
                min={1}
                step={1}
                value={customer}
                disabled={busy}
                onChange={(event) => setCustomer(event.target.value)}
              />
            </label>
          )}
          <label>
            {admin ? "Сообщение клиенту" : "Что произошло"}
            <textarea
              required
              minLength={3}
              maxLength={5000}
              rows={4}
              value={message}
              disabled={busy}
              onChange={(event) => setMessage(event.target.value)}
            />
          </label>
          {admin && (
            <small>
              Сообщение появится в личном кабинете клиента, в разделе
              «Поддержка».
            </small>
          )}
          {error && (
            <p role="alert" className={styles.error}>
              {error}
            </p>
          )}
          <button
            type="submit"
            className={styles.primary}
            disabled={
              busy ||
              !subject.trim() ||
              message.trim().length < 3 ||
              (admin && !order && !customer)
            }
          >
            {busy ? "Создаём…" : "Создать тикет"}
          </button>
        </form>
      )}
    </section>
  );
}
