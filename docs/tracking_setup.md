# Setup de Click Tracking — achadinhosbr.com

O módulo de tracking é uma API FastAPI que roda no mesmo servidor do bot.
Quando alguém clica num link do canal, passa por `achadinhosbr.com/r/{deal_id}`
antes de chegar ao link afiliado — registrando clique, canal de origem e timestamp.

---

## 1. DNS

No painel do seu registrador de domínio (Registro.br, Hostinger, Cloudflare, etc.),
adicione **dois registros A** apontando para o IP do seu servidor:

| Tipo | Nome | Valor | TTL |
|------|------|-------|-----|
| A | `@` | `<IP_DO_SERVIDOR>` | 300 |
| A | `www` | `<IP_DO_SERVIDOR>` | 300 |

Para descobrir o IP do servidor:
```bash
curl -s ifconfig.me
```

> **Propagação:** mudanças de DNS levam até 24h para propagar globalmente,
> mas em geral ficam visíveis em 5–30 minutos com TTL 300.

---

## 2. Reverse Proxy com Nginx + SSL

O FastAPI roda na porta 8000 internamente. O Nginx recebe o tráfego externo
nas portas 80/443 e redireciona para o processo local.

### 2.1 Instalar Nginx e Certbot

```bash
sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx
```

### 2.2 Configurar o virtual host

Crie o arquivo `/etc/nginx/sites-available/achadinhosbr`:

```nginx
server {
    listen 80;
    server_name achadinhosbr.com www.achadinhosbr.com;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}
```

Ative e recarregue:
```bash
sudo ln -s /etc/nginx/sites-available/achadinhosbr /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 2.3 Emitir certificado SSL (HTTPS)

```bash
sudo certbot --nginx -d achadinhosbr.com -d www.achadinhosbr.com
```

O Certbot edita automaticamente o nginx.conf para adicionar HTTPS e redirecionar
HTTP → HTTPS. Renovação automática já vem configurada via systemd timer.

---

## 3. Rodar a API de Tracking

### Opção A — systemd (recomendado para produção)

Crie `/etc/systemd/system/achadinhos-tracker.service`:

```ini
[Unit]
Description=Achadinhos Click Tracker API
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/deals-bot
EnvironmentFile=/home/ubuntu/deals-bot/.env
ExecStart=/home/ubuntu/deals-bot/.venv/bin/uvicorn src.api.app:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Ative e inicie:
```bash
sudo systemctl enable achadinhos-tracker
sudo systemctl start achadinhos-tracker
sudo systemctl status achadinhos-tracker
```

### Opção B — Docker Compose (se o bot já roda em container)

Adicione ao `docker-compose.yml`:

```yaml
  tracker:
    build: .
    command: uvicorn src.api.app:app --host 0.0.0.0 --port 8000
    env_file: .env
    volumes:
      - ./data:/app/data        # compartilha o mesmo deals.db
    restart: unless-stopped
    # não expõe a porta 8000 externamente — o Nginx acessa via rede interna
```

E ajuste o nginx para `proxy_pass http://tracker:8000;` (nome do serviço Docker).

---

## 4. Configuração no `.env`

```env
# URL base do servidor de tracking — sem barra no final
TRACKER_BASE_URL=https://achadinhosbr.com/r
```

Com isso configurado, o bot começa a gerar links rastreados automaticamente.
Sem essa variável (ou em branco), os publishers usam `affiliate_url` diretamente —
sem impacto em testes ou desenvolvimento local.

---

## 5. Validar o setup

```bash
# 1. Verificar se a API está respondendo localmente
curl -s http://127.0.0.1:8000/stats

# 2. Verificar via domínio público (após DNS propagar)
curl -si https://achadinhosbr.com/stats

# 3. Simular um clique (deal_id qualquer para testar 404)
curl -si https://achadinhosbr.com/r/abc123?s=tg
# Esperado: 404 {"error": "link não encontrado"}

# 4. Após o bot rodar um ciclo, pegar um deal_id real e testar o redirect
curl -si "https://achadinhosbr.com/r/<deal_id>?s=tg"
# Esperado: 302 Location: https://www.amazon.com.br/dp/...?tag=...
```

---

## 6. Endpoint de stats

```
GET https://achadinhosbr.com/stats
```

Retorna JSON com cliques agrupados por deal e canal:

```json
[
  { "deal_id": "a3f1c8b2e490", "url": "https://www.amazon.com.br/dp/B0ABC/...", "source": "tg", "clicks": 42 },
  { "deal_id": "a3f1c8b2e490", "url": "https://www.amazon.com.br/dp/B0ABC/...", "source": "dc", "clicks": 18 },
  { "deal_id": "9d2e7a0f1b3c", "url": "https://www.kabum.com.br/produto/...", "source": "tg", "clicks": 31 }
]
```

**Parâmetro `source`:**
| Valor | Origem |
|-------|--------|
| `tg` | Telegram |
| `dc` | Discord |

---

## 7. Alternativa: Caddy (mais simples, HTTPS automático)

Se preferir não lidar com Certbot manualmente, o Caddy obtém e renova SSL sozinho:

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy
```

`/etc/caddy/Caddyfile`:
```
achadinhosbr.com {
    reverse_proxy 127.0.0.1:8000
}
```

```bash
sudo systemctl reload caddy
```

Caddy obtém o certificado Let's Encrypt automaticamente na primeira requisição.
