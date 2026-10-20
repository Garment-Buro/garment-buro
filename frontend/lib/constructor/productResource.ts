import type { ConstructorProduct } from "./product.ts";

type Snapshot = {
  key: string | null;
  product: ConstructorProduct | null;
  status: "idle" | "loading" | "ready" | "error";
  error: unknown;
};
type Transport = (id: number, signal: AbortSignal) => Promise<ConstructorProduct>;

/** Only the requested product may become a usable constructor model. */
export class ConstructorProductResource {
  private snapshot: Snapshot = {
    key: null,
    product: null,
    status: "idle",
    error: null,
  };
  private controller: AbortController | null = null;
  private listeners = new Set<() => void>();

  getSnapshot = () => this.snapshot;
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  private publish(snapshot: Snapshot) {
    this.snapshot = snapshot;
    this.listeners.forEach((listener) => listener());
  }
  async load(key: string | null, transport: Transport) {
    this.dispose();
    if (key === null) {
      this.publish({ key, product: null, status: "idle", error: null });
      return;
    }
    const id = Number(key);
    if (
      !/^[1-9]\d*$/.test(key) ||
      !Number.isSafeInteger(id) ||
      id > 2147483647
    ) {
      this.publish({
        key,
        product: null,
        status: "error",
        error: new RangeError("Некорректный идентификатор модели."),
      });
      return;
    }
    const controller = new AbortController();
    this.controller = controller;
    this.publish({ key, product: null, status: "loading", error: null });
    try {
      const product = await transport(id, controller.signal);
      if (controller.signal.aborted) return;
      if (product.id !== id)
        throw new Error("Ответ каталога содержит другую модель.");
      this.publish({ key, product, status: "ready", error: null });
    } catch (error) {
      if (!controller.signal.aborted)
        this.publish({ key, product: null, status: "error", error });
    }
  }
  dispose() {
    this.controller?.abort();
    this.controller = null;
  }
}
