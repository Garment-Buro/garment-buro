"use client";

import { useCallback } from "react";
import { requestJson } from "@/lib/api/http";
import { useAuthStore } from "@/store/authStore";
import { useProductionAuthStore } from "@/store/productionAuthStore";

export type TicketMode = "customer" | "admin";
export type TicketSummary = {
  id: number;
  kind: "support" | "production_problem";
  subject: string;
  status: string;
  order_id: number | null;
  version: number;
  created_at: string;
  updated_at: string;
};
export type TicketDetail = TicketSummary & {
  message: string;
  initial_author: string;
  next_after: number | null;
  messages: {
    id: number;
    body: string;
    author_role: string;
    visibility: string;
    created_at: string;
  }[];
  routing_targets?: { value: string; label: string }[];
  order?: {
    id: number;
    user_id: number | null;
    status: string;
    customer: string;
    email: string | null;
    phone: string | null;
    items: { title: string; size: string; color: string; quantity: number }[];
  } | null;
};
export const ticketStatuses: Record<string, string> = {
  new: "Новое",
  in_progress: "В работе",
  resolved: "Решено",
  closed: "Закрыто",
};

export function useTicketRequest(mode: TicketMode) {
  const customerRun = useAuthStore((s) => s.runAuthenticated);
  const productionRun = useProductionAuthStore((s) => s.runAuthenticated);
  return useCallback(
    <T>(path: string, init?: RequestInit): Promise<T> => {
      if (mode === "customer")
        return customerRun((token) =>
          requestJson<T>(path, {
            ...init,
            headers: { ...init?.headers, Authorization: `Bearer ${token}` },
          }),
        );
      return productionRun(() => requestJson<T>(path, init));
    },
    [mode, customerRun, productionRun],
  );
}
