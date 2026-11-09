# pipeline-medallion-duckdb

Pipeline de dados em **arquitetura medalhão** (bronze → silver → gold) usando
**DuckDB** e SQL. Roda local, sem servidor, e reproduz em pequena escala o fluxo
de uma ingestão real: dado bruto sujo entra, dado confiável e agregado sai.

```
CSV sujo ──► BRONZE ──► SILVER ──► GOLD
             (cópia fiel)  (limpo, tipado,   (agregados para
                            sem duplicatas)   BI e relatórios)
                              └─► vendas_rejeitadas (quarentena com motivo)
```

## As camadas

| Camada | O que faz | Tabelas |
|---|---|---|
| **bronze** | Copia o arquivo como veio (tudo texto) e acrescenta metadados de ingestão (`linha`, `arquivo_origem`, `ingerido_em`). Não limpa nada, para permitir reprocessar. | `bronze.vendas` |
| **silver** | Converte tipos com `TRY_CAST`/`TRY_STRPTIME`, padroniza texto, aceita dois formatos de data e preço com vírgula, aplica regras de qualidade, remove duplicatas (mantém a primeira ocorrência). | `silver.vendas`, `silver.vendas_rejeitadas` |
| **gold** | Agregações prontas para consumo. | `gold.receita_diaria`, `gold.top_produtos`, `gold.receita_categoria_canal` |

Linhas inválidas **não são descartadas em silêncio**: vão para `silver.vendas_rejeitadas`
com o motivo (`data invalida`, `quantidade invalida`, `preco invalido`, ...).

## Como rodar

```bash
pip install -r requirements.txt
python -m pipeline gerar --linhas 5000        # cria dados/vendas_raw.csv (sujo, reproduzível)
python -m pipeline executar                   # roda as 3 camadas e grava dados/warehouse.duckdb
```

Saída de exemplo (5.000 linhas base):

```
Qualidade:
  linhas_bronze              5200
  linhas_silver              4804
  rejeitadas                  207
  duplicadas_removidas        189

Motivos de rejeição:
  quantidade invalida          99
  preco invalido               57
  data invalida                51

Top 5 produtos por receita:
  1. NOTEBOOK 14POL          911 un   R$ 3,267,320.73
  ...
```

`duplicadas_removidas` conta duplicatas entre linhas válidas; uma duplicata de linha
inválida entra em `rejeitadas`. Por isso é menor que o total de duplicatas injetadas.

Para consultar o resultado com o shell do DuckDB ou Python:

```python
import duckdb
duckdb.connect("dados/warehouse.duckdb").sql("SELECT * FROM gold.receita_diaria LIMIT 10").show()
```

## Dados de entrada

`pipeline/gerar_dados.py` gera vendas fictícias com problemas injetados de propósito:
duplicatas, datas em dois formatos (e algumas inválidas), preço com vírgula, nomes de
produto com caixa e espaços inconsistentes, cliente ausente, quantidade negativa/zero/texto
e preço vazio ou zero. A mesma semente gera sempre o mesmo arquivo.

## Decisões de projeto

- **SQL em arquivos** (`pipeline/sql/`), não em strings espalhadas pelo Python: fácil de revisar e versionar.
- **`TRY_*` em vez de `CAST`:** um valor ruim vira `NULL` e cai na regra de qualidade, em vez de derrubar o job.
- **Idempotência:** `CREATE OR REPLACE TABLE` em todas as camadas; rodar duas vezes dá o mesmo resultado.
- **Conservação de linhas:** os testes verificam `bronze = silver + rejeitadas + duplicadas`.

## Testes

```bash
pytest
```

Cobrem um CSV pequeno com resultado exato esperado (valores, motivos de rejeição, ranking),
o gerador, a conservação de linhas num volume maior e a idempotência.
