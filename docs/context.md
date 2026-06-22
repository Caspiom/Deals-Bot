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
| `fake-useragent` | 2.2.0 | Rotação de User-Agent realista nos scrapers Playwright |
| `sqlite3` | built-in | Filtro de duplicidade (dedup) — sem dependência externa |
| `discord.py` | 2.7.1 | Bot do Discord (slash commands, embeds, multi-servidor) |
| `pytest` + `pytest-asyncio` | 9.1.0 / 1.4.0 | Testes (grupo `dev`) |

**Nota sobre Playwright:** Adicionado ao projeto (`playwright==1.60.0`). Usado pelo `PelandoScraper` e `MercadoLivreScraper`. `PromobitScraper`, `KabumScraper` e `AliExpressScraper` usam apenas `httpx` (APIs REST públicas).

---

## 3. Arquitetura e Diretórios

### Mapa de Pastas

```
deals-bot/
│
├── docs/
│   ├── context.md              ← ESTE ARQUIVO (memória do projeto)
│   ├── proxy_setup.md          ← Guia de proxy residencial BR (anti-bot)
│   └── tracking_setup.md       ← Guia de DNS, Nginx/Caddy e SSL para o tracker
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
│   │   ├── kabum_scraper.py            ← httpx: API REST pública do KaBuM
│   │   ├── magalu_scraper.py           ← Playwright: busca por desconto ordenada por -percentual_desconto
│   │   ├── shopee_scraper.py           ← httpx: API interna /api/v4/search (multi-keyword, preços ÷ 100 000)
│   │   ├── aliexpress_scraper.py       ← httpx: AliExpress Portals API (HMAC-MD5, preço local c/ impostos BR)
│   │   └── amazon_scraper.py           ← httpx: Amazon PA API v5 (AWS Signature v4, multi-categoria)
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
  asyncio.gather(scrapers)       ← MercadoLivre, KaBuM, Magalu, Shopee, AliExpress, Amazon em paralelo
        │  Retorna: List[Deal]
        ▼
  is_commissionable(url)         ← Descarta URLs de agregadores (diretriz 4.11)
        │
        ▼
  dedup.is_new(deal)             ← Consulta SQLite pelo hash SHA-256 da URL
  dedup.can_repost(deal)         ← Promo quente (≥ MIN_HOT_DISCOUNT_PCT) com
        │                           last_posted_at > REPOST_INTERVAL_HOURS atrás
        │ (novo ou re-post quente)   (já visto recentemente → descartado)
        ▼
  AffiliateService.convert(url)  ← Rotas: Amazon, Magalu, ML; AliExpress já vem com tracking na URL
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
    url: str                         # URL original do produto (ou promotionLink para AliExpress)
    price: float                     # Preço atual (com impostos se local_sale_price disponível)
    old_price: float | None          # Preço antigo (None se não disponível)
    discount_pct: int | None         # Calculado em __post_init__ automaticamente
    image_url: str | None
    source: str                      # Ex: "kabum", "mercadolivre", "aliexpress"
    store: str                       # Loja real do produto (ex: "Amazon", "KaBuM", "AliExpress")
    tagline: str                     # Frase de efeito gerada pelo copywriter (default "")
    installments: int | None         # Número de parcelas (real ou estimado)
    installment_value: float | None  # Valor por parcela
    coupon_code: str | None          # Cupom de desconto quando disponível
    coins_discount_value: float | None  # Preço com moedas/cashback (MercadoLivre)
    affiliate_url: str               # Preenchida pelo AffiliateService antes de publicar (default "")
    tracked_url: str                 # URL de rastreamento achadinhosbr.com/r/{deal_id} (default ""); vazio se TRACKER_BASE_URL não configurado
    is_price_low: bool               # True se for o menor preço nos últimos 30 dias
    tax_note: str | None             # Nota de imposto de importação (ex: AliExpress com impostos BR)
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

### 4.12 Estratégia de Afiliado — Interpolação de String como Fallback Global

**Decisão:** O `AffiliateService` usa manipulação direta de URL (regex + reconstrução de string) como estratégia principal de injeção de tag de afiliado. Chamadas a SDKs ou APIs REST de afiliados ficam restritas a casos onde são obrigatórias (ex: AliExpress Portals API, que embute o tracking na `promotionLink`).

**Motivação:** APIs de afiliado (Amazon PA API, Magalu API) exigem credenciais, aprovação de parceiro e têm rate limits. A interpolação de string é zero-dependency, zero-latência e funciona para qualquer URL da loja — mesmo quando as APIs estão inacessíveis ou o programa de afiliado não está ativo ainda.

**Padrão por loja:**
- **Amazon:** extrai ASIN via `/dp/([A-Z0-9]{10})` e reconstrói `amazon.com.br/dp/{ASIN}?tag={tag}` — URL canônica sem parâmetros de tracking (`/ref=...`, `?ref=...`)
- **Magalu/ML/Shopee:** `urllib.parse` injeta `partner_id=` ou `af_id=` preservando params existentes
- **Lojas sem programa ativo (KaBuM etc.):** URL original retornada intacta via `_default(url)`

### 4.11 Filtro de Monetização — Proibido Dar Comissão a Agregadores
**DIRETRIZ DE MONETIZAÇÃO:** O bot NÃO DEVE dar comissão de graça para agregadores concorrentes. É estritamente proibido enviar para os cards finais do Telegram ofertas cujos links finais pertençam ou passem pelo redirecionamento de agregadores terceiros (como Promobit e Pelando), pois a comissão fica para eles.

**Implementação:** A função `is_commissionable(url)` em `src/services/affiliate.py` mantém uma lista negra de domínios de agregadores (`_AGGREGATOR_DOMAINS`). O `run_cycle()` em `main.py` descarta silenciosamente qualquer deal cujo `url` pertença a essa lista antes de entrar na fila de publicação. Paralelamente, os scrapers `PromobitScraper` e `PelandoScraper` são mantidos no codebase mas **removidos da lista ativa** de `main.py` — pois nunca expõem a URL direta da loja final.

**Lojas diretas permitidas — alvo do motor de captação:**

| Loja | Status | Programa de Afiliado | Observação |
|---|---|---|---|
| Amazon | ✅ Integrado | Amazon Associados (tag injetada via regex) | Playwright raspa `/deals`; ASIN extraído por regex; PA API removida |
| Mercado Livre | ✅ Integrado | Parceiros ML (`partner_id=`) | Scraper Playwright ativo |
| Magazine Luiza | ✅ Integrado | Parceiros Magalu (`partner_id=`) | Scraper Playwright ativo; `affiliate.py` injeta `partner_id` |
| KaBuM | ✅ Scraper ativo | Awin Brasil / Lomadee | URL direta; integração afiliado pendente |
| AliExpress | ✅ Integrado | Programa AliExpress Portals (Portals API) | `promotionLink` com tracking; `localSalePrice` com impostos BR |
| Shopee | ✅ Integrado | Shopee Affiliates (`af_id=`) | API interna /api/v4/search; `af_id` injetado via `affiliate.py._shopee()` |
| Casas Bahia | 🔲 Pendente | Awin Brasil | Produto de volume alto; scraper viável |
| Netshoes | 🔲 Pendente | Lomadee / Awin | Forte em calçados e esportes |
| Samsung BR | 🔲 Pendente | Awin Brasil | Lançamentos e campanhas de eletrônicos |
| Americanas | 🔲 Pendente | Awin Brasil | Marketplace de alto volume |
| Submarino | 🔲 Pendente | Awin Brasil | Mesmo grupo das Americanas (B2W) |
| Centauro | 🔲 Pendente | Lomadee | Esportes e artigos fitness |
| Dafiti | 🔲 Pendente | Awin Brasil | Moda e calçados |
| Shein BR | 🔲 Pendente | Shein Affiliates | Alto volume; moda popular |
| Dell BR | 🔲 Pendente | Awin Brasil | Notebooks e periféricos |
| Lenovo BR | 🔲 Pendente | Awin Brasil | Notebooks e desktops |
| Pichau | 🔲 Pendente | Programa próprio | Hardware e periféricos gamer |
| Terabyte Shop | 🔲 Pendente | Programa próprio | Hardware entusiasta |

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

### ✅ Fase 14 — Esquema de Cupons e Moedas (CONCLUÍDA — 2026-06-16)
- [x] Mapeado o comportamento de cupons e moedas nos scrapers existentes: MercadoLivre (DOM via Playwright), Promobit (campo `offer_coupon` da API) e Pelando (badge de cupom no DOM).
- [x] `src/models.py` — campos opcionais `coupon_code: str | None` e `coins_discount_value: float | None` adicionados ao dataclass `Deal`.
- [x] `MercadoLivreScraper` — `_EXTRACT_JS` estendido com seletores `[class*="coupon"]` e `[class*="coins"]`; Python mapeia para os novos campos.
- [x] `PromobitScraper` — extrai `offer_coupon` da resposta da API defensivamente.
- [x] `PelandoScraper` — `_EXTRACT_JS` estendido com seletor `[class*="coupon"]`.
- [x] `TelegramPublisher` — exibe `🎟️ Cupom: <code>CÓDIGO</code>` e `🪙 Com moedas sai por: R$ X,XX` quando presentes.
- [x] `DiscordPublisher` — exibe os mesmos campos em markdown Discord.
- [x] `tests/test_dedup.py` — corrigido bug pré-existente nos testes de repost (intervalo era 3h mas threshold padrão é 24h).
- [x] 101/101 testes passando, zero warnings.

---

### ✅ Fase 14.5 — Filtro de Monetização + Scraper AliExpress (CONCLUÍDA — 2026-06-16)

**Filtro de monetização (diretriz 4.11):**
- [x] `src/services/affiliate.py` — `_AGGREGATOR_DOMAINS` frozenset + `is_commissionable(url)`: descarta URLs de Promobit, Pelando, Zoom, Buscapé, Meliuz e similares
- [x] `main.py` — `PromobitScraper` e `PelandoScraper` removidos da lista ativa; filtro `is_commissionable()` aplicado como segunda barreira antes da fila de publicação
- [x] `src/services/affiliate.py` — bug corrigido: `_default()` retornava placeholder `shope.ee/exemplo` para todas as lojas sem integração; agora retorna a URL original intacta
- [x] `tests/test_affiliate.py` — 12 casos de teste para `is_commissionable()` (lojas diretas passam, agregadores bloqueiam)

**Scraper AliExpress:**
- [x] `src/scrapers/aliexpress_scraper.py` — AliExpress Portals API (`api-sg.aliexpress.com/sync`), método `aliexpress.affiliate.hotproduct.query`, autenticação HMAC-MD5
- [x] Usa `localSalePrice` / `localOriginalPrice` da API — preço calculado pelo próprio AliExpress já com II (20%) + ICMS (variável por estado) para o Brasil; fallback para `sale_price` se campos locais ausentes
- [x] `promotionLink` da resposta já embute o `tracking_id` — nenhuma manipulação de URL necessária; `convert()` retorna a URL intacta via `_default()`
- [x] `Deal.tax_note` — novo campo opcional; preenchido com aviso de impostos incluídos quando `local_sale_price` está disponível
- [x] `TelegramPublisher` e `DiscordPublisher` — exibem `tax_note` quando presente
- [x] `settings.py` — `ALIEXPRESS_APP_KEY`, `ALIEXPRESS_SECRET_KEY`, `ALIEXPRESS_TRACKING_ID`
- [x] `main.py` — `AliExpressScraper` adicionado à lista ativa de scrapers
- [x] `tests/test_aliexpress_scraper.py` — 12 testes (parsing de preço, assinatura, filtros, fallback sem credenciais, fallback sem local_price, erro de API)
- [x] 119/119 testes passando, zero warnings

**Decisão registrada:** AliExpress não expõe URL de produto direta via DOM público — usa a API oficial de afiliados (Portals). O campo `local_sale_price` retorna o preço correto para o Brasil (Remessa Conforme) evitando cálculo manual impreciso de 44%. Compras internacionais são marcadas explicitamente com `tax_note` para transparência ao usuário.

---

### ✅ Fase 14.6 — Scraper Amazon (CONCLUÍDA — 2026-06-16, migrado em 2026-06-16)

**Versão original (PA API — descontinuada):**
- Implementação com Amazon PA API v5 + AWS Signature v4 manual descontinuada por inacessibilidade de credenciais e rate limit rígido de 1 req/s

**Versão atual (HTML scraping via Playwright):**
- [x] `src/scrapers/amazon_scraper.py` — herdado de `PlaywrightBaseScraper`; raspa `amazon.com.br/deals` (Ofertas do Dia); âncora em `a[href*="/dp/"]`; usa `.a-offscreen` para preços (mais confiável que parsear whole+fraction)
- [x] ASIN extraído por regex `/dp/([A-Z0-9]{10})/` no JS extractor; dedup por ASIN no Python
- [x] `affiliate.py._amazon()` reescrito: extrai ASIN via regex, reconstrói URL canônica `amazon.com.br/dp/{ASIN}?tag={tag}` — elimina `/ref=...` e tracking poluído
- [x] `AMAZON_ACCESS_KEY` e `AMAZON_SECRET_KEY` removidos de `settings.py` e `.env.example` — não necessários
- [x] `tests/test_amazon_scraper.py` — 14 testes (parse BRL, parse discount, mapeamento de campos, dedup, filtros, resiliência a item inválido)
- [x] 169/169 testes passando, zero warnings

**Decisão registrada:** PA API exige credenciais de associado com ≥3 vendas qualificadas nos últimos 180 dias para manter acesso ativo. Scraping HTML da `/deals` não tem essa restrição — funciona imediatamente e sem chaves. A estratégia de interpolação de string para afiliado (diretriz 4.12) torna a PA API desnecessária.

---

### ✅ Fase 14.7 — Scraper Magazine Luiza (CONCLUÍDA — 2026-06-16)
- [x] `src/scrapers/magalu_scraper.py` — Playwright; URL `/busca/desconto/?ordenacao=-percentual_desconto&tipo=oferta` garante os maiores descontos primeiro
- [x] JS extractor com seletores por `data-testid` (mais estáveis) + fallback em padrão de classe do Luizalabs design system
- [x] `_parse_brl()` lida com espaço não-quebrável (`\xa0`) no formato `R$\xa01.299,90`; imagens placeholder base64 (lazy loading) são descartadas
- [x] Parcelamento extraído via `parse_installment_string()` quando disponível no card
- [x] Dedup por URL sem query string (remove `?partner_id=...&utm=...` antes de comparar)
- [x] `affiliate.py._magalu()` injeta `partner_id` no momento da publicação — scraper retorna URL limpa
- [x] `main.py` — `MagaluScraper` adicionado à lista ativa
- [x] `tests/test_magalu_scraper.py` — 18 testes (parse BRL, parse %, campos, parcelamento, dedup, imagem lazy, max deals)
- [x] 154/154 testes passando, zero warnings

**Decisão registrada:** PA API exige credenciais separadas do `ASSOCIATE_TAG` (obtidas em associados.amazon.com.br → Ferramentas → API de Publicidade). O scraper ignora graciosamente quando `AMAZON_ACCESS_KEY` não está configurado. A PA API tem rate limit de ~1 req/s e exige mínimo de 3 vendas qualificadas em 180 dias para manter acesso.

### ✅ Fase 14.8 — Scraper Shopee (CONCLUÍDA — 2026-06-16)
- [x] `src/scrapers/shopee_scraper.py` — reescrito de httpx para Playwright; API interna retornava 403; Playwright usa sessão real de browser, resolvendo o bloqueio
- [x] JS extractor ancora no padrão `-i.{shopid}.{itemid}` dos links de produto — estável mesmo com class names ofuscados
- [x] `affiliate.py` — novo `_shopee()`: appends `?af_id={AFFILIATE_ID}` à URL
- [x] `tests/test_shopee_scraper.py` — 14 testes (parse de campos, dedup, filtros, resiliência)
- [x] 168/168 testes passando, zero warnings

**Decisão registrada:** Shopee bloqueia httpx com 403 — requer cookies de sessão de browser real. Playwright contorna isso. O parâmetro `af_id` é o rastreamento para URLs diretas; links curtos (`s.shopee.com.br`) requerem API de afiliados — implementação futura.

---

### ✅ Fase 14.9 — Hardening do Motor de Captação (CONCLUÍDA — 2026-06-16)

**Diagnóstico que motivou esta fase:** Remoção do Promobit e Pelando (diretriz 4.11) secou o canal pois os scrapers de lojas diretas apresentavam quatro falhas críticas:
1. `PlaywrightBaseScraper` abria um Chromium por scraper sem semáforo → 3 browsers simultâneos → potencial OOM em container 1.5GB
2. `ShopeeScraper` buscava por popularidade (`sortBy=popular`) em vez de promoções
3. `MercadoLivreScraper` parava no scroll 3 de uma página de infinite scroll → volume baixo
4. `MagaluScraper` não aguardava o DOM carregar → extraía 0 cards consistentemente

**Mudanças implementadas:**

- [x] `src/scrapers/playwright_base_scraper.py` — **Semáforo global** `asyncio.Semaphore(PLAYWRIGHT_MAX_BROWSERS)` criado lazy; máximo 2 browsers ao mesmo tempo; **UA rotation** via `fake-useragent` (fallback para lista hardcoded de 5 UAs recentes se offline); **stealth init script** remove `navigator.webdriver`, adiciona `navigator.plugins` e `window.chrome`; suporte a **proxy** via `PROXY_URL` repassado ao `launch(proxy=...)`; viewport, locale e timezone realistas (`pt-BR`, `America/Sao_Paulo`)
- [x] `src/scrapers/mercadolivre_scraper.py` — 10 scrolls (era 3); `wait_for_selector('[class*="poly-card"]')` antes de scrollar; `wait_until="domcontentloaded"` + selector guard substitui `networkidle` (evita timeout por analytics); delay variável por scroll (500-900ms) para simular leitura humana; extração defensiva com `try/except` por item
- [x] `src/scrapers/magalu_scraper.py` — `wait_for_selector('a[href*="/p/"]', timeout=15000)` antes de extrair; extração defensiva com `try/except` por item e por campo de preço
- [x] `src/scrapers/shopee_scraper.py` — `https://shopee.com.br/flash_sale` adicionado como primeira URL (40-80% OFF); `wait_for_selector` antes de scrollar; `try/catch` interno no JS extractor evita que uma URL inválida quebre o loop; extração defensiva Python por item
- [x] `src/scrapers/amazon_scraper.py` — categorias agora **sequenciais** com `asyncio.sleep(1.1)` entre requests (PA API limita 1 req/s); decorator `@scraper_retry` na `_fetch_category`; suporte a proxy; `try/except` por item no parse
- [x] `src/scrapers/kabum_scraper.py` — decorator `@scraper_retry` no `fetch()`; User-Agent atualizado para Chrome/131; suporte a proxy; extração defensiva por item com log contextual
- [x] `src/scrapers/aliexpress_scraper.py` — decorator `@scraper_retry` no `fetch()`; suporte a proxy; `try/except` por produto
- [x] `src/utils/retry.py` — novo decorator `scraper_retry` (3 tentativas, backoff 1-8s) separado do `publisher_retry` (2-30s)
- [x] `src/config/settings.py` — `PLAYWRIGHT_MAX_BROWSERS` (padrão 2) e `PROXY_URL` (padrão vazio)
- [x] `.env.example` — documentadas novas variáveis com comentários de formato
- [x] `fake-useragent==2.2.0` adicionado via `uv add`
- [x] 168/168 testes passando, zero warnings

