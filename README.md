# Sistema de Gestão Operacional de Vendas

Sistema desenvolvido para gerenciamento de vendas e consignações de motocicletas, com foco em proporcionar controle operacional eficiente e geração de contratos automatizada.

## Funcionalidades

- **Gestão de Vendas**: Registro completo de atendimentos e vendas de veículos
- **Gestão de Consignações**: Controle de motocicletas recebidas em consignação, com valores, prazos e comissões
- **Geração de Contratos**: Emissão de diversos modelos de contratos com dados preenchidos automaticamente
- **Dashboard**: Visualização de estatísticas e indicadores de desempenho
- **Ranking de Vendedores**: Acompanhamento do desempenho da equipe de vendas
- **Relatórios Gerenciais**: Resumos e análises para tomada de decisão

## Tecnologias

- Django 5.2.1
- Python 3.13
- Bootstrap 5
- SQLite (banco de dados)

## Recursos Recentes

- Integração de consignações vendidas na lista geral de vendas
- Cálculo automático de valores por extenso nos contratos
- Suporte para número de motor, chassi e detalhes adicionais dos veículos
- Filtros avançados estilo Excel para busca de informações

## Instalação

1. Clone o repositório
```bash
git clone https://github.com/vinicius-lier/gestaovendas.git
```

2. Crie um ambiente virtual e instale as dependências
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

3. Execute as migrações
```bash
python manage.py migrate
```

4. Inicie o servidor
```bash
python manage.py runserver
```

5. Acesse o sistema em http://127.0.0.1:8000/

## Licença

Este projeto é proprietário e de uso exclusivo da Prado Motors. 