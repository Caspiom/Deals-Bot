# Deploy — bot/API na Oracle, site na Vercel

## Por que separado

O bot roda até 2 Chromium por ciclo e reserva 1.5 GB. Numa VM de 1 OCPU/3 GB,
somar o SSR do Next significaria disputar CPU justamente enquanto um ciclo de
scraping está rodando — o site fica lento na hora errada. Separando, a Vercel
ainda resolve SSL, CDN e deploy, e o site continua de pé se o bot cair (a
página mostra "não foi possível carregar" em vez de quebrar).

Vercel **não** serve para o backend: o sistema de arquivos é efêmero (o SQLite
não teria onde persistir), Chromium não cabe no limite de 250 MB por função, e
não existe processo de longa duração para o scheduler.

## Quem fala com quem

```
navegador ──► Vercel (Next, SSR) ──► API na VM Oracle ──► SQLite
     │                                      ▲
     └──────── /r/{id} (clique do Telegram) ┘
```

O navegador **nunca** fala com a API: quem busca dados é o Server Component.
Por isso o token vive só no servidor da Vercel e o CORS quase não importa —
ele é imposto pelo navegador.

Exceção: `/r/{id}`, o redirect de clique vindo do Telegram, é público por
definição.

---

## 1. VM Oracle

```bash
# Docker (Ubuntu)
sudo apt update && sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER && newgrp docker

git clone git@github.com:Caspiom/Deals-Bot.git && cd Deals-Bot
cp .env.example .env   # preencher os segredos
```

No `.env`, para produção:

```env
API_TOKEN=<gere com: openssl rand -hex 32>
API_BIND=0.0.0.0                      # expõe a API para a Vercel alcançar
CORS_ORIGINS=https://achadinhosbr.com
```

```bash
docker compose up -d --build
docker compose logs -f deals-bot      # acompanhar o primeiro ciclo
curl localhost:8000/health            # {"status":"ok"}
```

### Abrir a porta

A Oracle bloqueia tudo por padrão, em **dois** lugares — errar um é a causa
mais comum de "não conecta":

1. **Security List da VCN** (console Oracle → Networking → VCN → Security
   Lists): regra de ingresso TCP para a porta 8000.
2. **Firewall da instância**:
   ```bash
   sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT
   sudo netfilter-persistent save    # senão a regra some no reboot
   ```

---

## 2. Vercel

Importar o repositório `Caspiom/AchadinhosBr` e configurar as variáveis de
ambiente (Settings → Environment Variables):

| Variável | Valor |
|---|---|
| `API_URL` | `http://<IP-da-VM>:8000` |
| `API_TOKEN` | o mesmo valor do `.env` da VM |

Sem prefixo `NEXT_PUBLIC_`: são lidas só no servidor. Com o prefixo, o token
iria para o JavaScript do navegador.

Depois, apontar `achadinhosbr.com` para a Vercel (Settings → Domains). O
arquivo `CNAME` no repositório é do GitHub Pages e deixa de ter efeito.

---

## Operação

```bash
docker compose logs -f --tail=100     # acompanhar
docker compose restart api            # reiniciar só a API
uv run python scripts/backup_db.py    # backup sob demanda
uv run python scripts/reclassificar_catalogo.py --dry   # após mexer no classificador
```

O backup diário roda sozinho (`BACKUP_HOUR_UTC`, padrão 06h UTC = 03h em
Brasília) e mantém os `BACKUP_KEEP` mais recentes em `data/backups/`.

**Os backups ficam no mesmo disco do banco.** Isso protege contra corrupção
lógica, não contra perda da VM — vale copiar o mais recente para fora
periodicamente.

## Pendências conhecidas

- **HTTPS na API**: hoje o tráfego Vercel→VM vai em HTTP. O token protege o
  acesso, mas não o transporte. Um proxy (Caddy resolve o certificado sozinho)
  na frente da API fecharia isso.
- **Magalu e Shopee** seguem bloqueados por anti-bot; ver `docs/proxy_setup.md`.
