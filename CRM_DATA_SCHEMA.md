# Garment Buro: данные сайта для интеграции CRM

Документ описывает, какие данные сейчас хранит Garment Buro, где они лежат и в каком формате их лучше читать или передавать в CRM.

## 1. Основные сущности

Сейчас в базе есть 4 основные таблицы:

```text
products
product_variants
orders
users
```

Дополнительно есть JSON-настройки сайта:

```text
backend/uploads/settings.json
backend/uploads/variant_options.json
```

`variant_options.json` может отсутствовать. Если файла нет, backend возвращает значения по умолчанию.

## 2. Товары: `products`

Таблица хранит карточки товаров, цены, остатки, габариты и медиа.

| Поле | Тип | Что хранит |
| --- | --- | --- |
| `id` | integer | ID товара, главный идентификатор товара |
| `title` | string | Название товара |
| `price` | float | Текущая цена товара |
| `old_price` | float/null | Старая цена, если нужна зачеркнутая цена |
| `video_src` | string/null | Старое поле видео, сейчас почти не используется |
| `image_left` | string/null | Старое поле изображения для мобильных карточек |
| `image_right` | string/null | Старое поле изображения для мобильных карточек |
| `description` | string/null | Описание товара |
| `composition` | string/null | Состав |
| `model_info` | string/null | Информация о модели |
| `sizes` | string/null | Размеры через запятую, например `S,M,L,XL` |
| `colors` | string/null | Цвета через запятую |
| `gallery_images` | string/null | Старое поле галереи, URL через запятую |
| `is_active` | boolean | Показывать ли товар на сайте |
| `type` | string | Тип товара. Сейчас для обычных товаров используется `normal` |
| `weight` | float | Вес для доставки СДЭК |
| `height` | float | Высота упаковки/товара для доставки, см |
| `width` | float | Ширина упаковки/товара для доставки, см |
| `length` | float | Длина упаковки/товара для доставки, см |
| `stock_quantity` | integer | Общий остаток товара |
| `size_chart_img_1` | string/null | Изображение схемы изделия в размерной сетке |
| `size_chart_img_2` | string/null | Изображение размерной таблицы |
| `desktop_video` | string/null | Видео для десктопной версии |
| `desktop_video_poster` | string/null | Постер видео для десктопа |
| `desktop_card_images` | string/null | Фото для корзины/карточки, URL через запятую |
| `desktop_slider_images` | string/null | Фото слайдера товара на десктопе, URL через запятую |
| `mobile_card_image` | string/null | Фото для мобильного блока на лендинге |
| `mobile_video_poster` | string/null | Постер видео для мобильной версии |
| `mobile_slider_images` | string/null | Фото слайдера в каталоге на мобильной версии, URL через запятую |
| `mobile_product_slider_images` | string/null | Фото слайдера на странице товара на мобильной версии, URL через запятую |
| `mobile_size_chart_first` | string/null | Фото справа от размеров на мобильной странице товара |

### Важные правила для CRM по товарам

- Главный ID товара: `products.id`.
- Поля с несколькими изображениями хранятся строкой через запятую.
- Для конструктора сейчас важны первые две картинки из `desktop_slider_images`: первая считается видом спереди, вторая видом сзади.
- Для страницы товара на мобильной версии используются мобильные медиа-поля, но конструктор должен опираться на `desktop_slider_images`, потому что там хранится правильная пара “перед/зад”.
- `weight`, `height`, `width`, `length` используются для расчета доставки.
- Остатки есть на уровне товара (`stock_quantity`) и на уровне варианта (`product_variants.stock_quantity`).

Пример значения поля с несколькими фото:

```text
/uploads/front.png,/uploads/back.png,/uploads/detail.png
```

## 4. Варианты товара: `product_variants`

Таблица хранит размеры, цвета и остатки по конкретным вариантам товара.

| Поле | Тип | Что хранит |
| --- | --- | --- |
| `id` | integer | ID варианта |
| `product_id` | integer | ID товара из `products.id` |
| `size` | string/null | Размер, например `M` |
| `color` | string/null | Название цвета, например `Черный` |
| `color_hex` | string/null | HEX-цвет, например `#1A1A1A` |
| `stock_quantity` | integer | Остаток конкретного варианта |
| `preview_image` | string/null | Превью варианта |
| `images` | string/null | Дополнительные фото варианта, URL через запятую |

### Правила для CRM по вариантам

- Один товар может иметь несколько вариантов.
- Вариант связывается с товаром через `product_id`.
- При создании или обновлении товара через текущий API варианты передаются внутри payload товара.
- При обновлении товара backend удаляет старые варианты товара и создает новые из переданного списка.

## 5. Заказы: `orders`