**Decisões registradas:**
- Semáforo criado lazy (não no module-level) para garantir compatibilidade com event loops que podem não existir no momento do import
- `wait_until="domcontentloaded"` preferido sobre `"networkidle"` nos scrapers Playwright: `networkidle` trava em páginas com analytics que disparam requests contínuos (ML, Magalu, Shopee)
- Amazon mantém `asyncio.gather` para scrapers httpx mas serializa as 6 categorias da PA API — requests paralelos à PA API geram 429 imediato
- Proxy configurado uma vez no `PlaywrightBaseScraper` e nos clientes `httpx` via `PROXY_URL` — não exige mudança nos scrapers individuais
- Shopee Flash Sale (`/flash_sale`) como fonte primária: produtos com 40-80% de desconto real vs buscas por `popular` que não têm critério de desconto

---

### ✅ Fase 14.10 — Motor de Afiliados Completo + Guia de Proxy (CONCLUÍDA — 2026-06-16)
- [x] `src/services/affiliate.py` — `_amazon()` reescrito com extração de ASIN por regex e reconstrução de URL canônica (diretriz 4.12)
- [x] `docs/proxy_setup.md` — guia técnico completo: motivação (soft-blocks por IP de datacenter), formatos de `PROXY_URL`, tabela de provedores por custo/eficácia, validação de IP via httpx e Playwright, troubleshooting
- [x] `docs/context.md` — diretriz 4.12 registrada; tabela de lojas atualizada; fase 14.6 migrada para refletir mudança de PA API → HTML scraping
- [x] 169/169 testes passando, zero warnings

