# Зависимости frontend — 18 октября 2026

Дополнение19 октября: удалён неиспользуемый Phantom UI, его общий CSS/bootstrap
и шесть зависимостей Lit. Другие версии и integrity в lock сохранены.
Каталог:13→12 JS-файлов,689486→660746 байт после декомпрессии и
215348→205263 байт завершённых CDP-передач. Это отдельное сравнение production
сборок с настоящим локальным API, без нового замера LCP.621 frontend tests,
lint/build и оба browser gate прошли. Данные audit ниже относятся к18 октября,
новый npm audit в этом этапе не запускался.
[Проверки удаления](../../docs/superpowers/plans/2026-10-19-unused-skeleton-runtime.md).

До обновления npm audit сообщал 11 затронутых пакетов: 1 critical, 9 high,
1 moderate. Это число пакетов в графе зависимостей, не число независимых атак.

Next и eslint-config-next обновлены с16.3.0 до16.3.8 и зафиксированы точно.
Обновление осталось в той же minor-ветке. В lock также обновлены совместимые
sharp, source-map-js, js-yaml, brace-expansion и @humanfs/node. `npm audit fix
--force` и подмена major-версий через overrides не применялись.

После обновления `npm audit --omit=dev --json` сообщает **0** advisories.
Полный audit сообщает **5 high** из одной цепочки dev-only:

```text
eslint-config-next@16.3.8
  @next/eslint-plugin-next@16.3.8
    fast-glob@3.3.1
      micromatch@4.0.8
        braces@3.0.3
```

Для GHSA-vfj7-8cjw-p6xm пока нет исправленной версии braces. Переполнение
стека возникает на глубоко вложенном brace pattern. Здесь цепочка используется
ESLint при работе с файлами репозитория; она не должна принимать шаблоны
пользователей HTTP. Остаток не скрыт исключением audit и требует повторной
проверки при обновлении lint-инструментов. Предложенный npm downgrade
eslint-config-next до14.2.35 не согласуется с Next16 и не применён.

В CI добавлен `npm audit --omit=dev --audit-level=high`. Он проверяет известные
на момент запуска production advisories; нулевой результат не доказывает
отсутствие ещё не опубликованных уязвимостей. Полный `npm audit` остаётся
отдельной проверкой инструментов разработки. Docker/Actions и публичный
runtime ещё не подтверждены; это изменение локальной кодовой базы.

Проверено после обновления:535 tests, lint и production build/TypeScript.
В настоящем standalone найдены Next16.3.8 и sharp0.35.5; перечисленной dev-цепочки
и Playwright там нет. Оба analytics Chromium gate прошли повторно. Приватный
image optimizer возвращает400/no-store без чтения upstream; публичный PNG
оптимизируется с200, encoded private aliases отклоняются. Настоящая функция
image boundary из container gate также прошла с native standalone.

Источники исправлений: [Next16.3.8](https://github.com/vercel/next.js/releases/tag/v16.3.8),
[AVIF image optimization](https://github.com/vercel/next.js/security/advisories/GHSA-2xp9-vwfh-vxw4),
[оставшийся braces advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm).
