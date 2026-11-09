from __future__ import annotations

from pathlib import Path

import duckdb

SQL_DIR = Path(__file__).parent / "sql"


def _executar_arquivo_sql(con: duckdb.DuckDBPyConnection, nome: str) -> None:
    texto = (SQL_DIR / nome).read_text(encoding="utf-8")
    # separa por ';' ao final de linha; os scripts não têm ';' dentro de strings
    for comando in (c.strip() for c in texto.split(";\n")):
        sem_comentarios = "\n".join(l for l in comando.splitlines() if not l.strip().startswith("--")).strip()
        if sem_comentarios:
            con.execute(sem_comentarios)


def carregar_bronze(con: duckdb.DuckDBPyConnection, csv_path: str | Path) -> None:
    """BRONZE: cópia fiel do arquivo (tudo como texto) + metadados de ingestão. Sem limpeza."""
    csv_path = Path(csv_path)
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    con.execute(
        """
        CREATE OR REPLACE TABLE bronze.vendas AS
        SELECT
            row_number() OVER () AS linha,
            *,
            ?                    AS arquivo_origem,
            current_timestamp    AS ingerido_em
        FROM read_csv(?, header = true, all_varchar = true)
        """,
        [csv_path.name, str(csv_path)],
    )


def construir_silver(con: duckdb.DuckDBPyConnection) -> None:
    _executar_arquivo_sql(con, "silver.sql")


def construir_gold(con: duckdb.DuckDBPyConnection) -> None:
    _executar_arquivo_sql(con, "gold.sql")


def _escalar(con: duckdb.DuckDBPyConnection, consulta: str) -> int:
    return int(con.execute(consulta).fetchone()[0])


def metricas(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    bronze = _escalar(con, "SELECT COUNT(*) FROM bronze.vendas")
    silver = _escalar(con, "SELECT COUNT(*) FROM silver.vendas")
    rejeitadas = _escalar(con, "SELECT COUNT(*) FROM silver.vendas_rejeitadas")
    return {
        "linhas_bronze": bronze,
        "linhas_silver": silver,
        "rejeitadas": rejeitadas,
        "duplicadas_removidas": bronze - silver - rejeitadas,
    }


def rodar(csv_path: str | Path, db_path: str | Path = ":memory:") -> tuple[duckdb.DuckDBPyConnection, dict[str, int]]:
    """Executa bronze -> silver -> gold e devolve a conexão aberta e as métricas."""
    con = duckdb.connect(str(db_path))
    carregar_bronze(con, csv_path)
    construir_silver(con)
    construir_gold(con)
    return con, metricas(con)
