# Shurl - Сервис для сокращения ссылок

## Установка

Необходимо наличие `docker compose` или `docker desktop`. Работоспособность проверялась как на win10 pro с 
docker desktop, так и на ubuntu24

1. Клонируем репозиторий
```bash
git clone https://github.com/timurlalala/shurl.git
```
2. Создаем файл `.env` в корне (по примеру, см `.env.example`), ставим свои переменные
3. В корне проекта выполняем
```bash
docker compose build
```
4. Запускаем сервис
```bash
docker compose up
```


## Особенности

- API построен на фреймворке FastAPI
- В качестве БД используется Postgres
- Миграции alembic, асинхронное взаимодействие с БД через sqlalchemy
- Весь код полностью асинхронный
- Реализовано кеширование запросов на переадресацию с использованием Redis
- Возможность сбора статистики (количество кликов и последний переход по ссылке), которая корректно работает с кешированием 
(тут вообще изящное, как мне кажется, решение, достойное отдельного раздела в этом файле)
- Аутентификация пользователей с помощью fatapi-users, через JWT/Bearer
- Все действия, связанные с удалением и изменением ссылок, требуют аутентификации. Причем удалять и изменять можно только
безхозные ссылки и собственные ссылки.
- Регулярная задача на удаление ссылок с истекшим сроком, реализованная с помощью celery beat
- Полная докеризация, причем контейнер с приложением билдится в два шага, что позволяет уменьшить его размер (это лучше заметно при использовании alpine)

### База данных

Сервис использует postgres для хранения ссылок и данных пользователей. 

#### Таблица `links`:

- `id`: Уникальный идентификатор ссылки (целое число, первичный ключ).
- `original_url`: Оригинальный URL-адрес (строка, обязательное поле, индексировано).
- `short_url`: Сокращенный URL-адрес (строка, обязательное поле, уникальное, индексировано).
- `created_by_uuid`: UUID пользователя, создавшего ссылку (`UUID`, может быть `null`, индексировано).
- `created_at`: Дата и время создания ссылки (`DateTime`, обязательное поле, текущее время по умолчанию).
- `updated_at`: Дата и время последнего обновления ссылки (`DateTime`, обязательное поле, текущее время по умолчанию).
- `expires_at`: Дата и время истечения срока действия ссылки (`DateTime`, может быть `null`, индексировано).
- `last_used`: Дата и время последнего использования ссылки (`DateTime`, может быть `null`).
- `clicks`: Количество кликов по ссылке (целое число, обязательное поле, значение по умолчанию `0`).

#### Таблица `users`:

- (Взята реализация из fastapi-users, ничего не изменено)

### Кеширование

Входящие запросы на переадресацию кешируются на 60 секунд. В качестве хранилища используется Redis. 

При кешировании возникает проблема: как нам обновлять статистики по ссылке, если код хэндлера не выполняется?
Решение:
- Кешируется обработка запроса не на уровне хэндлера (как это, например, реализовано в fastapi-cache2),
а внутри хендлера
- Для ключа, по которому хранится значение длинной ссылки собственно перехода по ссылке устанавливается время жизни
- Параллельно создается ключ для той же короткой ссылки, хранящий статистики. Время жизни у него не устанавливается
- При использовании кешированного значения мы также обновляем статистики в Redis
- При запуске сервиса выставляется lifetime задача, слушающая канал Redis на предмет протухших ключей. Когда возникает такое событие,
статистики по этому ключу выгружаются в БД и удаляются из Redis.
- Также статистики преждевременно выгружаются при запросе статистики, если они есть в кеше.

Такое решение позволило мне эффективно кешировать запросы, при этом корректно обновляя счетчик кликов и время последнего использования ссылки.

### Дополнительный функционал

- Возможность для аутентифицированных пользователей просмотреть все свои ссылки
- Возможность для аутентифицированных пользователей удалить все свои ссылки, которыми никто не пользовался в последние n часов/суток

Описани эндпоинтов ниже в документации

## Описание API

### 1. Создание короткой ссылки (`POST /links/shorten`)

Создает короткую ссылку для заданного URL.

**Параметры запроса:**

* `original_url` (обязательный, строка): Оригинальный URL для сокращения.
* `custom_alias` (необязательный, строка): Пользовательский псевдоним для короткой ссылки.
* `expires_at` (необязательный, datetime): Дата и время истечения срока действия ссылки.

**Пример запроса:**

```http
POST /links/shorten?original_url=https://www.example.com&custom_alias=myalias&expires_at=2024-12-31T23:59:59Z
```

**Пример ответа (201 Created):**

```json
{
  "short_url": "http://yourdomain.com/myalias",
  "short_code": "myalias"
}
```

**Пример ответа (409 Conflict) :**

```json
{
  "detail": "Custom alias already exists"
}
```

### 2. Поиск ссылок по оригинальному URL (`GET /links/search`)

Поиск коротких ссылок, связанных с заданным оригинальным URL.

**Параметры запроса:**

* `original_url` (обязательный, строка): Оригинальный URL для поиска.

**Пример запроса:**

```http
GET /links/search?original_url=https://www.example.com
```

**Пример ответа (200 OK):**

