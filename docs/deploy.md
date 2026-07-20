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
CORS_ORIGINS=https://achadinhosbr.com
# API_BIND fica em 127.0.0.1: quem fala com a internet é o Caddy (passo 2).
# Publicar a 8000 daria um caminho em HTTP puro contornando o certificado.
```

```bash
docker compose up -d --build
docker compose logs -f deals-bot      # acompanhar o primeiro ciclo
curl localhost:8000/health            # {"status":"ok"}
```

---

## 2. HTTPS com Let's Encrypt

O Caddy emite e **renova** o certificado sozinho. Não há certbot nem cron —
mas a ordem importa: o Let's Encrypt precisa confirmar que você controla o
domínio, então DNS e portas têm que estar prontos **antes** de subir o Caddy.

### 2.0 Tornar o IP reservado (antes de apontar o DNS)

O IP que a Oracle atribui na criação da instância é **efêmero**: muda se a
máquina for parada e iniciada. Como o domínio e o certificado vão depender
dele, converta para reservado **antes** de configurar o DNS — senão um
restart derruba o site e invalida a validação do Let's Encrypt.

Console → **Networking** → **IP Management** → **Reserved public IPs** →
`Reserve public IP address`. Depois, na instância: **Attached VNICs** →
clique na VNIC → **IPv4 Addresses** → editar o IP público → trocar de
*Ephemeral* para *Reserved*.

Confirme que o IP continua o mesmo antes de seguir.

### 2.1 Apontar o subdomínio

No painel do seu domínio, criar um registro:

| Tipo | Nome | Valor |
|---|---|---|
| A | `api` | IP público da VM |

Esperar propagar e **confirmar** antes de seguir:

```bash
dig +short api.achadinhosbr.com     # tem que devolver o IP da VM
```

Se ainda não resolver, aguarde. Subir o Caddy antes disso gasta tentativas
no limite do Let's Encrypt (5 validações falhas por hora).

### 2.2 Abrir as portas 80 e 443

A Oracle bloqueia em **dois** lugares independentes — errar um é a causa mais
comum de "abri a porta e não conecta":

1. **Security List da VCN** (console Oracle → Networking → Virtual Cloud
   Networks → sua VCN → Security Lists → Default): adicionar regras de
   ingresso, Source `0.0.0.0/0`, TCP, portas **80** e **443**.
2. **Firewall da instância** (dentro da VM):
   ```bash
   sudo iptables -I INPUT -p tcp --dport 80  -j ACCEPT
   sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
   sudo netfilter-persistent save    # senão as regras somem no reboot
   ```

A porta 80 é obrigatória mesmo que o site só use HTTPS: é por ela que o
Let's Encrypt faz a validação (desafio HTTP-01).

### 2.3 Configurar e subir

No `.env`:

```env
API_DOMAIN=api.achadinhosbr.com
ACME_EMAIL=seu@email.com
```

```bash
docker compose --profile https up -d
docker compose logs -f caddy
```

No log, o sucesso aparece como `certificate obtained successfully`. A emissão
leva alguns segundos.

### 2.4 Verificar

```bash
curl https://api.achadinhosbr.com/health          # {"status":"ok"}
curl -I https://api.achadinhosbr.com/health       # HTTP/2 200
```

Sem `-k` em nenhum dos dois: se precisar ignorar o certificado, ele não está
válido de verdade.

### Se falhar

| Sintoma | Causa provável |
|---|---|
| `no such host` / timeout | DNS ainda não propagou — confira com `dig` |
| Caddy trava em "obtaining certificate" | Porta 80 fechada em um dos dois firewalls |
| `too many failed authorizations` | Limite do Let's Encrypt; espere 1h antes de tentar de novo |
| Certificado inválido no navegador | `API_DOMAIN` diferente do domínio acessado |

O certificado fica no volume `caddy_data`. **Não apague esse volume** — cada
reemissão consome o limite semanal do Let's Encrypt (50 certificados por
domínio por semana).

---

## 3. Vercel

Importar o repositório `Caspiom/AchadinhosBr` e configurar as variáveis de
ambiente (Settings → Environment Variables):

| Variável | Valor |
|---|---|
| `API_URL` | `https://api.achadinhosbr.com` |
| `API_TOKEN` | o mesmo valor do `.env` da VM |

Sem prefixo `NEXT_PUBLIC_`: são lidas só no servidor. Com o prefixo, o token
iria para o JavaScript do navegador.

Depois, apontar `achadinhosbr.com` para a Vercel (Settings → Domains). O
arquivo `CNAME` no repositório é do GitHub Pages e deixa de ter efeito.

---

## 4. Operação

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

- **Backups fora da VM**: hoje ficam no mesmo disco do banco.
- **Magalu e Shopee** seguem bloqueados por anti-bot; ver `docs/proxy_setup.md`.
