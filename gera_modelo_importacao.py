import pandas as pd

colunas = [
    'nome_cliente',
    'contato',
    'origem',
    'modelo_interesse',
    'forma_pagamento',
    'status',
    'observacoes',
    'data_atendimento',
    'vendedor',
]

df = pd.DataFrame(columns=colunas)
df.to_excel('modelo_importacao_vendas.xlsx', index=False)
print('Modelo de importação criado: modelo_importacao_vendas.xlsx') 