---

### ✅ Fase 15.1 — Click Tracking via achadinhosbr.com (CONCLUÍDA — 2026-06-22)

**Motivação:** sem dados de cliques, impossível saber quais fontes (Telegram vs Discord) e quais lojas (KaBuM vs Amazon) convertem mais. Decisão de especializar o Discord em eletrônicos precisa de dados reais.

**Implementação:**
- [x] `src/services/tracker.py` — `ClickTracker`: tabelas `tracked_links` e `clicks` no mesmo `deals.db`; `register(affiliate_url)` gera `deal_id = sha256[:12]` e retorna `TRACKER_BASE_URL/{deal_id}`; `log_click(deal_id, source)` registra clique; `get_stats()` agrega por deal e source
- [x] `src/api/app.py` — FastAPI com dois endpoints: `GET /r/{deal_id}?s=tg` → 302 ao link afiliado + loga clique; `GET /stats` → JSON com cliques por deal e canal
- [x] `src/api/__init__.py` — pacote criado
- [x] `src/models.py` — campo `tracked_url: str = ""` adicionado ao `Deal`
- [x] `src/config/settings.py` — `TRACKER_BASE_URL` (padrão vazio = tracking desativado)
- [x] `main.py` — `ClickTracker` inicializado junto ao `DedupFilter`; `deal.tracked_url = tracker.register(deal.affiliate_url)` antes de publicar; `tracker.close()` no shutdown
- [x] `TelegramPublisher` — usa `tracked_url + "?s=tg"` quando disponível
- [x] `DiscordPublisher` — usa `tracked_url + "?s=dc"` quando disponível
- [x] `fastapi>=0.138.0` e `uvicorn[standard]>=0.49.0` adicionados via `uv add`
- [x] 189/189 testes passando

