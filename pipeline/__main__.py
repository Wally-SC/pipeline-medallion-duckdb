from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.executar import rodar
from pipeline.gerar_dados import gravar_csv


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline", description="Pipeline medalhão (bronze/silver/gold) com DuckDB.")
    sub = parser.add_subparsers(dest="comando", required=True)

    gerar = sub.add_parser("gerar", help="gera um CSV de vendas sujo")
    gerar.add_argument("--linhas", type=int, default=5000)
    gerar.add_argument("--semente", type=int, default=42)
    gerar.add_argument("--saida", type=Path, default=Path("dados/vendas_raw.csv"))

    exe = sub.add_parser("executar", help="roda bronze -> silver -> gold")
    exe.add_argument("--csv", type=Path, default=Path("dados/vendas_raw.csv"))
    exe.add_argument("--db", type=Path, default=Path("dados/warehouse.duckdb"))

    args = parser.parse_args(argv)

    if args.comando == "gerar":
        total = gravar_csv(args.saida, args.linhas, args.semente)
        print(f"{total} linhas gravadas em {args.saida}")
        return 0

    args.db.parent.mkdir(parents=True, exist_ok=True)
    con, m = rodar(args.csv, args.db)
    print("Qualidade:")
    for chave, valor in m.items():
        print(f"  {chave:<22} {valor:>8}")
    print("\nMotivos de rejeição:")
    for motivo, qtd in con.execute(
        "SELECT motivo_rejeicao, COUNT(*) FROM silver.vendas_rejeitadas GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall():
        print(f"  {motivo:<22} {qtd:>8}")
    print("\nTop 5 produtos por receita:")
    for produto, unidades, receita, ranking in con.execute(
        "SELECT produto, unidades, receita, ranking FROM gold.top_produtos ORDER BY ranking LIMIT 5"
    ).fetchall():
        print(f"  {ranking}. {produto:<20} {unidades:>6} un   R$ {receita:>12,.2f}")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
