-- SILVER: dados tipados, padronizados, validados e sem duplicatas.
CREATE SCHEMA IF NOT EXISTS silver;

-- 1) Converte tipos e normaliza texto. Valores que não convertem viram NULL (TRY_*),
--    em vez de derrubar o pipeline inteiro.
CREATE OR REPLACE TABLE silver.vendas_tipadas AS
SELECT
    linha,
    NULLIF(TRIM(id_venda), '')                                              AS id_venda,
    COALESCE(
        TRY_STRPTIME(TRIM(data_venda), '%Y-%m-%d'),
        TRY_STRPTIME(TRIM(data_venda), '%d/%m/%Y')
    )::DATE                                                                 AS data_venda,
    COALESCE(NULLIF(TRIM(cliente_id), ''), 'NAO_INFORMADO')                 AS cliente_id,
    NULLIF(UPPER(TRIM(produto)), '')                                        AS produto,
    NULLIF(UPPER(TRIM(categoria)), '')                                      AS categoria,
    TRY_CAST(TRIM(quantidade) AS INTEGER)                                   AS quantidade,
    TRY_CAST(REPLACE(TRIM(preco_unitario), ',', '.') AS DECIMAL(12, 2))     AS preco_unitario,
    LOWER(TRIM(canal))                                                      AS canal
FROM bronze.vendas;

-- 2) Aplica as regras de qualidade; cada linha ganha no máximo um motivo de rejeição.
CREATE OR REPLACE TABLE silver.vendas_validacao AS
SELECT
    *,
    CASE
        WHEN id_venda IS NULL                          THEN 'id_venda ausente'
        WHEN data_venda IS NULL                        THEN 'data invalida'
        WHEN produto IS NULL                           THEN 'produto ausente'
        WHEN quantidade IS NULL OR quantidade <= 0     THEN 'quantidade invalida'
        WHEN preco_unitario IS NULL OR preco_unitario <= 0 THEN 'preco invalido'
    END AS motivo_rejeicao
FROM silver.vendas_tipadas;

-- 3) Quarentena: linhas rejeitadas ficam guardadas com o motivo, nada é descartado em silêncio.
CREATE OR REPLACE TABLE silver.vendas_rejeitadas AS
SELECT linha, id_venda, motivo_rejeicao
FROM silver.vendas_validacao
WHERE motivo_rejeicao IS NOT NULL
ORDER BY linha;

-- 4) Tabela final: só linhas válidas, mantendo a primeira ocorrência de cada id_venda.
CREATE OR REPLACE TABLE silver.vendas AS
SELECT
    id_venda, data_venda, cliente_id, produto, categoria,
    quantidade, preco_unitario, canal,
    quantidade * preco_unitario AS valor_total
FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY id_venda ORDER BY linha) AS ocorrencia
    FROM silver.vendas_validacao
    WHERE motivo_rejeicao IS NULL
)
WHERE ocorrencia = 1;