**Como rodar o servidor de tracking:** ver `docs/tracking_setup.md` — inclui configuração de DNS, Nginx/Caddy, SSL e systemd.
O bot e a API compartilham o mesmo `deals.db` — rodam no mesmo servidor.

**Configuração no `.env`:**
```
TRACKER_BASE_URL=https://achadinhosbr.com/r
```
Deixar vazio desativa o tracking; publishers voltam a usar `affiliate_url` diretamente.

**Dados capturados por clique:** `deal_id`, `source` (tg/dc), `clicked_at` (UTC ISO).

---

### 🔲 Fase 15.2 — API REST de Deals (Este Repositório)
- [ ] Endpoint `GET /deals` — lista deals ativos com paginação, filtro por loja/categoria/desconto mínimo
- [ ] Endpoint `GET /deals/{deal_id}` — deal individual com histórico de preço
- [ ] Autenticação simples (API key no header) para proteger endpoints de stats/admin
- [ ] Dashboard de analytics: cliques por fonte, CTR por loja, deals mais clicados

**Direcionamento estratégico:** Este repositório funciona como Engine de Mineração e API provedora de dados. O Frontend Web e o Aplicativo Mobile serão desenvolvidos em repositórios separados e independentes que consomem esta API.

---

### 🔲 Fase 16 — Ecossistema Externo (Novos Repositórios Separáveis)
- [ ] Planejar o desenvolvimento de um novo projeto/repositório para a Plataforma Web (Frontend em Next.js/React, inspirado em catálogo de vendas, otimizado para SEO) que consome a API JSON deste backend.
- [ ] Planejar o desenvolvimento de um novo projeto/repositório para o Aplicativo Android nativo ou híbrido (focado em notificações push em tempo real de bugs e promoções), consumindo os mesmos endpoints unificados.

**Direcionamento estratégico:** O objetivo de longo prazo é ser a infraestrutura que alimenta múltiplos clientes externos — não apenas publishers de redes sociais. Cada cliente externo é um projeto independente que integra via API REST (Fase 15).

---

## 6. Convenções de Atualização deste Arquivo

- **Ao concluir uma fase:** Mover o item de `🔲` para `✅` e adicionar a data de conclusão.
- **Ao tomar uma nova decisão de design:** Adicionar em "Diretrizes de Design" com a motivação.
- **Ao adicionar uma dependência:** Atualizar a tabela da seção 2.
- **Ao mudar a estrutura de pastas:** Atualizar o mapa na seção 3.
