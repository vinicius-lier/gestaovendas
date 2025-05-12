import os
import django
import pandas as pd
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestao_vendas.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import Venda

# Caminho para o arquivo Excel
df = pd.read_excel('dados/importe geral.xlsx')

for index, row in df.iterrows():
    try:
        # Vendedor: linhas 119 a 131 (índices 118 a 130) sempre 'Adria', demais conforme coluna
        if 118 <= index <= 130:
            vendedor = User.objects.get(username='Adria')
        else:
            vendedor_nome = str(row['Vendedor']).strip()
            try:
                vendedor = User.objects.get(username=vendedor_nome)
            except User.DoesNotExist:
                vendedor = None
        # Garantir formato da data
        data_raw = row['Data do Atendimento']
        if pd.isnull(data_raw):
            data_atendimento = None
        elif isinstance(data_raw, str):
            data_atendimento = data_raw[:10]
        else:
            data_atendimento = data_raw.strftime('%Y-%m-%d')
        venda = Venda.objects.create(
            nome_cliente=row['Nome do Cliente'],
            contato=row['Contato'],
            origem=row['Origem'],
            modelo_interesse=row['Modelo de Interesse'],
            forma_pagamento=row['Forma de Pagamento'],
            status=row['Status'],
            observacoes=row.get('Observações', ''),
            data_atendimento=data_atendimento,
            vendedor=vendedor
        )
        print(f"Venda importada: {venda.nome_cliente} - {venda.vendedor}")
    except Exception as e:
        print(f"Erro ao importar linha {index+2}: {e}")

print('Importação concluída!') 