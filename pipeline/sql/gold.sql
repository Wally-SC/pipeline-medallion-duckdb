-- GOLD: tabelas agregadas, prontas para consumo (BI, relatórios).
CREATE SCHEMA IF NOT EXISTS gold;

CREATE OR REPLACE TABLE gold.receita_diaria AS
SELECT
    data_venda,
    COUNT(*)           AS vendas,
    SUM(quantidade)    AS itens,
    SUM(valor_total)   AS receita
FROM silver.vendas
GROUP BY data_venda
ORDER BY data_venda;

CREATE OR REPLACE TABLE gold.top_produtos AS
SELECT
    produto,
    SUM(quantidade)  AS unidades,
    SUM(valor_total) AS receita,
    RANK() OVER (ORDER BY SUM(valor_total) DESC) AS ranking
FROM silver.vendas
GROUP BY produto
ORDER BY ranking;

CREATE OR REPLACE TABLE gold.receita_categoria_canal AS
SELECT
    categoria,
    canal,
    COUNT(*)         AS vendas,
    SUM(valor_total) AS receita,
    ROUND(100.0 * SUM(valor_total) / SUM(SUM(valor_total)) OVER (), 2) AS pct_receita
FROM silver.vendas
GROUP BY categoria, canal
ORDER BY receita DESC;
