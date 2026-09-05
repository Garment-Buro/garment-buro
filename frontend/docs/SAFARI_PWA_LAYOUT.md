# Safari 26 / PWA: карта настроек интерфейса

Эти правила относятся к standalone PWA и Safari с динамическим viewport. Проверять их только в обычном desktop-браузере недостаточно: там нет реальных `safe-area-inset-*` и поведения нижней панели iOS.

## Корзина

- Нижний отступ задаётся в `app/globals.css` переменной `--cart-action-bar-bottom`.
- Для `pwa`, `safari26`, `safari18` и `display-mode: standalone` значение равно `20px`.
- `components/cart/CartActionBar.tsx` использует эту переменную в `bottom` оболочки и не переопределяет её при раскрытии.
- Геометрия раскрытой панели настраивается константами `CART_ACTION_EXPANDED_*` в `lib/cart/constants.ts`: базовая высота `510`, максимум `560`, запас до верха viewport `80`, длительность раскрытия `560ms`.
- Для плавности Safari при раскрытии анимируется только высота продуктовой панели. Нельзя возвращать одновременно две анимируемые поверхности с `backdrop-filter`: это давало заметный лаг в PWA.
- Первый видимый кадр корзины должен иметь `opacity: 1`; появление делается через `transform`, чтобы не возвращался белый flash.

## Конструктор

- Нижний отступ панели задаётся в `app/globals.css` внутри `.constructorViewport` переменной `--constructor-panel-bottom: 10px`.
- `hooks/constructor/useConstructorPageController.ts` использует эту переменную для самой панели. Значение `panelBottomForCanvas` должно оставаться синхронным с ней, чтобы расчёт свободной области холста был правильным.
- Фон под панелью — это продолжение `/constructor_bg.webp`. Он назначен для `.constructorViewport`, а также для `html`, `body` и `.appPageShell` на странице конструктора.
- Отдельного нижнего Safari-bar, белого псевдоэлемента или одноцветной подложки здесь быть не должно.
- Высота конструктора строится на `100dvh`; `visualViewport.height` не используется для постоянной геометрии страницы. Он нужен только для специальных сценариев экранной клавиатуры, если такие появятся отдельно.

## Overlay инструкции и popup

- Общая геометрия находится в `.viewportOverlayRoot` в `app/globals.css`.
- В PWA/Safari overlay продлевается вниз на `env(safe-area-inset-bottom)`, поэтому затемняет и область под нижней системной панелью.
- `hooks/constructor/useConstructorPageEnvironment.ts` выставляет `data-constructor-overlay-active="true"` на `html` и `body`, а затем повторно применяет состояние сразу, через два `requestAnimationFrame` и через `120ms`. Это защищает от запоздалой перерисовки chrome в Safari 26.
- Активный overlay должен иметь z-index выше `.constructorSafariTop`; верхняя safe-area при этом остаётся белой под цвет header, а затемнение рисует сам overlay.
- Снятие overlay обязано восстановить `theme-color`, dataset и прокрутку страницы.

## Верхняя safe-area и цвета страниц

- `providers/AppEnvironmentProvider.tsx` — единая точка применения page chrome к `html`, `body` и `theme-color`; provider подключён в корневом `app/layout.tsx`.
- `lib/browser/utils/detectBrowserSurface.ts` определяет `pwa`, `safari26`, `safari18` и `otherbrowser`.
- `lib/browser/utils/pageChrome.ts` сопоставляет маршрут с цветами и CSS-переменными страницы.
- `hooks/browser/useBrowserSurface.ts` подписывается на смену standalone display mode без дублирующих `useEffect` и локального состояния.
- Компоненты, которым нужно прочитать текущую среду, используют `useAppEnvironment()`; повторно разбирать `navigator.userAgent` внутри компонентов нельзя.
- Слои `.appSafariTopBar` и `.constructorSafariTop`, их высота и z-index находятся в `app/globals.css`.
- Для каталога и товара верх использует тот же градиент, что и шапка. Конструктор в обычном состоянии использует белый верх.
- Не добавлять глобальную нижнюю safe-area подложку: нижний край должен краситься настоящим фоном конкретной страницы.

## Заставка `logo_anim`

- Состояние и media lifecycle находятся в `hooks/browser/useSplashController.ts`, а разметка — в `components/shared/SplashScreen.tsx`.
- Видео всегда получает `muted`, `autoplay`, `playsinline` и `webkit-playsinline`; воспроизведение повторно запрашивается после монтирования, `pageshow` и возврата вкладки в активное состояние.
- Видео не скрывается через `opacity: 0` до `playing`: скрытая поверхность может не запускаться в WebKit. Используется само `logo_anim`, без статичной фотографии или poster.
- Текст раскрывается после первого кадра, успешного запуска или ошибки. Через 3,5 секунды ожидания показываются повторный запуск и переход на сайт; при запрете autoplay кнопка вызывает `play()` непосредственно в пользовательском жесте. Ошибка не оставляет пустую заставку.
- Настройка muted inline autoplay и классификация отказов находятся в `lib/browser/utils/splashPlayback.ts` и проверяются поведенческими тестами.
- WebKit media controls дополнительно скрыты только для `.appSplashScreen video` в `app/globals.css`.
- Заставка монтируется после клиентской проверки текущего app-run; отдельного bootstrap-script и dataset `data-p2o-splash` в `app/layout.tsx` нет.

## Проверка перед выкладкой

```bash
rtk node --test components/**/*.test.mjs
rtk npm run build
```

После выкладки нужно отдельно проверить установленную PWA на реальном iPhone/Safari 26: холодный запуск, раскрытие/закрытие корзины, инструкцию конструктора, popup выхода и возврат приложения из background.
