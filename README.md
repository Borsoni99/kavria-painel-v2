# Painel KAVRIA v2 — multicanal

TV e admin com **Mercado Livre, Shopee, Amazon e TikTok Shop** juntos, alimentados pela
**API da Jodda AI** (que já calcula comissão, frete, custo, imposto e lucro de cada pedido).
O painel v1 (só Mercado Livre, integração direta com o ML) continua separado, em painel.kavria.com.br.

## Como funciona
- **Pedidos:** carga histórica (desde `BACKFILL_FROM`) e, depois, a cada minuto, só os pedidos novos ou
  alterados (`GET /v1/pedidos?atualizados_desde=`). Ficam guardados em SQLite (`backend/data/kavria2.db`).
- **Resumos** (a cada 2 min): vendas do mês e de hoje (`/v1/vendas/resumo`, mesmos números do painel da
  Jodda: lucro já com Ads, previsão do mês) e Ads do mês (`/v1/ads/resumo`).
- **TV** (`/tv?key=TV_ACCESS_KEY`): meta, hoje, margem antes/depois do Ads, Ads, canais, diário
  empilhado por canal, últimas vendas e mais vendidos. Atualiza ao vivo (SSE) e toca som a cada venda.
- **Admin** (`/admin`): status da integração e metas mensais.
- A Jodda só tem dados a partir de **novembro/2026**; o histórico cresce daqui para frente.
- Limite da Jodda: 60 chamadas/minuto por chave (o cliente espaça as chamadas e respeita o Retry-After).

## Rodar localmente
```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -c constraints.txt -r requirements-dev.txt
copy ..\.env.example ..\.env   # preencha JODDA_API_KEY, APP_SECRET, ADMIN_PASSWORD, TV_ACCESS_KEY
.venv\Scripts\python -m app.cli migrate
.venv\Scripts\python -m app.cli sync        # carga + resumos
.venv\Scripts\python -m uvicorn app.main:app --port 8001
cd ..\frontend; npm ci; npm run build
```
Testes: `cd backend; .venv\Scripts\python -m pytest -q`

## Produção (mesmo servidor Lightsail do v1)
- Pasta `/opt/kavria2`, container `kavria2-app` na rede `kavria_default` do v1. O **Caddy do v1** atende
  `painel2.kavria.com.br` e encaminha para `kavria2-app:8000` (bloco no `deploy/Caddyfile` do v1).
- DNS: registro **A** `painel2` → `54.232.124.83`, **nuvem cinza** (DNS only) na Cloudflare.
- Publicar: `.\deploy\aws\publicar.ps1 -Mensagem "..."` (commit + push + deploy; o banco do servidor não é tocado).
