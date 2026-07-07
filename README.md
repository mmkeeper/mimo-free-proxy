# MiMo Free Proxy

Локальный HTTP-прокси-сервер для доступа к бесплатному API Xiaomi MiMo через стандартный OpenAI-совместимый интерфейс.

## Возможности

- Проксирование запросов к бесплатному API MiMo
- Автоматическое обновление JWT-токена
- Поддержка SOCKS5-прокси
- Аутентификация по API-ключу
- Streaming-ответов (SSE)
- Совместимость с OpenAI API (`/v1/chat/completions`, `/v1/models`)

## Установка

```bash
pip install -r requirements.txt
```

## Настройка

Отредактируйте параметры в начале `server.py`:

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `LISTEN_HOST` | Хост для прослушивания | `127.0.0.1` |
| `LISTEN_PORT` | Порт | `8788` |
| `LOCAL_KEY` | API-ключ для доступа к прокси | `sk-mimo-keeper-unique-key` |
| `SOCKS5_HOST` | SOCKS5-прокси хост | `127.0.0.1` |
| `SOCKS5_PORT` | SOCKS5-прокси порт | `9150` |
| `SOCKS5_USERNAME` | Логин SOCKS5 (если нужен) | `None` |
| `SOCKS5_PASSWORD` | Пароль SOCKS5 (если нужен) | `None` |

## Запуск

```bash
python server.py
```

Сервер будет доступен по адресу `http://127.0.0.1:8788`.

## Использование

### Через curl

```bash
curl http://127.0.0.1:8788/v1/chat/completions \
  -H "Authorization: Bearer sk-mimo-keeper-unique-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mimo-auto",
    "messages": [{"role": "user", "content": "Привет!"}]
  }'
```

### Через Python (openai библиотека)

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8788/v1",
    api_key="sk-mimo-keeper-unique-key"
)

response = client.chat.completions.create(
    model="mimo-auto",
    messages=[{"role": "user", "content": "Привет!"}]
)
print(response.choices[0].message.content)
```

### Endpoint'ы

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/v1/models` | Список доступных моделей |
| GET | `/health` | Проверка работоспособности |
| POST | `/v1/chat/completions` | Отправка чат-запроса |

## Логика работы

1. Генерация или чтение fingerprint-клиента
2. Bootstrap-запрос для получения JWT
3. При каждом запросе — проксирование к upstream API
4. Автоматическое обновление JWT при истечении или ошибке 401/403
