import type { UploadedImage } from "./types.ts";
import { PROJECT_IMAGE_MAX_BYTES } from "../projects/images.ts";

export const CONSTRUCTOR_IMAGE_ACCEPT = "image/jpeg,image/png,image/webp";

/** Local input owns both browser resources until completion or editor cancellation. */
export function readUploadedImage(
  file: File,
  signal?: AbortSignal,
): Promise<UploadedImage> {
  return new Promise((resolve, reject) => {
    if (
      !CONSTRUCTOR_IMAGE_ACCEPT.split(",").includes(file.type) ||
      file.size > PROJECT_IMAGE_MAX_BYTES ||
      file.size === 0
    ) {
      reject(new RangeError("Выберите JPEG, PNG или WebP размером до 8 МБ."));
      return;
    }
    if (signal?.aborted) {
      reject(signal.reason);
      return;
    }
    const reader = new FileReader();
    let image: HTMLImageElement | null = null,
      settled = false,
      readComplete = false;
    const finish = (error: unknown, result?: UploadedImage) => {
      if (settled) return;
      settled = true;
      signal?.removeEventListener("abort", abort);
      reader.onload = null;
      reader.onerror = null;
      reader.onabort = null;
      if (image) {
        image.onload = null;
        image.onerror = null;
        if (error) image.src = "";
      }
      if (error) {
        if (!readComplete) reader.abort();
        reject(error);
      } else resolve(result!);
    };
    const abort = () =>
      finish(signal?.reason ?? new DOMException("Canceled", "AbortError"));
    signal?.addEventListener("abort", abort, { once: true });
    reader.onload = () => {
      if (settled) return;
      readComplete = true;
      const src = String(reader.result || "");
      image = new Image();
      image.onload = () => {
        if (settled) return;
        const width = image!.naturalWidth,
          height = image!.naturalHeight;
        if (
          width < 1 ||
          height < 1 ||
          width > 8192 ||
          height > 8192 ||
          width * height > 16_777_216
        ) {
          finish(
            new RangeError(
              "Изображение должно быть не больше 8192 пикселей по стороне и 16 мегапикселей.",
            ),
          );
          return;
        }
        finish(null, { src, width, height });
      };
      image.onerror = () =>
        finish(
          new Error("Не удалось прочитать изображение. Выберите другой файл."),
        );
      image.src = src;
    };
    reader.onerror = () =>
      finish(reader.error ?? new Error("Не удалось прочитать файл."));
    reader.onabort = () => finish(new DOMException("Canceled", "AbortError"));
    reader.readAsDataURL(file);
  });
}
