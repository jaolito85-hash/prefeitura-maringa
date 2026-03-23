-- 009: Adicionar campo descricao à tabela ocorrencias
-- Separa a descrição do cidadão do campo endereço

ALTER TABLE ocorrencias ADD COLUMN IF NOT EXISTS descricao TEXT;

-- Migrar dados existentes: onde o endereco parece ser texto de relato, mover pra descricao
UPDATE ocorrencias
SET descricao = endereco,
    endereco = '',
    endereco_normalizado = ''
WHERE endereco != ''
  AND endereco NOT LIKE 'GPS:%'
  AND endereco NOT LIKE '%Rua%'
  AND endereco NOT LIKE '%Avenida%'
  AND endereco NOT LIKE '%Av.%'
  AND endereco NOT LIKE '%R.%'
  AND (
    endereco LIKE '%arvore%'
    OR endereco LIKE '%caiu%'
    OR endereco LIKE '%enchente%'
    OR endereco LIKE '%buraco%'
    OR endereco LIKE '%incendio%'
    OR endereco LIKE '%alagamento%'
    OR endereco LIKE '%deslizamento%'
    OR LENGTH(endereco) > 100
  );
