from decimal import Decimal

import pytest

from pipeline.executar import rodar
from pipeline.gerar_dados import CABECALHO, gerar_linhas, gravar_csv

CSV_PEQUENO = """id_venda,data_venda,cliente_id,produto,categoria,quantidade,preco_unitario,canal
V1,2026-03-01,C1,  Mouse Sem Fio ,perifericos,2,"89,90",Site
V2,02/03/2026,,teclado,perifericos,1,249.90,app
V2,02/03/2026,,teclado,perifericos,1,249.90,app
V3,2026-03-02,C2,Cabo HDMI,acessorios,-1,29.90,loja
V4,ontem,C3,Cabo HDMI,acessorios,1,29.90,loja
V5,2026-03-03,C4,Cabo HDMI,acessorios,1,0,loja
V6,2026-03-03,C5,Cabo HDMI,acessorios,abc,29.90,loja
,2026-03-03,C6,Cabo HDMI,acessorios,1,29.90,loja
V7,2026-03-03,C7,mouse sem fio,perifericos,3,89.90,SITE
"""


@pytest.fixture
def pequeno(tmp_path):
    caminho = tmp_path / "vendas.csv"
    caminho.write_text(CSV_PEQUENO, encoding="utf-8")
    con, metricas = rodar(caminho)
    yield con, metricas
    con.close()


def test_bronze_e_copia_fiel_em_texto(pequeno):
    con, _ = pequeno
    assert con.execute("SELECT COUNT(*) FROM bronze.vendas").fetchone()[0] == 9
    # nada foi limpo: o preço com vírgula e a data inválida continuam como vieram
    assert con.execute("SELECT preco_unitario FROM bronze.vendas WHERE linha = 1").fetchone()[0] == "89,90"
    assert con.execute("SELECT data_venda FROM bronze.vendas WHERE id_venda = 'V4'").fetchone()[0] == "ontem"
    assert con.execute("SELECT DISTINCT arquivo_origem FROM bronze.vendas").fetchone()[0] == "vendas.csv"


def test_metricas_de_qualidade(pequeno):
    _, m = pequeno
    assert m == {"linhas_bronze": 9, "linhas_silver": 3, "rejeitadas": 5, "duplicadas_removidas": 1}


def test_silver_padroniza_valores(pequeno):
    con, _ = pequeno
    linhas = con.execute(
        "SELECT id_venda, data_venda::VARCHAR, cliente_id, produto, quantidade, preco_unitario, canal "
        "FROM silver.vendas ORDER BY id_venda"
    ).fetchall()
    assert linhas == [
        ("V1", "2026-03-01", "C1", "MOUSE SEM FIO", 2, Decimal("89.90"), "site"),
        ("V2", "2026-03-02", "NAO_INFORMADO", "TECLADO", 1, Decimal("249.90"), "app"),
        ("V7", "2026-03-03", "C7", "MOUSE SEM FIO", 3, Decimal("89.90"), "site"),
    ]


def test_rejeicoes_guardam_motivo(pequeno):
    con, _ = pequeno
    motivos = dict(
        con.execute("SELECT COALESCE(id_venda, '(vazio)'), motivo_rejeicao FROM silver.vendas_rejeitadas").fetchall()
    )
    assert motivos == {
        "V3": "quantidade invalida",
        "V4": "data invalida",
        "V5": "preco invalido",
        "V6": "quantidade invalida",
        "(vazio)": "id_venda ausente",
    }


def test_gold_agrega_corretamente(pequeno):
    con, _ = pequeno
    receita_total = con.execute("SELECT SUM(receita) FROM gold.receita_diaria").fetchone()[0]
    assert receita_total == Decimal("2") * Decimal("89.90") + Decimal("249.90") + Decimal("3") * Decimal("89.90")

    ranking = con.execute("SELECT produto, ranking FROM gold.top_produtos ORDER BY ranking").fetchall()
    assert ranking[0][0] == "MOUSE SEM FIO"  # 5 un x 89,90 = 449,50 > 249,90

    pct = con.execute("SELECT SUM(pct_receita) FROM gold.receita_categoria_canal").fetchone()[0]
    assert abs(pct - 100) < Decimal("0.1")


def test_gerador_e_reproduzivel_e_realmente_sujo():
    a = gerar_linhas(500, semente=7)
    assert a == gerar_linhas(500, semente=7)
    assert a != gerar_linhas(500, semente=8)
    assert len(a) == 500 + int(500 * 0.04)  # linhas base + duplicatas injetadas
    assert all(len(l) == len(CABECALHO) for l in a)


def test_pipeline_completo_conserva_linhas(tmp_path):
    csv = tmp_path / "grande.csv"
    total = gravar_csv(csv, 3000, semente=1)
    con, m = rodar(csv)
    try:
        assert m["linhas_bronze"] == total
        assert m["linhas_silver"] + m["rejeitadas"] + m["duplicadas_removidas"] == total
        assert m["duplicadas_removidas"] > 0 and m["rejeitadas"] > 0

        # invariantes da camada silver
        assert con.execute("SELECT COUNT(*) - COUNT(DISTINCT id_venda) FROM silver.vendas").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM silver.vendas WHERE quantidade <= 0 OR preco_unitario <= 0").fetchone()[0] == 0
        # gold fecha com silver
        assert (
            con.execute("SELECT SUM(valor_total) FROM silver.vendas").fetchone()[0]
            == con.execute("SELECT SUM(receita) FROM gold.receita_diaria").fetchone()[0]
        )
    finally:
        con.close()


def test_rerodar_e_idempotente(tmp_path):
    csv = tmp_path / "v.csv"
    gravar_csv(csv, 500, semente=3)
    db = tmp_path / "w.duckdb"
    con1, m1 = rodar(csv, db)
    con1.close()
    con2, m2 = rodar(csv, db)  # CREATE OR REPLACE: mesma entrada, mesmo resultado
    con2.close()
    assert m1 == m2
