import os
import django
import pandas as pd
from datetime import datetime

# Configurar o ambiente Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestao_operacional_vendas.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import Venda

# Caminho para o arquivo Excel
excel_file = 'dados/importe_geral.xlsx'

# Ler a planilha
df = pd.read_excel(excel_file)

# Iterar sobre as linhas da planilha
for index, row in df.iterrows():
    try:
        # Obter ou criar o vendedor
        username = row['vendedor']  # Ajuste para o nome da coluna de vendedor
        vendedor, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': f"{username}@example.com",
                'password': 'senha123'
            }
        )

        # Criar a venda
        venda = Venda.objects.create(
            vendedor=vendedor,
            data=row['data'],  # Ajuste para o nome da coluna de data
            valor=row['valor'],  # Ajuste para o nome da coluna de valor
            quantidade_atendimentos=row['atendimentos'],  # Ajuste para o nome da coluna de atendimentos
            observacoes=row.get('observacoes', '')  # Ajuste para o nome da coluna de observações
        )
        print(f"Venda importada: {venda.data} - {venda.vendedor.username} - R$ {venda.valor}")

    except Exception as e:
        print(f"Erro ao importar linha {index + 2}: {str(e)}")

print("Importação concluída!") 