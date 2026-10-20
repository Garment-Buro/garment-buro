# Nginx: установка и приватность журналов

Выбрать один вариант vhost для фактической топологии. Файлы примеров сами
по себе не активированы; старый production snapshot не является конфигурацией
нового релиза. Изменения в репозитории не переключают публичный сервер.

Перед установкой **любого** vhost из этой папки или корневых `nginx*.conf`
установить общий формат журналов и server include. Для Nginx на хосте:

```sh
sudo install -d -m 0755 /etc/nginx/garment-buro
sudo install -m 0644 deploy/nginx/logging/http.conf /etc/nginx/conf.d/00-garment-logging.conf
sudo install -m 0644 deploy/nginx/logging/server.conf /etc/nginx/garment-buro/server-logging.conf
```

`http.conf` должен подключаться **один раз** внутри `http {}` до vhost.
Обычная конфигурация Nginx подключает `/etc/nginx/conf.d/*.conf` автоматически.
Если она изменена, проверить порядок `include`. Server include обязателен
в каждом server, включая HTTP redirect, ACME, bootstrap и терминал.
`nginx -t` должен пройти до reload. Отсутствующий include приводит к отказу
проверки, а не к тихому возврату небезопасного формата.

Для существующего Docker Nginx скрипт `deploy/scripts/enable-public-hosts.sh`
копирует оба файла в `garment-nginx-logging` рядом с legacy Compose и подключает
их через `docker-compose.legacy-nginx.override.yml`. Preflight получает те же
mounts. Резервная копия и откат включают vhost, override и оба logging-файла.
Скрипт также меняет сертификат/настройки widget: для одного исправления журналов
не запускать весь скрипт без проверки текущей серверной топологии.

## Что сохраняется

Access event — одна JSON-строка: UTC offset timestamp, случайный request ID
самого Nginx, конфигурационное имя server, разрешённый метод, постоянная
категория маршрута, HTTP status, байты, длительность, upstream status/time.
Произвольные методы заменяются на `OTHER`. Неизвестный маршрут — `page`.
В журнал не входят URL, ID пользователя/заказа, capability, query, Host клиента,
Referer, user agent, cookies, Authorization и тело запроса. Существующий
`/var/log/nginx/access.log` сохраняет штатную ротацию хоста; в официальном
Docker-образе этот путь направлен в stdout. Проверить ротацию Docker logs
в реальном развёртывании.

Обычный Nginx error log добавляет сырой request/upstream URL к ошибке и не
поддерживает редактирование полей через `log_format`. Поэтому HTTP server
направляет **свой** error log в `/dev/null`. Это осознанное ограничение:
подробная строка причины ошибки Nginx отсутствует; 4xx/5xx, upstream status и
время остаются в безопасном access event, причины backend — в его структурированных
событиях с шаблоном маршрута. Ошибки главного процесса, конфигурации и запуска
остаются в основном `error_log`. Не включать HTTP debug/дополнительные combined
журналы на production: они обходят эту границу.

## Проверка без сервера

```sh
python3 deploy/scripts/verify-nginx-privacy.py --nginx /usr/sbin/nginx
```

Нужны локальные Nginx с SSL/HTTP2 и OpenSSL. Скрипт использует временные каталоги,
синтетический сертификат, loopback-порты и собственный HTTP upstream; системный
Nginx, сертификаты и конфигурация не меняются. Меняются только адреса/порты,
пути сертификата, ACME root и журналов внутри тестовой копии vhost.

Все восемь конфигураций проходят настоящую загрузку Nginx и HTTP/HTTPS-запросы.
Проверяются приватные media и подписанные storage URL, image optimizer,
401/400, оборванный upstream 502, отсутствующий ACME-файл 404, 301 redirect,
слишком большой заголовок, поддельные Host/request ID и произвольный метод.
Небезопасный parent combined log специально включён, чтобы проверить override.
Два отрицательных контроля возвращают combined/error log и обязаны обнаружить
синтетический секрет. Все процессы и временные ключи удаляются в finally.

Локально 18 октября 2026: Nginx 1.30.6, **8 конфигураций / 129 access events**,
оба отрицательных контроля обнаружены. Восемь тестов исполняют installer с
поддельным Docker и проверяют установку/откат с прежними logging-файлами и без
них. CI gate добавлен в deployment job; его запуск на GitHub и публичный
Nginx/CDN пока не подтверждены. Локальный standalone/Chromium gate Метрики
прошёл с тестовым и сохранённым официальным SDK: DOM родителя и хранилища
недоступны, приватные маркеры не передаются. Это отдельная граница, см.
[analytics-privacy.md](../../frontend/docs/analytics-privacy.md). Настройки
серверного счётчика и публичные отчёты ещё не проверены.

Источники поведения: [access_log/log_format](https://nginx.org/en/docs/http/ngx_http_log_module.html),
[error_log](https://nginx.org/en/docs/ngx_core_module.html#error_log).
