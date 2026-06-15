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
| `discord.py` | 2.7.1 | Bot do Discord (slash commands, embeds, multi-servidor) |
| `pytest` + `pytest-asyncio` | 9.1.0 / 1.4.0 | Testes (grupo `dev`) |

**Nota sobre Playwright:** Adicionado ao projeto (`playwright==1.60.0`). Usado pelo `PelandoScraper` e `MercadoLivreScraper`. `PromobitScraper` e `KabumScraper` usam apenas `httpx` (APIs REST públicas).

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
│   │   ├── base_scraper.py             ← Contrato abstrato (interface)
│   │   ├── playwright_base_scraper.py  ← Base para scrapers com browser headless
│   │   ├── mock_scraper.py             ← Scraper de teste com dados BR realistas
│   │   ├── pelando_scraper.py          ← Playwright: feed do Pelando
│   │   ├── promobit_scraper.py         ← httpx: API REST pública do Promobit
│   │   ├── mercadolivre_scraper.py     ← Playwright: página de ofertas do ML
│   │   └── kabum_scraper.py            ← httpx: API REST pública do KaBuM (6 categorias)
│   │
│   ├── publishers/
│   │   ├── __init__.py
│   │   ├── base_publisher.py           ← Contrato abstrato (interface)
│   │   ├── telegram_publisher.py       ← Card HTML + botão inline + retry
│   │   ├── x_publisher.py              ← Tweepy AsyncClient (500 tweets/mês free)
│   │   ├── instagram_publisher.py      ← Graph API v20: container → publish
│   │   └── discord_publisher.py        ← discord.py: bot multi-servidor com slash commands
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── affiliate.py                ← Conversor de links (Amazon, Magalu, shope.ee)
│   │   ├── dedup_filter.py             ← Filtro SHA-256 + TTL + re-post de promos quentes
│   │   └── guild_config.py             ← Configuração de canal por servidor Discord (SQLite)
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logger.py                   ← Configuração global do loguru
│   │   ├── retry.py                    ← Decorator de retry via tenacity
│   │   └── formatters.py              ← brl() compartilhado entre publishers
│   │
│   └── config/
│       ├── __init__.py
│       └── settings.py                 ← Carrega .env e expõe constantes tipadas
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
APScheduler (a cada SCRAPE_INTERVAL_MINUTES)
        │
        ▼
  asyncio.gather(scrapers)       ← Pelando, Promobit, MercadoLivre, KaBuM em paralelo
        │  Retorna: List[Deal]
        ▼
  dedup.is_new(deal)             ← Consulta SQLite pelo hash SHA-256 da URL
  dedup.can_repost(deal)         ← Promo quente (≥ MIN_HOT_DISCOUNT_PCT) com
        │                           last_posted_at > REPOST_INTERVAL_HOURS atrás
        │ (novo ou re-post quente)   (já visto recentemente → descartado)
        ▼
  AffiliateService.convert(url)  ← Rotas: Amazon, Magalu, shope.ee (fallback)
        │
        ▼
  for publisher in publishers:   ← Telegram, X, Instagram, Discord (conforme ENABLED_PUBLISHERS)
      publisher.publish(deal)    ← Retry com backoff exponencial via tenacity
        │
        ▼
  dedup.mark_seen(deal)          ← Atualiza last_posted_at (preserva seen_at original)
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
    source: str              # Ex: "pelando", "promobit", "kabum"
    store: str               # Loja real do produto (ex: "Amazon", "KaBuM")
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
O `conftest.py` na raiz injeta variáveis de ambiente mínimas (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`) antes da coleta do pytest. Isso mantém o Fail-Fast do `settings.py` em produção sem exigir um `.env` no CI ou ambiente de testes. `DedupFilter` e `GuildConfigStore` aceitam `db_path` opcional para usar banco em memória temporária (`tmp_path` do pytest) sem monkeypatching.

### 4.9 Re-post com Intervalo por Desconto
Deals ainda ativos nos scrapers são elegíveis para re-post baseado no desconto: `discount_pct >= HIGH_DISCOUNT_PCT` (padrão 50%) → re-post a cada `REPOST_HIGH_HOURS` (padrão 24h); abaixo disso → `REPOST_LOW_HOURS` (padrão 48h). O `DedupFilter` rastreia dois timestamps distintos: `seen_at` (primeira vez, usado para TTL/expiração) e `last_posted_at` (último post, usado para intervalo de re-post). O `mark_seen()` usa UPSERT — preserva `seen_at` original e atualiza apenas `last_posted_at`. O hash de URL normaliza o path removendo query string e fragment, evitando falsos "novos" por parâmetros de tracking.

### 4.10 Discord Bot — Configuração por Servidor
O `DiscordPublisher` não usa canal fixo. Cada servidor Discord configura seu próprio canal via slash command `/set-channel #canal` (requer permissão "Gerenciar Servidor"). A configuração `guild_id → channel_id` fica salva na tabela `discord_guild_channels` do mesmo `deals.db`. Ao entrar em novo servidor, o bot envia mensagem de boas-vindas explicando o setup. Se o canal configurado for deletado, o bot loga warning e pula o servidor sem travar os demais.

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

### ✅ Fase 8 — Docker e Deploy (CONCLUÍDA — 2026-06-14)
- [x] `Dockerfile` — python:3.12-slim + uv + Playwright Chromium; layers otimizados por ordem de cópia
- [x] `docker-compose.yml` — bind mounts para `data/` e `logs/`, `restart: unless-stopped`, `mem_limit: 1.5g`
- [x] `.dockerignore` — exclui `.env`, `.venv`, `tests/`, `data/`, `logs/`, `docs/`
- [x] Build local validado: imagem 624MB (content), smoke test dentro do container OK
- [ ] Deploy em produção (Hetzner / Fly.io / Oracle Cloud)

**Plataformas recomendadas:** Hetzner CX22 (~R$ 25/mês, 2GB RAM) ou Fly.io (~R$ 30/mês, região GRU). Oracle Cloud Free Tier (0 custo, ARM, 1GB RAM) como opção gratuita. AWS descartada por custo/complexidade.

**Comando de deploy:**
```bash
# Qualquer VPS com Docker instalado:
git clone https://github.com/Caspiom/Deals-Bot.git
cd Deals-Bot
cp .env.example .env   # preencher credenciais
docker compose up -d
```

---

### ✅ Fase 7 — Multi-Platform Publishers (CONCLUÍDA — 2026-06-14)
- [x] `src/publishers/base_publisher.py` — ABC com `publish(deal)`
- [x] `src/publishers/telegram_publisher.py` — migrado do telegram_poster.py
- [x] `src/publishers/x_publisher.py` — tweepy `AsyncClient` (requer `aiohttp`, `async-lru`)
- [x] `src/publishers/instagram_publisher.py` — Graph API v20: container → publish (pula deals sem imagem)
- [x] `src/utils/formatters.py` — `brl()` compartilhado entre publishers
- [x] `ENABLED_PUBLISHERS` no `.env` controla quais plataformas estão ativas
- [x] `main.py` — scrapers em paralelo (`asyncio.gather`) + publishers em loop por deal
- [x] 50/50 testes passando, zero warnings

**Decisão registrada:** WhatsApp excluído do escopo — Meta Cloud API não suporta broadcast nativo; soluções não-oficiais têm risco de ban. Instagram requer conta Business + Facebook Page. X tem free tier de 500 tweets/mês (suficiente para ~16 posts/dia).

---

### ✅ Fase 6 — Scrapers Reais: Pelando + Promobit (CONCLUÍDA — 2026-06-14)
- [x] `src/scrapers/playwright_base_scraper.py` — base para scrapers com browser headless
- [x] `src/scrapers/pelando_scraper.py` — Playwright: `a[data-deal-id]` + JS evaluate, parse BRL, extrai % do título
- [x] `src/scrapers/promobit_scraper.py` — httpx puro: API REST pública `api.promobit.com.br/offers`, sem browser
- [x] `tests/test_pelando_scraper.py` — 8 testes de parsing (sem Playwright)
- [x] `tests/test_promobit_scraper.py` — 5 testes com httpx mockado
- [x] 39/39 testes passando

**Decisão registrada:** Promobit expõe API REST pública descoberta via interceptação de rede com Playwright — não precisa de browser para scraping. `offer_discont_percentage == 0` é recalculado via preços quando disponíveis. Pelando usa Playwright com `a[data-deal-id]` como âncora estável.

---

### ✅ Fase 5 — Orquestrador e Finalização (CONCLUÍDA — 2026-06-14)
- [x] `main.py` — `run_cycle()` orquestra scraper → dedup → affiliate → poster; `AsyncIOScheduler` com execução imediata no startup; shutdown limpo no Ctrl+C
- [x] `tests/test_integration.py` — 4 testes ponta-a-ponta: posts novos, dedup no 2º ciclo, affiliate_url preenchida, resiliência a falha de post
- [x] 26/26 testes passando, zero warnings
- [ ] Deploy (systemd service ou Docker) — a decidir

---

### ✅ Fase 9 — Re-post de Promos Quentes (CONCLUÍDA — 2026-06-14)
- [x] `dedup_filter.py` — coluna `last_posted_at` adicionada com migração automática de DBs existentes
- [x] `can_repost(deal)` — retorna `True` se `discount_pct >= MIN_HOT_DISCOUNT_PCT` e intervalo decorrido
- [x] `mark_seen()` — UPSERT: preserva `seen_at` original, atualiza apenas `last_posted_at`
- [x] `main.py` — `run_cycle()` publica `new_deals + hot_reposts` por ciclo
- [x] `settings.py` — `MIN_HOT_DISCOUNT_PCT=40`, `REPOST_INTERVAL_HOURS=2`
- [x] `tests/test_dedup.py` — 12 testes (6 novos para `can_repost` e comportamento do UPSERT)

---

### ✅ Fase 10 — Scraper KaBuM (CONCLUÍDA — 2026-06-14)
- [x] `src/scrapers/kabum_scraper.py` — httpx puro, API REST pública `servicespub.prod.api.aws.grupokabum.com.br`
- [x] Busca 6 categorias em paralelo: `hardware`, `perifericos`, `smartphones-tablets`, `computadores`, `games`, `tv-video`
- [x] Deduplicação por `product_id` entre categorias; URL: `kabum.com.br/produto/{id}/{slug}`
- [x] `tests/test_kabum_scraper.py` — 8 testes (filtros, mapeamento, dedup, cálculo de desconto, resiliência a falha de categoria)
- [x] 76/76 testes passando

**Decisão registrada:** Pichau (403 na API), Shopee (403), Zoom (Algolia, precisa de key), Cuponomia (403) e Buscapé (offline) investigados e descartados. KaBuM foi o único portal com API REST pública acessível sem autenticação além dos já existentes.

---

### ✅ Fase 11 — Publisher Discord (CONCLUÍDA — 2026-06-14)
- [x] `src/publishers/discord_publisher.py` — `discord.py` 2.7.1; bot multi-servidor com `CommandTree`
- [x] `src/services/guild_config.py` — `GuildConfigStore`: tabela `discord_guild_channels` no `deals.db`
- [x] Slash commands (sync global via `tree.sync()` no `on_ready`):
  - `/set-channel #canal` — configura canal do servidor (requer Gerenciar Servidor)
  - `/remove-channel` — remove configuração
  - `/help` — mostra comandos + status atual do canal configurado
- [x] `on_guild_join` — mensagem de boas-vindas com instruções de setup
- [x] Shutdown limpo: `close()` chamado no `finally` do `main.py`
- [x] `DISCORD_BOT_TOKEN` no `.env`; ativado via `ENABLED_PUBLISHERS=discord`
- [x] `tests/test_discord_publisher.py` + `tests/test_guild_config.py` — 17 testes
- [x] 93/93 testes passando, zero warnings

**Setup para novo servidor:** criar aplicação em discord.com/developers → Bot → copiar token. OAuth2 → URL Generator (scopes: `bot`, permissões: Send Messages, Embed Links, Attach Files, View Channels). Ao entrar no servidor, admin usa `/set-channel` para apontar o canal desejado.

---

---

### ✅ Fase 12 — Módulo de Frases de Efeito / Copywriter (CONCLUÍDA — 2026-06-15)
- [x] `src/services/category_classifier.py` — classifica produto em 9 categorias via regex no título
- [x] `src/services/copywriter.py` — sorteia frase orgânica por categoria (tom casual, BR, sem marketing genérico)
- [x] `Deal.tagline` — campo gerado uma vez antes de publicar, reutilizado por todos os publishers
- [x] `TelegramPublisher` — exibe tagline entre título e preços
- [x] `main.py` — chama `generate_tagline(deal)` no loop de publicação

**Decisão registrada:** Templates estáticos com variação aleatória por categoria. LLM (`claude-haiku-4-5`) planejado como evolução futura para produtos que não se encaixam nos padrões de regex. Frases no tom de "amigo mandando no grupo" — sem travessões, sem linguagem de marketing.

---

### ✅ Fase 13 — Módulo de Parcelamento (CONCLUÍDA — 2026-06-15)
- [x] `src/services/installment_calculator.py` — `parse_installment_string()` para strings reais + `estimate()` por faixa de preço (mínimo R$50/parcela, máx 12x)
- [x] KaBuM: campo `max_installment` já disponível na API como string — parseado diretamente
- [x] MercadoLivre: extração do DOM via `[class*="installments"], [class*="poly-price__installments"]`
- [x] Promobit/Pelando: sem dado real na API/DOM — estimativa ativada por `SHOW_ESTIMATED_INSTALLMENTS=true` no `.env` (padrão: desligado)
- [x] `Deal.installments` e `Deal.installment_value` — preenchidos antes de publicar
- [x] `TelegramPublisher` — linha `💳 Nx de R$ X,XX sem juros` exibida quando disponível
- [x] `settings.py` — `SHOW_ESTIMATED_INSTALLMENTS` (bool, padrão `false`)

**Decisão registrada:** Promobit não retorna dado de parcelamento na API. KaBuM retorna `max_installment` como string (`"10x de R$ 280,00"`). Estimativa por faixa de preço desligada por padrão para não exibir dado impreciso.

---

## 6. Convenções de Atualização deste Arquivo

- **Ao concluir uma fase:** Mover o item de `🔲` para `✅` e adicionar a data de conclusão.
- **Ao tomar uma nova decisão de design:** Adicionar em "Diretrizes de Design" com a motivação.
- **Ao adicionar uma dependência:** Atualizar a tabela da seção 2.
- **Ao mudar a estrutura de pastas:** Atualizar o mapa na seção 3.
