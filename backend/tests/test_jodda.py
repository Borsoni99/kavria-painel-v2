"""Sincronização com a Jodda (carga, incremental, resumos) e os dados da TV multicanal."""
from datetime import timedelta

import httpx
import respx
from sqlalchemy import func, select

from app.config import TZ
from app.db import SessionLocal
from app.finance.tv_data import tv_data
from app.models import JoddaSnapshot, MonthlyGoal, OrderLine
from app.sources.jodda.sync import refresh_summaries, sync_orders
from app.state import get_state
from app.utils import now_utc
from tests.conftest import API

TODAY = now_utc().astimezone(TZ).date()


def line(numero: str, mk: str = "Mercado Livre", sku: str = "SKU-A", total: float = 100.0, lucro: float = 30.0,
         status: str = "Aprovado", upd: str = "2026-11-25T10:00:00Z", day=TODAY, hour: int = 10) -> dict:
    return {"numero_loja": numero, "numero": f"erp-{numero}", "data": day.isoformat(),
            "data_hora": f"{day.isoformat()}T{hour:02d}:00:00-03:00", "atualizado_em": upd,
            "marketplace": mk, "conta": "KAVRIA", "status": status, "sku": sku, "descricao": f"Produto {sku}",
            "quantidade": 1, "total": total, "comissao": 10.0, "frete": 5.0, "desconto": 0, "custo": 40.0,
            "imposto": 4.0, "lucro": lucro, "margem_pct": 30.0, "repasse": 85.0, "logistica": "fulfillment", "uf": "SP"}


def page(rows: list[dict], total: int | None = None) -> httpx.Response:
    return httpx.Response(200, json={"pedidos": rows, "total": len(rows) if total is None else total, "pagina": 1})


@respx.mock
async def test_first_sync_backfills_then_only_changes():
    first = [line("1"), line("2", mk="Shopee", total=50, lucro=20, upd="2026-11-25T11:00:00Z")]
    route = respx.get(f"{API}/pedidos").mock(side_effect=[
        page(first),  # carga histórica (mês atual)
        page([line("1", status="Cancelado", upd="2026-11-25T12:00:00Z"), line("3", upd="2026-11-25T12:00:00Z")]),
    ])
    r1 = await sync_orders()
    assert r1["novas"] == 2 and await get_state("orders_cursor") == "2026-11-25T11:00:00Z"
    assert "inicio=" in str(route.calls[0].request.url)

    r2 = await sync_orders()  # incremental: só o que mudou desde o cursor
    assert "atualizados_desde=2026-11-25T11%3A00%3A00Z" in str(route.calls[1].request.url)
    assert (r2["novas"], r2["atualizadas"]) == (1, 1)
    async with SessionLocal() as s:
        n = (await s.execute(select(func.count()).select_from(OrderLine))).scalar_one()
        cancelled = (await s.execute(select(OrderLine).where(OrderLine.order_key == "1"))).scalar_one()
    assert n == 3 and cancelled.status == "Cancelado" and cancelled.total_c == 10000
    assert await get_state("orders_cursor") == "2026-11-25T12:00:00Z"


@respx.mock
async def test_pagination_reads_all_pages():
    rows = [line(str(i)) for i in range(150)]
    respx.get(f"{API}/pedidos").mock(side_effect=[page(rows[:100], total=150), page(rows[100:], total=150)])
    assert (await sync_orders())["novas"] == 150


@respx.mock
async def test_rate_limit_waits_and_retries():
    respx.get(f"{API}/pedidos").mock(side_effect=[
        httpx.Response(429, json={"error": "limite", "code": "RATE_LIMITED"}, headers={"Retry-After": "1"}),
        page([line("9")]),
    ])
    assert (await sync_orders())["novas"] == 1


@respx.mock
async def test_tv_data_combines_jodda_kpis_and_channels():
    respx.get(f"{API}/pedidos").mock(return_value=page([
        line("1", total=100, lucro=30), line("2", total=200, lucro=50, hour=11),
        line("3", mk="Shopee", total=50, lucro=20, hour=12),
        line("4", mk="Shopee", total=80, lucro=10, status="Cancelado", hour=13),
    ]))
    respx.get(f"{API}/vendas/resumo").mock(return_value=httpx.Response(200, json={
        "faturamento": 350.0, "pedidos": 3, "ticket_medio": 116.67, "unidades": 3, "lucro": 90.0,
        "margem_pct": 28.57, "imposto": 12.0, "previsao_mes": 1000.0,
        "ads": {"ml": 10.0, "shopee": 0, "amazon": 0, "margem_pos_ads_pct": 25.71},
        "por_marketplace": [], "serie_diaria": [], "top_produtos": [], "avisos": []}))
    respx.get(f"{API}/ads/resumo").mock(return_value=httpx.Response(200, json={"totais": {
        "gasto_total": 10.0, "receita_ads_total": 80.0, "acos_pct": 12.5, "roas": 8.0, "participacao_ads_pct": 2.86,
        "por_marketplace": [{"marketplace": "Mercado Livre", "gasto": 10.0}]}}))
    await sync_orders()
    await refresh_summaries()
    async with SessionLocal() as s:
        s.add(MonthlyGoal(month=TODAY.strftime("%Y-%m"), goal_c=100000))
        await s.commit()
        assert (await s.execute(select(func.count()).select_from(JoddaSnapshot))).scalar_one() == 3
        d = await tv_data(s, now_utc())

    t = d["totals"]
    assert t["faturamento_c"] == 35000 and t["lucro_c"] == 9000 and t["lucro_antes_ads_c"] == 10000
    assert t["margem_bp"] == 2857 and t["margem_pos_ads_bp"] == 2571 and t["cancelados_mes"] == 1
    assert d["goal"]["atingido_bp"] == 3500 and d["goal"]["projecao_c"] == 100000
    ch = {c["marketplace"]: c for c in d["channels"]}
    assert ch["Mercado Livre"]["faturamento_c"] == 30000 and ch["Mercado Livre"]["pedidos"] == 2
    assert ch["Shopee"]["faturamento_c"] == 5000  # cancelado fora
    assert ch["Mercado Livre"]["ads_c"] == 1000
    assert [f["marketplace"] for f in d["feed"]][:2] == ["Shopee", "Mercado Livre"]  # mais recente primeiro
    assert d["rolling"][-1]["por_canal"]["Mercado Livre"] == 30000
    assert d["ads"]["roas_x100"] == 800 and d["ads"]["tacos_bp"] == 286


async def test_tv_snapshot_requires_key():
    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.get("/api/tv/snapshot")).status_code == 401
        ok = await c.get("/api/tv/snapshot?key=chave-tv")
    assert ok.status_code == 200 and "channels" in ok.json()
