import os
import django
import pandas as pd

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestao_vendas.settings')
django.setup()

from django.contrib.auth.models import User

# Caminho do arquivo
arquivo = 'temp_import.xlsx'

df = pd.read_excel(arquivo)

# Encontrar a coluna de vendedor (aceitar variações)
col_vendedor = None
for col in df.columns:
    if col.strip().lower() == 'vendedor':
        col_vendedor = col
        break
if not col_vendedor:
    print('Coluna de vendedor não encontrada.')
    exit()

# Usernames únicos na planilha
usernames_planilha = set(df[col_vendedor].astype(str).str.strip())
# Usernames cadastrados no sistema
usernames_sistema = set(User.objects.values_list('username', flat=True))

nao_encontrados = usernames_planilha - usernames_sistema

if nao_encontrados:
    print('Usernames de vendedores que NÃO existem no sistema:')
    for nome in nao_encontrados:
        print('-', nome)
else:
    print('Todos os vendedores da planilha existem no sistema!') 