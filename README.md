# MiMo Free Proxy

Локальный HTTP-прокси-сервер для доступа к бесплатному API Xiaomi MiMo через стандартный OpenAI-совместимый интерфейс.

## Related projects

All three projects share the same CLI interface (`--port`, `--host`, `--proxy`, `--api-key`) and work together through [llama-swap](https://github.com/mmkeeper/llama-swap):

| Project | Port | What |
|---------|------|------|
| [opencode-free-proxy](https://github.com/mmkeeper/opencode-free-proxy) | 6446 | OpenCode free models |
| [deepseek-free-api](https://github.com/mmkeeper/deepseek-free-api) | 18632 | DeepSeek free API |
| [mimo-free-proxy](https://github.com/mmkeeper/mimo-free-proxy) | 8788 | Xiaomi MiMo free API (this) |

## Возможности

- Проксирование запросов к бесплатному API MiMo
- Автоматическое обновление JWT-токена
- Поддержка SOCKS5-прокси (⚠️ upstream блокирует некоторые proxy IP)
- Аутентификация по API-ключу
- Streaming-ответов (SSE)
- Совместимость с OpenAI API (`/v1/chat/completions`, `/v1/models`)

## Модели

| ID | Описание | Работает с прокси | Работает без прокси |
|---|---|---|---|
| `mcf-mimo-auto` | Xiaomi MiMo (авто) | ❌ upstream блокирует | ⚠️ rate-limit |

> Префикс `mcf-` используется для совместимости с другими провайдерами в инструментах вроде Hermes. Префикс автоматически снимается перед отправкой в upstream.

## Установка

```bash
git clone https://github.com/mmkeeper/mimo-free-proxy.git
cd mimo-free-proxy
pip install -r requirements.txt
```

## CLI arguments

Все проекты используют одинаковый CLI интерфейс:

```bash
python server.py --port 8788 --host 127.0.0.1 --proxy socks5://127.0.0.1:9150 --api-key sk-my-key
```

| Аргумент | По умолчанию | Описание |
|----------|--------------|----------|
| `--port` | `8788` | Порт прослушивания |
| `--host` | `127.0.0.1` | Хост прослушивания |
| `--proxy` | _(нет)_ | SOCKS5 прокси (например `socks5://127.0.0.1:9150`) |
| `--api-key` | `sk-mimo-keeper-unique-key` | API-ключ для доступа к прокси |

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
    "model": "mcf-mimo-auto",
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
    model="mcf-mimo-auto",
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

## llama-swap integration

Этот сервер работает с [llama-swap](https://github.com/mmkeeper/llama-swap) как peer. Пример конфигурации см. в `config.yaml` в репо llama-swap.
