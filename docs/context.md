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

| Biblioteca | Versão Pinada | Responsabilidade |
|---|---|---|
| `httpx` | 0.27.0 | Cliente HTTP async para o scraper |
| `beautifulsoup4` | 4.12.3 | Parsing de HTML das páginas de ofertas |
| `lxml` | 5.2.2 | Parser rápido usado como backend do bs4 |
| `python-telegram-bot` | 21.3 | Interface com a Telegram Bot API (async/v20+) |
| `APScheduler` | 3.10.4 | Agendamento do loop de scraping (cron-like) |
| `python-dotenv` | 1.0.1 | Carregamento de variáveis de ambiente via `.env` |
| `loguru` | 0.7.2 | Logging estruturado com rotação de arquivos |
| `tenacity` | 8.3.0 | Retries declarativos com backoff exponencial |
| `sqlite3` | built-in | Filtro de duplicidade (dedup) — sem dependência externa |
| `pytest` + `pytest-asyncio` | 8.2.2 / 0.23.7 | Testes unitários e assíncronos |

**Nota sobre Playwright:** A dependência `playwright` está preparada na arquitetura (via `BaseScraper`) mas **não está no `requirements.txt`** do MVP. Adicionar apenas quando o scraper-alvo exigir JavaScript.

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
├── .env                        ← Variáveis reais (no .gitignore, NUNCA commitado)
├── .env.example                ← Template de variáveis (commitado)
├── requirements.txt
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

```python
@dataclass
class Deal:
    title: str
    url: str                # URL original do produto
    affiliate_url: str      # URL convertida (preenchida pelo AffiliateService)
    price: float            # Preço atual
    old_price: float | None # Preço antigo (None se não disponível)
    discount_pct: int | None# Calculado automaticamente
    image_url: str | None
    source: str             # Ex: "pelando", "amazon", "mock"
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

---

## 5. Estado Atual e Próximos Passos

### ✅ Fase 1 — Estrutura Fundacional (CONCLUÍDA)
- [x] Estrutura de pastas criada (`src/`, `data/`, `logs/`, `docs/`)
- [x] `requirements.txt` com todas as dependências pinadas
- [x] `.env.example` documentado por categoria (Telegram, Afiliados, Scraper, DB, Logs)
- [x] `.gitignore` configurado (protege `.env`, `deals.db`, logs, caches)
- [x] `src/config/settings.py` carregando e tipando todas as variáveis de ambiente
- [x] `docs/context.md` criado (este arquivo)

---

### 🔲 Fase 2 — Utilitários e Filtro de Duplicidade (PRÓXIMA)

**Escopo exato:**

| Arquivo | O que implementar |
|---|---|
| `src/utils/logger.py` | Configurar `loguru` com sink para arquivo (`logs/bot.log`) com rotação diária e sink para `stdout`. Nível controlado por `settings.LOG_LEVEL`. |
| `src/utils/retry.py` | Criar decorator `telegram_retry` usando `tenacity`: 3 tentativas, `wait_exponential(min=2, max=30)`, logar cada tentativa falha. |
| `src/services/dedup_filter.py` | Classe `DedupFilter`: inicializa o SQLite, cria tabela `seen_deals(url_hash, seen_at)`, métodos `is_new(deal) -> bool` e `mark_seen(deal)`, limpeza de TTL no `__init__`. |

**Critério de conclusão da Fase 2:** Os três arquivos implementados e um teste rápido (pode ser um `if __name__ == "__main__"` ou `pytest`) confirmando que o dedup filtra corretamente um deal repetido.

---

### 🔲 Fase 3 — Scrapers

**Escopo:**
- `src/scrapers/base_scraper.py`: ABC com método abstrato `fetch()` e o dataclass `Deal`.
- `src/scrapers/pelando_scraper.py`: Implementação concreta usando `httpx` + `bs4` para raspar o feed público do Pelando.com.br. Filtrar por `MIN_DISCOUNT_PERCENT`.

---

### 🔲 Fase 4 — Serviços de Afiliado e Telegram

**Escopo:**
- `src/services/affiliate.py`: Função `convert(url: str) -> str` com lógica mockada para o MVP. Preparar a estrutura de `if "amazon" in url` / `if "magalu" in url` para futuras integrações reais.
- `src/services/telegram_poster.py`: Formatar card com `HTML parse_mode` (título em negrito, preço em destaque, % de desconto, botão inline com link de afiliado). Aplicar retry e rate limiting.

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
