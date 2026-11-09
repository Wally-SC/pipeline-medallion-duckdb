"""Gera um CSV de vendas SUJO e reproduzível (mesma semente, mesmo arquivo).

Problemas injetados de propósito, para o pipeline ter o que limpar:
duplicatas, datas em dois formatos (e algumas inválidas), preço com vírgula,
nomes de produto com caixa/espaços inconsistentes, cliente ausente,
quantidade negativa/zero/texto e preço vazio ou zero.
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

CATALOGO = [
    ("Teclado Mecânico", "perifericos", 249.90),
    ("Mouse Sem Fio", "perifericos", 89.90),
    ("Monitor 24pol", "monitores", 799.00),
    ("Monitor 27pol", "monitores", 1199.00),
    ("Cabo HDMI", "acessorios", 29.90),
    ("Hub USB-C", "acessorios", 139.90),
    ("Webcam Full HD", "perifericos", 219.00),
    ("Headset Gamer", "audio", 329.90),
    ("Caixa de Som", "audio", 159.90),
    ("Notebook 14pol", "computadores", 3599.00),
]
CANAIS = ["site", "app", "loja", "marketplace"]
CABECALHO = ["id_venda", "data_venda", "cliente_id", "produto", "categoria", "quantidade", "preco_unitario", "canal"]


def _sujar_nome(nome: str, rng: random.Random) -> str:
    variante = rng.choice(["igual", "maiusculo", "minusculo", "espacos"])
    if variante == "maiusculo":
        return nome.upper()
    if variante == "minusculo":
        return nome.lower()
    if variante == "espacos":
        return f"  {nome} "
    return nome


def gerar_linhas(n: int, semente: int = 42) -> list[list[str]]:
    rng = random.Random(semente)
    inicio = date(2026, 1, 1)
    linhas: list[list[str]] = []

    for i in range(1, n + 1):
        produto, categoria, preco_base = rng.choice(CATALOGO)
        dia = inicio + timedelta(days=rng.randrange(0, 181))
        preco = round(preco_base * rng.uniform(0.9, 1.1), 2)

        data = dia.isoformat()
        if rng.random() < 0.05:
            data = dia.strftime("%d/%m/%Y")
        if rng.random() < 0.01:
            data = rng.choice(["31/02/2026", "ontem", "2026-13-40"])

        preco_txt = f"{preco:.2f}"
        if rng.random() < 0.30:
            preco_txt = preco_txt.replace(".", ",")
        if rng.random() < 0.01:
            preco_txt = rng.choice(["", "0", "0,00"])

        quantidade = str(rng.choices([1, 2, 3, 4, 5], weights=[50, 25, 12, 8, 5])[0])
        if rng.random() < 0.02:
            quantidade = rng.choice(["-1", "0", "abc"])

        cliente = f"C{rng.randrange(1, max(2, n // 5)):05d}"
        if rng.random() < 0.03:
            cliente = ""

        linhas.append(
            [
                f"V{i:07d}",
                data,
                cliente,
                _sujar_nome(produto, rng),
                categoria,
                quantidade,
                preco_txt,
                rng.choice(CANAIS),
            ]
        )

    # duplicatas: reaparecem mais adiante no arquivo (como num reenvio de lote)
    for _ in range(int(n * 0.04)):
        original = rng.choice(linhas[: max(1, len(linhas))])
        linhas.insert(rng.randrange(len(linhas) + 1), list(original))
    return linhas


def gravar_csv(caminho: str | Path, n: int, semente: int = 42) -> int:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    linhas = gerar_linhas(n, semente)
    with open(caminho, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(CABECALHO)
        escritor.writerows(linhas)
    return len(linhas)