Таблица хранит данные покупателя, доставку, оплату, состав корзины и статусы интеграций.

| Поле | Тип | Что хранит |
| --- | --- | --- |
| `id` | integer | ID заказа |
| `email` | string/null | Email покупателя |
| `phone` | string/null | Телефон покупателя |
| `first_name` | string/null | Имя |
| `last_name` | string/null | Фамилия |
| `patronymic` | string/null | Отчество |
| `delivery_city` | string/null | Город доставки |
| `delivery_method` | string/null | Способ доставки |
| `delivery_address` | string/null | Адрес доставки или адрес ПВЗ |
| `payment_method` | string/null | Способ оплаты |
| `cart_items` | string/null | JSON-строка с товарами заказа |
| `total_price` | float/null | Итоговая сумма заказа |
| `status` | string | Статус заказа, по умолчанию `new` |
| `cdek_uuid` | string/null | UUID заказа в СДЭК |
| `cdek_point_code` | string/null | Код ПВЗ СДЭК |
| `delivery_price` | float/null | Стоимость доставки |
| `payment_id` | string/null | ID платежа YooKassa |
| `payment_status` | string | Статус оплаты, по умолчанию `pending` |
| `created_at` | datetime | Дата создания заказа |
| `cdek_number` | string/null | Номер заказа СДЭК |
| `cdek_status` | string/null | Статус заказа СДЭК |

### Формат `cart_items`

`cart_items` хранится как JSON-строка. Пример:

```json
[
  {
    "product_id": 4,
    "title": "худи на молнии с мехом \"Dark Прямой\"",
    "price": 5980,
    "image": "/uploads/VeXb_KTD5Hc.png",
    "size": "M",
    "color": "Черный",
    "quantity": 1,
    "id": "4_M_Черный"
  }
]
```

Если товар добавлен из конструктора, внутри item может быть дополнительный объект `customization` с выбранными украшениями, размерами, ценами и стороной изделия. CRM должна сохранять его как часть состава заказа, даже если пока не использует все поля.

### Статусы

Текущие значения, которые ожидает backend:

```text
orders.status: new, processing, shipped, completed, cancelled
orders.payment_status: pending, paid, failed
```

Фактические значения в базе могут расширяться, если CRM или админка добавит новые статусы.

### Доставка и оплата

- Если `delivery_method` содержит `cdek` или `сдэк`, backend может регистрировать заказ в СДЭК.
- Для оплаты картой или QR используется YooKassa.
- При успешной оплате webhook переводит `payment_status` в `paid`, а `status` в `processing`.

## 6. Пользователи: `users`

Таблица хранит аккаунты покупателей и данные профиля.

| Поле | Тип | Что хранит |
| --- | --- | --- |
| `id` | integer | ID пользователя |
| `email` | string/null | Email, уникальный |
| `telegram_id` | string/null | Telegram ID, уникальный |
| `first_name` | string/null | Имя |
| `last_name` | string/null | Фамилия |
| `username` | string/null | Username |
| `created_at` | datetime | Дата создания пользователя |
| `phone` | string/null | Телефон |
| `gender` | string/null | Пол |
| `birth_date` | string/null | Дата рождения |
| `height` | float/null | Рост |
| `weight` | float/null | Вес |
| `otp_code` | string/null | Одноразовый код входа |
| `otp_expiry` | datetime/null | Срок действия одноразового кода |

### Важно по персональным данным

`users` и `orders` содержат персональные данные: ФИО, телефон, email, адрес доставки. CRM должна хранить и передавать эти данные только по защищенному каналу и не выводить их в публичные логи.

## 7. Настройки сайта: `settings.json`

Файл:

```text
backend/uploads/settings.json
```

Текущая структура:

```json
{
  "logo_video_url": "/logo_anim.mp4",
  "hero_products": [1, 2, 3, 4],
  "showroom1_products": [2, 3, 4],
  "showroom2_products": [1, 2, 3, 4],
  "links": {}
}
```

Что это значит:

| Поле | Что хранит |
| --- | --- |
| `logo_video_url` | URL видео логотипа |
| `hero_products` | ID товаров для главного блока |
| `showroom1_products` | ID товаров для первого блока шоурума |
| `showroom2_products` | ID товаров для второго блока шоурума |
| `links` | Дополнительные ссылки сайта |

## 8. Опции размеров и цветов: `variant_options.json`

Файл:

```text
backend/uploads/variant_options.json
```

Если файла нет, backend возвращает дефолт:

```json
{
  "colors": [
    { "label": "Черный", "hex": "#1A1A1A" },
    { "label": "Белый", "hex": "#FFFFFF" }
  ],
  "sizes": ["XS", "S", "M", "L", "XL", "XXL"]
}
```

CRM может использовать эти данные как справочник для формы товара.
