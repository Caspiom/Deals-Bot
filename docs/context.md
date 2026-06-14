# Deals Bot — Contexto do Projeto para LLMs

> **Instruções para a IA:** Este arquivo é a fonte da verdade do projeto. Leia-o integralmente antes de sugerir qualquer código ou decisão de arquitetura. As seções "Diretrizes de Design" e "Estado Atual" são especialmente críticas.

---

## 1. Visão Geral do Projeto

**Nome:** Deals Bot MVP
**Objetivo:** Bot automatizado para o Telegram que monitora portais de promoções, filtra as melhores ofertas, converte links em URLs de afiliado e posta cards formatados em um canal do Telegram.

**Público-alvo:** Seguidores de um canal Telegram de "achadinhos" (promoções e cupons).

**Princípio central:** MVP funcional, modular e resiliente a falhas. Cada camada é substituível de forma independente — um scraper pode ser trocado sem alterar o poster do Telegram, e vice-versa.

---

## 2. Stack Técnica e Dependências

**Gerenciador de pacotes:** `uv` (não pip). Usar sempre `uv add`, `uv sync`, `uv run`. O lock file é `uv.lock` (commitado). Não existe `requirements.txt` neste projeto.

| Biblioteca | Versão Resolvida | Responsabilidade |
|---|---|---|
| `httpx` | 0.28.1 | Cliente HTTP async para o scraper |
| `beautifulsoup4` | 4.15.0 | Parsing de HTML das páginas de ofertas |
| `lxml` | 6.1.1 | Parser rápido usado como backend do bs4 |
| `python-telegram-bot` | 22.8 | Interface com a Telegram Bot API (async/v20+) |
| `APScheduler` | 3.11.2 | Agendamento do loop de scraping (cron-like) |
| `python-dotenv` | 1.2.2 | Carregamento de variáveis de ambiente via `.env` |
| `loguru` | 0.7.3 | Logging estruturado com rotação de arquivos |
| `tenacity` | 9.1.4 | Retries declarativos com backoff exponencial |
| `sqlite3` | built-in | Filtro de duplicidade (dedup) — sem dependência externa |
| `pytest` + `pytest-asyncio` | 9.1.0 / 1.4.0 | Testes (grupo `dev`) |

**Nota sobre Playwright:** Preparado na arquitetura via `BaseScraper`, mas não adicionado ao MVP. Usar `uv add playwright` apenas quando o scraper-alvo exigir JavaScript.

---

## 3. Arquitetura e Diretórios

### Mapa de Pastas

```
deals-bot/
│
├── docs/
│   └── context.md              ← ESTE ARQUIVO (memória do projeto)
│
├── src/
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base_scraper.py     ← Contrato abstrato (interface)
│   │   └── pelando_scraper.py  ← Implementação concreta (MVP)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── affiliate.py        ← Conversor de links (mockado no MVP)
│   │   ├── telegram_poster.py  ← Worker de postagem com retry
│   │   └── dedup_filter.py     ← Filtro de duplicidade via SQLite
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logger.py           ← Configuração global do loguru
│   │   └── retry.py            ← Decorator de retry via tenacity
│   │
│   └── config/
│       ├── __init__.py
│       └── settings.py         ← Carrega .env e expõe constantes tipadas
│
├── data/
│   └── deals.db                ← Gerado em runtime (SQLite, no .gitignore)
│
├── logs/
│   └── bot.log                 ← Gerado em runtime (no .gitignore)
│
├── main.py                     ← Orquestrador / entry point
├── conftest.py                 ← Injeta env vars mínimas para testes (sem .env)
├── pyproject.toml              ← Dependências e metadados do projeto (uv)
├── uv.lock                     ← Lock file gerado pelo uv (commitado)
├── pytest.ini                  ← Config do pytest (testpaths, asyncio_mode, pythonpath)
├── .env                        ← Variáveis reais (no .gitignore, NUNCA commitado)
├── .env.example                ← Template de variáveis (commitado)
└── .gitignore
```