```json
[
  {
    "short_url": "http://yourdomain.com/short1",
    "created_at": "2023-10-27T10:00:00Z",
    "updated_at": "2023-10-27T10:00:00Z",
    "expires_at": "2024-12-31T23:59:59Z"
  },
  {
    "short_url": "http://yourdomain.com/short2",
    "created_at": "2023-10-27T10:00:00Z",
    "updated_at": "2023-10-27T10:00:00Z",
    "expires_at": null
  }
]
```

**Пример ответа (404 Not Found):**

```json
{
  "detail": "Original URL not found"
}
```

### 3. Перенаправление по короткой ссылке (`GET /links/{short_code}`)

Перенаправляет на оригинальный URL, связанный с заданной короткой ссылкой.

**Параметры пути:**

* `short_code` (обязательный, строка): Короткий код ссылки.

**Пример запроса:**

```http
GET /links/myalias
```

**Пример ответа (302 Found):**

Перенаправление на `https://www.example.com`.

**Пример ответа (404 Not Found):**

```json
{
  "detail": "Short code not found"
}
```

**Пример ответа (410 Gone):**

```json
{
  "detail": "Link has expired"
}
```

### 4. Удаление короткой ссылки (`DELETE /links/{short_code}`)

Удаляет короткую ссылку.

**Параметры пути:**

* `short_code` (обязательный, строка): Короткий код ссылки.

**Пример запроса:**

```http
DELETE /links/myalias
```

**Пример ответа (200 OK):**

```json
{
  "message": "Link deleted successfully"
}
```

**Пример ответа (404 Not Found):**

```json
{
  "detail": "Short code not found"
}
```

**Пример ответа (403 Forbidden):**

```json
{
  "detail": "You are not an owner of this link"
}
```

### 5. Обновление короткой ссылки (`PUT /links/{short_code}`)

Обновляет оригинальный URL, связанный с заданной короткой ссылкой.

**Параметры пути:**

* `short_code` (обязательный, строка): Короткий код ссылки.

**Параметры запроса:**

* `original_url` (обязательный, строка): Новый оригинальный URL.

**Пример запроса:**

```http
PUT /links/myalias?original_url=https://www.newexample.com
```

**Пример ответа (200 OK):**

```json
{
  "message": "Link updated successfully"
}
```

**Пример ответа (404 Not Found):**

```json
{
  "detail": "Short code not found"
}
```

**Пример ответа (403 Forbidden):**

```json
{
  "detail": "You are not an owner of this link"
}
```

### 6. Получение статистики ссылки (`GET /links/{short_code}/stats`)

Получает статистику по короткой ссылке.

**Параметры пути:**

* `short_code` (обязательный, строка): Короткий код ссылки.

**Пример запроса:**

```http
GET /links/myalias/stats
```

**Пример ответа (200 OK):**

```json
{
  "short_code": "myalias",
  "original_url": "https://www.example.com",
  "created_at": "2023-10-27T10:00:00Z",
  "updated_at": "2023-10-27T10:00:00Z",
  "expires_at": "2024-12-31T23:59:59Z",
  "clicks": 10,
  "last_used": "2023-10-28T10:00:00Z"
}
```

**Пример ответа (404 Not Found):**

```json
{
  "detail": "Short code not found"
}
```


## Дополнительные методы

### 1. Получение списка ссылок пользователя (`GET /account/mylinks`)

Возвращает список коротких ссылок, созданных текущим пользователем, и общую статистику по кликам.

**Пример запроса:**

```http
GET /account/mylinks
```

**Пример ответа (200 OK):**

```json
{
  "links": [
    {
      "short_url": "http://yourdomain.com/short1",
      "original_url": "https://www.example.com",
      "created_at": "2023-10-27T10:00:00Z",
      "updated_at": "2023-10-27T10:00:00Z",
      "expires_at": "2024-12-31T23:59:59Z",
      "clicks": 10,
      "last_used": "2023-10-28T10:00:00Z"
    },
    {
      "short_url": "http://yourdomain.com/short2",
      "original_url": "https://www.anotherexample.com",
      "created_at": "2023-10-28T10:00:00Z",
      "updated_at": "2023-10-28T10:00:00Z",
      "expires_at": null,
      "clicks": 5,
      "last_used": "2023-10-29T10:00:00Z"
    }
  ],
  "total_clicks": 15
}
```

**Пример ответа (404 Not Found):**

```json
{
  "detail": "Original URL not found"
}
```

### 2. Удаление неиспользуемых ссылок (`DELETE /account/remove_unused_links`)

Удаляет короткие ссылки, созданные текущим пользователем, которые не использовались в течение заданного периода времени.

**Параметры запроса:**

* `days` (необязательный, целое число, по умолчанию 0): Количество дней.
* `hours` (необязательный, целое число, по умолчанию 1, максимум 24): Количество часов.

**Пример запроса:**

```http
DELETE /account/remove_unused_links?days=7&hours=0
```

**Пример ответа (200 OK):**

```json
{
  "message": "Links deleted successfully"
}
```

**Пример ответа (500 Internal Server Error):**

```json
{
  "detail": "Some error message"
}
```

### Также реализованные встроенные в fastapi-users ручки регистрации, логина и логаута 

(я устал описывать все это...)