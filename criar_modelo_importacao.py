import os
import django
import pandas as pd

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestao_vendas.settings')
django.setup()

# Criar DataFrame com as colunas necessárias
df = pd.DataFrame(columns=[
    'data_atendimento',
    'nome_cliente',
    'contato',
    'origem',
    'modelo_interesse',
    'forma_pagamento',
    'status',
    'vendedor',
    'observacoes'
])

# Adicionar exemplo
df.loc[0] = [
    '2025-05-10',  # data_atendimento
    'João Silva',   # nome_cliente
    '(11) 99999-9999',  # contato
    'Site',        # origem
    'Modelo X',    # modelo_interesse
    'À Vista',     # forma_pagamento
    'PENDENTE',    # status
    'Pedro',       # vendedor (username do vendedor)
    'Cliente interessado no modelo'  # observacoes
]

# Criar diretório se não existir
os.makedirs('core/static/core', exist_ok=True)

# Salvar arquivo
df.to_excel('core/static/core/modelo_importacao_vendas.xlsx', index=False)

print('Modelo de importação criado com sucesso!') 