### Fluxo de Dados

```
APScheduler (a cada N minutos, configurado em SCRAPE_INTERVAL_MINUTES)
        │
        ▼
  PelandoScraper.fetch()
        │  Retorna: List[Deal]  (dataclass com title, url, price, old_price, image_url, source)
        ▼
  DedupFilter.is_new(deal)      ← Consulta SQLite pelo hash SHA-256 da URL
        │
        │ (novo)                 (já visto → descartado silenciosamente)
        ▼
  AffiliateService.convert(url) ← Retorna URL de afiliado (mockada no MVP)
        │
        ▼
  TelegramPoster.send(deal)     ← Formata card HTML + posta via Bot API
        │                          Retry com backoff exponencial via tenacity
        ▼
  DedupFilter.mark_seen(deal)   ← Salva hash no SQLite com timestamp
```

### Modelo de Dados — `Deal` (dataclass)

Definido em `src/models.py`. O `discount_pct` é calculado automaticamente em `__post_init__` se `old_price` estiver disponível.

```python
@dataclass
class Deal:
    title: str
    url: str                 # URL original do produto
    price: float             # Preço atual
    old_price: float | None  # Preço antigo (None se não disponível)
    discount_pct: int | None # Calculado em __post_init__ automaticamente
    image_url: str | None
    source: str              # Ex: "pelando", "amazon", "mock"
    affiliate_url: str       # Preenchida pelo AffiliateService (default "")
```

---

## 4. Diretrizes de Design (Regras da Casa)

Estas decisões foram tomadas conscientemente e **não devem ser revertidas sem discussão**.

### 4.1 Fail-Fast na Inicialização
`settings.py` usa `os.environ["CHAVE"]` (levanta `KeyError`) para variáveis obrigatórias como `TELEGRAM_BOT_TOKEN`. O bot **não deve iniciar em silêncio** se estiver mal configurado. Variáveis opcionais usam `os.getenv("CHAVE", "default")`.

### 4.2 Paths Absolutos via `BASE_DIR`
Todos os caminhos de arquivo (`DATABASE_PATH`, `LOG_FILE`) são resolvidos como `Path` absolutos a partir de `BASE_DIR = Path(__file__).resolve().parent.parent.parent`. O bot funciona corretamente independente do diretório de trabalho ao ser chamado.

### 4.3 Desacoplamento de Scrapers via `BaseScraper`
Todo scraper herda de `BaseScraper` (ABC) e implementa o método `async def fetch() -> list[Deal]`. O orquestrador (`main.py`) não conhece a implementação concreta — apenas o contrato. Trocar de Pelando para Amazon Offers = trocar uma linha em `main.py`.

### 4.4 Retries com `tenacity` (não manual)
Nenhum `try/except` com `time.sleep` para retry. Toda lógica de retenativa usa o decorator `@retry` do `tenacity` com `wait_exponential` e `stop_after_attempt`. O decorator reutilizável fica em `src/utils/retry.py`.

### 4.5 Deduplicação por Hash SHA-256
O `DedupFilter` não armazena URLs brutas. Armazena `sha256(url)` para manter o banco compacto e uniforme. Registros expiram após `DEDUP_TTL_DAYS` dias (limpeza no startup do bot).

### 4.6 Rate Limiting do Telegram
A Telegram Bot API limita a **30 mensagens/segundo** globais e **1 mensagem/segundo por chat**. O `TelegramPoster` aplica um delay fixo de `1.1s` entre postagens do mesmo ciclo para nunca atingir esse limite.

### 4.7 Logging Estruturado
Toda saída de log passa pelo `loguru`. Proibido usar `print()` fora de scripts de debug pontuais. O logger é configurado uma vez em `src/utils/logger.py` e importado nos demais módulos.

