"""Linha de comando do painel v2. Rode a partir de backend/:  .venv\\Scripts\\python -m app.cli <comando>

Comandos:
  gen-secret                 gera um valor para APP_SECRET / TV_ACCESS_KEY
  migrate                    aplica as migrações do banco
  conta                      testa a chave da Jodda (GET /v1/conta)
  backfill [--from D] [--to D]  carga histórica de pedidos (padrão: BACKFILL_FROM até hoje)
  sync                       pedidos novos/alterados + resumos do mês, de hoje e de Ads
  status                     linhas de pedido por canal e última sincronização
  backup                     copia o banco para data/backups (guarda 30)
"""
import argparse
import asyncio
import json
import logging
from datetime import date

from app.config import TZ, get_settings
from app.utils import now_utc


async def _run(args) -> None:
    from app.sources.jodda.client import jodda

    try:
        if args.cmd == "conta":
            print(json.dumps(await jodda.get("/conta"), ensure_ascii=False, indent=1))
        elif args.cmd == "backfill":
            from app.sources.jodda.sync import backfill

            d_from = date.fromisoformat(args.date_from or get_settings().backfill_from)
            d_to = date.fromisoformat(args.date_to) if args.date_to else now_utc().astimezone(TZ).date()
            print(await backfill(d_from, d_to))
        elif args.cmd == "sync":
            from app.sources.jodda.sync import refresh_summaries, sync_orders

            print(await sync_orders())
            print(await refresh_summaries())
        elif args.cmd == "status":
            from sqlalchemy import func, select

            from app.db import SessionLocal
            from app.models import OrderLine
            from app.state import get_state

            async with SessionLocal() as s:
                rows = (await s.execute(select(OrderLine.marketplace, OrderLine.status, func.count(),
                                               func.sum(OrderLine.total_c)).group_by(OrderLine.marketplace, OrderLine.status))).all()
            for mk, st, n, tot in rows:
                print(f"{mk:15} {st:10} {n:6} linhas  R$ {(tot or 0) / 100:,.2f}")
            print("pedidos:", await get_state("orders_last"))
            print("resumos:", await get_state("summaries_last"))
    finally:
        await jodda.aclose()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("gen-secret")
    sub.add_parser("migrate")
    sub.add_parser("conta")
    b = sub.add_parser("backfill")
    b.add_argument("--from", dest="date_from")
    b.add_argument("--to", dest="date_to")
    sub.add_parser("sync")
    sub.add_parser("status")
    sub.add_parser("backup")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.cmd == "gen-secret":
        from app.security import new_secret

        print(new_secret())
    elif args.cmd == "migrate":
        from app.migrate import run_migrations

        run_migrations()
        print("Banco atualizado.")
    elif args.cmd == "backup":
        from app.backup import backup_db

        print(f"Backup gravado em {backup_db()}")
    else:
        asyncio.run(_run(args))


if __name__ == "__main__":
    main()
