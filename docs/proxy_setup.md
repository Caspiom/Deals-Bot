# Configuração de Proxy — Deals Bot

## Por que usar proxy?

O bot raspa lojas diretamente via Playwright (navegador headless) e httpx. Quando hospedado em produção num VPS europeu ou americano (Hetzner, Fly.io, Oracle), o IP de saída é de um datacenter internacional — um perfil que sistemas anti-bot como Cloudflare, Akamai e DataDome reconhecem e bloqueiam silenciosamente.

**Sintomas de soft-block sem proxy em produção:**

| Loja | Sintoma observado |
|---|---|
| Magazine Luiza | `nenhum link de produto encontrado` mesmo com DOM carregado |
| Shopee | 0 cards extraídos consistentemente |
| Amazon | Página de CAPTCHA em vez de `/deals` |
| Mercado Livre | Cards extraídos mas preços ausentes (DOM sanitizado) |

**Proxy residencial BR** resolve porque o IP de saída pertence a um provedor de internet doméstico brasileiro — indistinguível de um usuário real navegando de São Paulo. O cookie de sessão, locale e User-Agent já são configurados pelo scraper; o proxy completa o fingerprint de rede.

---

## Variável de ambiente

```env
# .env
PROXY_URL=http://usuario:senha@host:porta
```

O valor é repassado automaticamente para:
- **Playwright**: `browser.launch(proxy={"server": PROXY_URL})`
- **httpx**: `AsyncClient(proxy=PROXY_URL)`

Deixe em branco (`PROXY_URL=`) para conexão direta (padrão).

---

## Formatos aceitos

```env
# HTTP/HTTPS (mais comum, funciona com Playwright e httpx)
PROXY_URL=http://usuario:senha@br.proxy.exemplo.com:8080

# SOCKS5 (mais anônimo, suportado por ambos)
PROXY_URL=socks5://usuario:senha@br.proxy.exemplo.com:1080

# Sem autenticação (IP allowlist)
PROXY_URL=http://br.proxy.exemplo.com:8080
```

---

## Onde comprar (do mais barato ao mais eficaz)

### 1. Proxy de Datacenter Compartilhado — ~$3-8/mês

Suficiente para volume baixo (< 100 req/hora). IP fixo de datacenter — pode ser bloqueado por Shopee/Magalu se detectado.

- [Webshare](https://webshare.io) — plano free com 10 proxies, pago a partir de $3/mês
- [Proxy-Cheap](https://proxy-cheap.com) — ~$4/mês por IP BR dedicado

```env
PROXY_URL=http://seu_usuario:sua_senha@proxy.webshare.io:80
```

### 2. Proxy de Datacenter Dedicado — ~$15-30/mês

IP exclusivo, menos chance de estar em blocklists. Boa escolha para rodar 24/7.

- [BrightData Datacenter](https://brightdata.com) — IP BR fixo
- [Smartproxy](https://smartproxy.com) — pool de IPs BR

### 3. Proxy Residencial Rotativo — ~$15-40/GB

IP real de usuário doméstico (Tim, Claro, Vivo). Praticamente impossível de bloquear. Pago por tráfego consumido.

- [BrightData Residential](https://brightdata.com) — maior pool, ~$8.4/GB
- [Smartproxy Residential](https://smartproxy.com) — ~$7/GB com IPs BR
- [IPRoyal](https://iproyal.com) — mais barato, ~$3/GB

**Para o bot Deals Bot:** proxy residencial rotativo é o mais eficaz mas tem custo variável. Comece com datacenter e migre para residencial se ainda houver bloqueios.

---

## Como validar que o proxy está funcionando

### 1. Verificar IP de saída via httpx

```bash
uv run python -c "
import asyncio, httpx, os
from dotenv import load_dotenv
load_dotenv()

async def check():
    proxy = os.getenv('PROXY_URL') or None
    async with httpx.AsyncClient(proxy=proxy, timeout=10) as c:
        r = await c.get('https://api.ipify.org?format=json')
        print('IP de saída:', r.json()['ip'])

asyncio.run(check())
"
```

Se o proxy estiver configurado corretamente, o IP exibido deve ser diferente do IP do seu servidor e, idealmente, brasileiro.

### 2. Verificar localização do IP

Cole o IP de saída em [ipinfo.io](https://ipinfo.io) e confirme:
- `country: BR`
- `org: AS` de uma operadora doméstica (Claro, Tim, Vivo, NET) para residencial
- `org: AS` de um provedor de proxy para datacenter

### 3. Testar navegação Playwright via proxy

```bash
uv run python - <<'EOF'
import asyncio
from playwright.async_api import async_playwright
import os
from dotenv import load_dotenv
load_dotenv()

async def check():
    proxy_url = os.getenv("PROXY_URL", "")
    async with async_playwright() as pw:
        kwargs = {"headless": True}
        if proxy_url:
            kwargs["proxy"] = {"server": proxy_url}
        browser = await pw.chromium.launch(**kwargs)
        page = await browser.new_page()
        await page.goto("https://api.ipify.org?format=json")
        content = await page.content()
        print("Conteúdo:", content)
        await browser.close()

asyncio.run(check())
EOF
```

---

## Configuração no Docker Compose

Se você roda o bot via `docker compose up`, adicione a variável no `docker-compose.yml` ou no arquivo `.env` na raiz do projeto (o compose já carrega o `.env` automaticamente):

```env
# .env na raiz do projeto (já no .gitignore)
PROXY_URL=http://usuario:senha@host:porta
```

O `docker-compose.yml` não precisa de mudanças — a variável é lida pelo `python-dotenv` dentro do container.

---

## Troubleshooting

| Sintoma | Causa provável | Solução |
|---|---|---|
| `ProxyError: 407 Proxy Authentication Required` | Credenciais erradas | Verificar usuário e senha no `.env` |
| `ConnectTimeout` | Host/porta errado ou firewall | Verificar host e porta com o provedor |
| IP ainda é o do VPS | `PROXY_URL` em branco ou não carregado | Confirmar que o `.env` foi salvo e o bot reiniciado |
| Loja ainda bloqueia | IP de datacenter detectado | Migrar para proxy residencial |
| `SOCKS5 not supported` (httpx) | httpx precisa de `httpx[socks]` | `uv add httpx[socks]` |