### 4.8 Isolamento de Testes via `conftest.py`
O `conftest.py` na raiz injeta variáveis de ambiente mínimas (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`) antes da coleta do pytest. Isso mantém o Fail-Fast do `settings.py` em produção sem exigir um `.env` no CI ou ambiente de testes. `DedupFilter` aceita `db_path` opcional para usar banco em memória temporária (`tmp_path` do pytest) sem monkeypatching.

---

## 5. Estado Atual e Próximos Passos

### ✅ Fase 1 — Estrutura Fundacional (CONCLUÍDA — 2026-06-14)
- [x] Estrutura de pastas criada (`src/`, `data/`, `logs/`, `docs/`)
- [x] `.env.example` documentado por categoria (Telegram, Afiliados, Scraper, DB, Logs)
- [x] `.gitignore` configurado (protege `.env`, `deals.db`, logs, caches)
- [x] `src/config/settings.py` carregando e tipando todas as variáveis de ambiente
- [x] `docs/context.md` criado (este arquivo)

---

### ✅ Fase 2 — Utilitários e Filtro de Duplicidade (CONCLUÍDA — 2026-06-14)
- [x] Migração de `pip` + `requirements.txt` para `uv` + `pyproject.toml` + `uv.lock`
- [x] `src/models.py` — dataclass `Deal` com cálculo automático de `discount_pct`
- [x] `src/utils/logger.py` — loguru com sink stdout + arquivo, rotação diária
- [x] `src/utils/retry.py` — decorator `telegram_retry` (3 tentativas, backoff exponencial)
- [x] `src/services/dedup_filter.py` — SQLite com SHA-256, TTL, `is_new()`, `mark_seen()`
- [x] `conftest.py` — isolamento de testes sem `.env`
- [x] `tests/test_dedup.py` — 6 testes, 0 warnings (`uv run pytest -v`)

---

### ✅ Fase 3 — Scrapers (CONCLUÍDA — 2026-06-14)
- [x] `src/scrapers/base_scraper.py` — ABC com método abstrato `async def fetch() -> list[Deal]`
- [x] `src/scrapers/mock_scraper.py` — 12 produtos BR realistas, filtra por `MIN_DISCOUNT_PERCENT`, respeita `MAX_DEALS_PER_RUN`, simula latência de rede
- [x] `tests/test_mock_scraper.py` — 5 testes async, 11/11 total passando

**Decisão registrada:** Pelando e Promobit são SPAs JS-rendered (Next.js). Mercado Livre API exige OAuth. Scrapers reais precisam de Playwright — adiado para Fase 6. `MockScraper` garante que o pipeline completo pode ser testado sem dependência externa.

---

### ✅ Fase 4 — Serviços de Afiliado e Telegram (CONCLUÍDA — 2026-06-14)
- [x] `src/services/affiliate.py` — `convert(url)` com rotas para Amazon (`tag=`), Magalu (`partner_id=`) e fallback shope.ee; usa `urllib.parse` para preservar params existentes
- [x] `src/services/telegram_poster.py` — card HTML com título, preço BRL formatado (`R$ 2.199,00`), desconto em %, botão inline de afiliado; `@telegram_retry` + rate limit de 1.1s
- [x] `tests/test_affiliate.py` — 5 testes, `tests/test_telegram_poster.py` — 6 testes (Bot mockado com `AsyncMock`)
- [x] 22/22 testes passando, zero warnings

---

### 🔲 Fase 5 — Orquestrador e Finalização

**Escopo:**
- `main.py`: Instanciar todos os serviços, registrar o job no `APScheduler`, iniciar o loop.
- Teste de integração ponta-a-ponta.
- Instruções de deploy (systemd service ou Docker — a decidir).

---

## 6. Convenções de Atualização deste Arquivo

- **Ao concluir uma fase:** Mover o item de `🔲` para `✅` e adicionar a data de conclusão.
- **Ao tomar uma nova decisão de design:** Adicionar em "Diretrizes de Design" com a motivação.
- **Ao adicionar uma dependência:** Atualizar a tabela da seção 2.
- **Ao mudar a estrutura de pastas:** Atualizar o mapa na seção 3.
