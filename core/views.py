from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, FormView
from django.urls import reverse_lazy
from django.db.models import Count, Q, Sum, F
from django.contrib.auth.models import User
from .models import Venda, Perfil, Consignacao, AssinaturaDigital, EstoqueMoto, Cliente
from .forms import VendaForm, ConsignacaoForm, ConsignacaoVendaForm, PerfilForm, UsuarioCreateForm, UsuarioUpdateForm, AlterarSenhaForm, EstoqueMotoForm, ClienteForm
import pandas as pd
from django.http import JsonResponse, FileResponse
from django.contrib import messages
from django.conf import settings
import os
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import Group
from django.views.decorators.csrf import csrf_exempt
import json
import decimal

def is_master(user):
    try:
        return user.perfil.tipo == 'master'
    except:
        return False

def is_gerente(user):
    try:
        return user.perfil.tipo in ['master', 'gerente']
    except:
        return False

@login_required
def dashboard(request):
    if is_master(request.user) or is_gerente(request.user):
        vendedor_id = request.GET.get('vendedor')
        vendedores = User.objects.filter(groups__name='vendedores')
        
        # Vendas diretas
        vendas = Venda.objects.all()
        if vendedor_id:
            vendas = vendas.filter(vendedor_id=vendedor_id)
            
        # Consignações vendidas
        consignacoes_vendidas = Consignacao.objects.filter(status='VENDIDO')
        if vendedor_id:
            consignacoes_vendidas = consignacoes_vendidas.filter(vendedor_responsavel_id=vendedor_id)
            
        # Totais
        numero_atendimentos = vendas.count() + consignacoes_vendidas.count()
        numero_fechamentos = vendas.filter(status='VENDIDO').count() + consignacoes_vendidas.count()
        
        # Ranking de vendedores combinando vendas diretas e consignações vendidas
        # Primeiro obtemos as estatísticas de vendas diretas
        ranking_vendas = (
            Venda.objects.values('vendedor__username', 'vendedor_id')
            .annotate(
                total_atendimentos=Count('id'),
                fechamentos=Count('id', filter=Q(status='VENDIDO'))
            )
        )
        
        # Depois obtemos estatísticas de consignações vendidas
        ranking_consignacoes = (
            Consignacao.objects.filter(status='VENDIDO')
            .values('vendedor_responsavel__username', 'vendedor_responsavel_id')
            .annotate(
                total_atendimentos=Count('id'),
                fechamentos=Count('id')
            )
        )
        
        # Combinamos os dois rankings em um dicionário
        ranking_combinado = {}
        
        # Adicionar dados de vendas diretas
        for item in ranking_vendas:
            vendedor_id = item['vendedor_id']
            vendedor_nome = item['vendedor__username']
            
            if vendedor_id not in ranking_combinado:
                ranking_combinado[vendedor_id] = {
                    'vendedor_id': vendedor_id,
                    'vendedor__username': vendedor_nome,
                    'total_atendimentos': 0,
                    'fechamentos': 0
                }
                
            ranking_combinado[vendedor_id]['total_atendimentos'] += item['total_atendimentos']
            ranking_combinado[vendedor_id]['fechamentos'] += item['fechamentos']
        
        # Adicionar dados de consignações vendidas
        for item in ranking_consignacoes:
            vendedor_id = item['vendedor_responsavel_id']
            vendedor_nome = item['vendedor_responsavel__username']
            
            if vendedor_id not in ranking_combinado:
                ranking_combinado[vendedor_id] = {
                    'vendedor_id': vendedor_id,
                    'vendedor__username': vendedor_nome,
                    'total_atendimentos': 0,
                    'fechamentos': 0
                }
                
            ranking_combinado[vendedor_id]['total_atendimentos'] += item['total_atendimentos']
            ranking_combinado[vendedor_id]['fechamentos'] += item['fechamentos']
        
        # Convertemos o dicionário para lista e ordenamos
        ranking = sorted(
            ranking_combinado.values(),
            key=lambda x: (-x['fechamentos'], -x['total_atendimentos'])
        )
        
        context = {
            'numero_atendimentos': numero_atendimentos,
            'numero_fechamentos': numero_fechamentos,
            'vendas': vendas,
            'vendedores': vendedores,
            'vendedor_selecionado': int(vendedor_id) if vendedor_id else None,
            'ranking': ranking,
            'is_gerente': True,  # Flag para controlar exibição no template
        }
    else:
        vendas = Venda.objects.filter(vendedor=request.user)
        consignacoes_vendidas = Consignacao.objects.filter(vendedor_responsavel=request.user, status='VENDIDO')
        
        numero_atendimentos = vendas.count() + consignacoes_vendidas.count()
        numero_fechamentos = vendas.filter(status='VENDIDO').count() + consignacoes_vendidas.count()
        
        context = {
            'numero_atendimentos': numero_atendimentos,
            'numero_fechamentos': numero_fechamentos,
            'vendas': vendas,
            'is_gerente': False,
        }
    return render(request, 'core/dashboard.html', context)

@login_required
def dashboard_vendas(request):
    hoje = timezone.now().date()
    
    # Obter filtros de mês e ano dos parâmetros GET, ou usar todos se não informados
    mes = request.GET.get('mes')
    ano = request.GET.get('ano')
    
    # Se não tiver filtros, pegue todas as vendas, caso contrário filtre por mês/ano
    if mes and ano:
        mes_atual = int(mes)
        ano_atual = int(ano)
        vendas = Venda.objects.filter(data_atendimento__year=ano_atual, data_atendimento__month=mes_atual)
    else:
        mes_atual = hoje.month
        ano_atual = hoje.year
        vendas = Venda.objects.exclude(data_atendimento__isnull=True)  # Pega todas as vendas com data
    
    atendimentos = vendas.count()
    vendas_fechadas = vendas.filter(status='VENDIDO')
    total_vendas = vendas_fechadas.count()

    # Como não há campo de valor, ticket médio será apenas o número de vendas
    valor_total = total_vendas
    ticket_medio = total_vendas

    taxa_conversao = (total_vendas / atendimentos * 100) if atendimentos else 0

    # Agrupamentos com tratamento para nulos
    vendas_por_vendedor = vendas_fechadas.values('vendedor__username').annotate(
        qtd=Count('id')
    ).order_by('-qtd')
    
    # Tratar campos nulos para origem
    vendas_por_origem = vendas_fechadas.values('origem').annotate(
        qtd=Count('id')
    )
    # Substituir valores nulos por "Não informado"
    vendas_por_origem = [
        {'origem': v['origem'] if v['origem'] else 'Não informado', 'qtd': v['qtd']} 
        for v in vendas_por_origem
    ]
    
    # Tratar campos nulos para forma_pagamento
    vendas_por_pagamento = vendas_fechadas.values('forma_pagamento').annotate(
        qtd=Count('id')
    )
    # Substituir valores nulos por "Não informado"
    vendas_por_pagamento = [
        {'forma_pagamento': v['forma_pagamento'] if v['forma_pagamento'] else 'Não informado', 'qtd': v['qtd']} 
        for v in vendas_por_pagamento
    ]
    
    vendas_por_status = vendas.values('status').annotate(qtd=Count('id'))
    # Substituir valores nulos por "Não informado"
    vendas_por_status = [
        {'status': v['status'] if v['status'] else 'Não informado', 'qtd': v['qtd']} 
        for v in vendas_por_status
    ]
    
    vendas_por_dia = vendas_fechadas.values('data_atendimento').annotate(qtd=Count('id')).order_by('data_atendimento')

    context = {
        'total_vendas': total_vendas,
        'taxa_conversao': round(taxa_conversao, 2),
        'ticket_medio': round(ticket_medio, 2),
        'vendas_por_vendedor': list(vendas_por_vendedor),
        'vendas_por_origem': vendas_por_origem,
        'vendas_por_pagamento': vendas_por_pagamento,
        'vendas_por_status': vendas_por_status,
        'vendas_por_dia': list(vendas_por_dia),
        'mes_atual': mes_atual,
        'ano_atual': ano_atual,
        'tem_vendas': total_vendas > 0,  # Flag para verificar se há vendas
    }
    
    return render(request, 'core/dashboard_vendas.html', context)

class VendaListView(LoginRequiredMixin, ListView):
    model = Venda
    template_name = 'core/venda_list.html'
    context_object_name = 'vendas'
    paginate_by = 10

    def get_queryset(self):
        # Obtém vendas diretas
        if is_master(self.request.user) or is_gerente(self.request.user):
            queryset = Venda.objects.all().select_related('vendedor')
        else:
            queryset = Venda.objects.filter(vendedor=self.request.user)
        
        # Filtro por vendedor
        vendedor_id = self.request.GET.get('vendedor')
        if vendedor_id and (is_master(self.request.user) or is_gerente(self.request.user)):
            queryset = queryset.filter(vendedor_id=vendedor_id)
        
        # Ordenação
        ordem = self.request.GET.get('ordem', '-data_atendimento')  # Padrão: mais recente primeiro
        if ordem == 'data_asc':
            queryset = queryset.order_by('data_atendimento')
        elif ordem == 'data_desc':
            queryset = queryset.order_by('-data_atendimento')
        elif ordem == 'vendedor_asc':
            queryset = queryset.order_by('vendedor__username')
        elif ordem == 'vendedor_desc':
            queryset = queryset.order_by('-vendedor__username')
        
        # Obter consignações vendidas e convertê-las para objetos tipo Venda
        if is_master(self.request.user) or is_gerente(self.request.user):
            consignacoes_vendidas = Consignacao.objects.filter(status='VENDIDO').select_related('vendedor_responsavel')
            if vendedor_id:
                consignacoes_vendidas = consignacoes_vendidas.filter(vendedor_responsavel_id=vendedor_id)
        else:
            consignacoes_vendidas = Consignacao.objects.filter(
                status='VENDIDO', 
                vendedor_responsavel=self.request.user
            ).select_related('vendedor_responsavel')
        
        # Converter consignações em objetos tipo Venda para exibição unificada
        vendas_lista = list(queryset)
        for consignacao in consignacoes_vendidas:
            venda_virtual = Venda(
                nome_cliente=consignacao.nome_comprador or consignacao.nome_proprietario,
                contato=consignacao.contato_proprietario,
                modelo_interesse=f"{consignacao.marca} {consignacao.modelo}",
                status='VENDIDO',
                data_atendimento=consignacao.data_venda or consignacao.data_entrada,
                vendedor=consignacao.vendedor_responsavel,
                observacoes=f"Venda de consignação: {consignacao.marca} {consignacao.modelo} (#{consignacao.id})"
            )
            venda_virtual.id = f"C{consignacao.id}"  # Prefixo C para identificar consignações
            venda_virtual.is_consignacao = True
            vendas_lista.append(venda_virtual)
        
        # Ordenação manual da lista combinada
        if ordem == 'data_asc':
            vendas_lista.sort(key=lambda x: x.data_atendimento or timezone.now().date())
        elif ordem == 'data_desc' or ordem == '-data_atendimento':
            vendas_lista.sort(key=lambda x: x.data_atendimento or timezone.now().date(), reverse=True)
        elif ordem == 'vendedor_asc':
            vendas_lista.sort(key=lambda x: x.vendedor.username if x.vendedor else '')
        elif ordem == 'vendedor_desc':
            vendas_lista.sort(key=lambda x: x.vendedor.username if x.vendedor else '', reverse=True)
        
        return vendas_lista

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['show_vendedor'] = is_master(self.request.user) or is_gerente(self.request.user)
        
        # Adiciona a ordem atual ao contexto
        context['ordem_atual'] = self.request.GET.get('ordem', '-data_atendimento')
        
        # Adiciona lista de vendedores para o filtro
        if context['show_vendedor']:
            context['vendedores'] = User.objects.filter(groups__name='vendedores')
        
        # Adiciona o vendedor selecionado ao contexto
        vendedor_id = self.request.GET.get('vendedor')
        if vendedor_id:
            vendedor = User.objects.filter(id=vendedor_id).first()
            context['vendedor_selecionado'] = vendedor_id
            context['vendedor_nome'] = vendedor.get_full_name() or vendedor.username if vendedor else ''
        
        return context

class VendaCreateView(LoginRequiredMixin, CreateView):
    model = Venda
    form_class = VendaForm
    template_name = 'core/venda_form.html'
    success_url = reverse_lazy('venda-list')

    def form_valid(self, form):
        form.instance.vendedor = self.request.user
        return super().form_valid(form)

class VendaUpdateView(LoginRequiredMixin, UpdateView):
    model = Venda
    form_class = VendaForm
    template_name = 'core/venda_form.html'
    success_url = reverse_lazy('venda-list')

    def get_queryset(self):
        if is_master(self.request.user) or is_gerente(self.request.user):
            return Venda.objects.all()
        return Venda.objects.filter(vendedor=self.request.user)

class VendaDeleteView(LoginRequiredMixin, DeleteView):
    model = Venda
    template_name = 'core/venda_confirm_delete.html'
    success_url = reverse_lazy('venda-list')

    def get_queryset(self):
        if is_master(self.request.user) or is_gerente(self.request.user):
            return Venda.objects.all()
        return Venda.objects.filter(vendedor=self.request.user)

@login_required
def resumo_gerencial(request):
    if not is_gerente(request.user):
        return redirect('dashboard')
    
    # Obter vendas diretas
    vendas = Venda.objects.all()
    
    # Obter consignações vendidas
    consignacoes = Consignacao.objects.filter(status='VENDIDO')
    
    # Calcular estatísticas para vendas diretas
    vendas_por_vendedor = vendas.values('vendedor__username', 'vendedor_id').annotate(
        total_vendas=Count('id', filter=Q(status='VENDIDO')),
        total_atendimentos=Count('id')
    )
    
    # Calcular estatísticas para consignações vendidas
    consignacoes_por_vendedor = consignacoes.values(
        'vendedor_responsavel__username', 'vendedor_responsavel_id'
    ).annotate(
        total_vendas=Count('id'),
        total_atendimentos=Count('id')
    )
    
    # Combinar estatísticas
    estatisticas_combinadas = {}
    
    # Adicionar dados de vendas diretas
    for item in vendas_por_vendedor:
        vendedor_id = item['vendedor_id']
        vendedor_nome = item['vendedor__username']
        
        if vendedor_id not in estatisticas_combinadas:
            estatisticas_combinadas[vendedor_id] = {
                'vendedor__username': vendedor_nome,
                'vendedor_id': vendedor_id,
                'total_vendas': 0,
                'total_atendimentos': 0
            }
            
        estatisticas_combinadas[vendedor_id]['total_vendas'] += item['total_vendas']
        estatisticas_combinadas[vendedor_id]['total_atendimentos'] += item['total_atendimentos']
    
    # Adicionar dados de consignações vendidas
    for item in consignacoes_por_vendedor:
        vendedor_id = item['vendedor_responsavel_id']
        vendedor_nome = item['vendedor_responsavel__username']
        
        if vendedor_id not in estatisticas_combinadas:
            estatisticas_combinadas[vendedor_id] = {
                'vendedor__username': vendedor_nome,
                'vendedor_id': vendedor_id,
                'total_vendas': 0,
                'total_atendimentos': 0
            }
            
        estatisticas_combinadas[vendedor_id]['total_vendas'] += item['total_vendas']
        estatisticas_combinadas[vendedor_id]['total_atendimentos'] += item['total_atendimentos']
    
    # Converter para lista para exibição na tabela
    vendas_por_vendedor_combinado = list(estatisticas_combinadas.values())
    
    # Ordenar por total de vendas (decrescente)
    vendas_por_vendedor_combinado = sorted(
        vendas_por_vendedor_combinado,
        key=lambda x: (-x['total_vendas'], -x['total_atendimentos'])
    )
    
    context = {
        'vendas_por_vendedor': vendas_por_vendedor_combinado,
    }
    
    return render(request, 'core/resumo_gerencial.html', context)

@login_required
def importar_vendas(request):
    if not (is_master(request.user) or is_gerente(request.user)):
        messages.error(request, 'Você não tem permissão para importar vendas.')
        return redirect('dashboard')
    
    if request.method == 'POST' and request.FILES.get('arquivo'):
        arquivo = request.FILES['arquivo']
        try:
            # Ler o arquivo Excel
            df = pd.read_excel(arquivo)
            
            # Encontrar a coluna de vendedor (aceitar variações)
            col_vendedor = None
            for col in df.columns:
                if col.strip().lower() == 'vendedor':
                    col_vendedor = col
                    break
            if not col_vendedor:
                messages.error(request, 'Coluna de vendedor não encontrada. Certifique-se de que existe uma coluna chamada "vendedor".')
                return redirect('importar-vendas')
            
            # Validar colunas obrigatórias
            colunas_obrigatorias = [
                'data_atendimento', 'nome_cliente', 'contato', 
                'origem', 'modelo_interesse', 'forma_pagamento', 
                'status'
            ]
            for coluna in colunas_obrigatorias:
                if coluna not in df.columns:
                    messages.error(request, f'Coluna obrigatória não encontrada: {coluna}')
                    return redirect('importar-vendas')
            
            # Processar cada linha
            vendas_importadas = 0
            for _, row in df.iterrows():
                try:
                    vendedor_nome = str(row[col_vendedor]).strip()
                    vendedor = User.objects.get(username=vendedor_nome)
                    
                    venda = Venda(
                        data_atendimento=row['data_atendimento'],
                        nome_cliente=row['nome_cliente'],
                        contato=row['contato'],
                        origem=row['origem'],
                        modelo_interesse=row['modelo_interesse'],
                        forma_pagamento=row['forma_pagamento'],
                        status=row['status'],
                        observacoes=row.get('observacoes', ''),
                        vendedor=vendedor
                    )
                    venda.save()
                    vendas_importadas += 1
                except User.DoesNotExist:
                    messages.warning(request, f'Vendedor não encontrado: {row[col_vendedor]}')
                    continue
                except Exception as e:
                    messages.warning(request, f'Erro ao importar linha: {str(e)}')
                    continue
            
            messages.success(request, f'{vendas_importadas} vendas importadas com sucesso!')
            return redirect('dashboard')
            
        except Exception as e:
            messages.error(request, f'Erro ao processar arquivo: {str(e)}')
            return redirect('importar-vendas')
            
    return render(request, 'core/importar_vendas.html')

@login_required
def download_modelo_importacao(request):
    if not (is_master(request.user) or is_gerente(request.user)):
        messages.error(request, 'Você não tem permissão para baixar o modelo.')
        return redirect('dashboard')
    
    file_path = os.path.join(settings.BASE_DIR, 'core', 'static', 'core', 'modelo_importacao_vendas.xlsx')
    return FileResponse(open(file_path, 'rb'), as_attachment=True)

def valor_por_extenso(valor):
    """Converte um valor numérico para texto por extenso em português do Brasil."""
    
    # Trata o valor como decimal para evitar problemas de arredondamento
    valor = decimal.Decimal(str(valor))
    
    # Separa reais e centavos
    reais = int(valor)
    centavos = int((valor - reais) * 100)
    
    # Listas com os nomes dos números
    unidades = ['', 'um', 'dois', 'três', 'quatro', 'cinco', 'seis', 'sete', 'oito', 'nove']
    dezenas = ['', 'dez', 'vinte', 'trinta', 'quarenta', 'cinquenta', 'sessenta', 'setenta', 'oitenta', 'noventa']
    de_11_a_19 = ['', 'onze', 'doze', 'treze', 'quatorze', 'quinze', 'dezesseis', 'dezessete', 'dezoito', 'dezenove']
    centenas = ['', 'cento', 'duzentos', 'trezentos', 'quatrocentos', 'quinhentos', 'seiscentos', 'setecentos', 'oitocentos', 'novecentos']
    milhares = ['', 'mil', 'milhão', 'bilhão', 'trilhão']
    milhares_plural = ['', 'mil', 'milhões', 'bilhões', 'trilhões']
    
    # Função para converter número até 999
    def converter_ate_999(numero):
        if numero == 0:
            return ''
        elif numero == 100:
            return 'cem'
        elif numero < 10:
            return unidades[numero]
        elif numero < 20:
            return de_11_a_19[numero - 10]
        else:
            dezena = dezenas[numero // 10]
            unidade = unidades[numero % 10]
            if unidade:
                return f"{dezena} e {unidade}"
            return dezena
            
    # Função para converter centenas
    def converter_centena(numero):
        if numero == 0:
            return ''
        elif numero == 100:
            return 'cem'
        else:
            centena = centenas[numero // 100]
            resto = numero % 100
            
            if resto == 0:
                return centena
            else:
                resto_str = converter_ate_999(resto)
                return f"{centena} e {resto_str}"
    
    # Se o valor for zero
    if reais == 0 and centavos == 0:
        return 'zero reais'
    
    # Parte dos reais
    texto_reais = ''
    
    if reais > 0:
        # Divide o valor em grupos de 3 dígitos
        grupos = []
        temp = reais
        while temp > 0:
            grupos.append(temp % 1000)
            temp //= 1000
            
        # Converte cada grupo em texto
        textos_grupos = []
        for i, grupo in enumerate(grupos):
            if grupo > 0:
                texto_grupo = converter_centena(grupo)
                
                # Adiciona o sufixo (mil, milhão, etc.)
                if i > 0:
                    if grupo == 1:
                        texto_grupo = f"{texto_grupo} {milhares[i]}"
                    else:
                        texto_grupo = f"{texto_grupo} {milhares_plural[i]}"
                        
                textos_grupos.append(texto_grupo)
        
        # Junta os textos dos grupos
        textos_grupos.reverse()
        
        if len(textos_grupos) == 1:
            texto_reais = textos_grupos[0]
        else:
            texto_reais = " e ".join(textos_grupos)
            # Substituir a última ocorrência de " e " por " e "
            ultima_ocorrencia = texto_reais.rfind(" e ")
            if ultima_ocorrencia != -1 and ultima_ocorrencia != 0:
                texto_reais = texto_reais[:ultima_ocorrencia] + " e " + texto_reais[ultima_ocorrencia + 3:]
    
    # Parte dos centavos
    texto_centavos = ''
    if centavos > 0:
        texto_centavos = converter_ate_999(centavos)
    
    # Monta o texto final
    if reais == 0:
        return f"{texto_centavos} centavos"
    elif reais == 1:
        if centavos == 0:
            return f"{texto_reais} real"
        else:
            return f"{texto_reais} real e {texto_centavos} centavos"
    else:
        if centavos == 0:
            return f"{texto_reais} reais"
        else:
            return f"{texto_reais} reais e {texto_centavos} centavos"

@login_required
def gerar_contrato(request, venda_id, tipo_contrato):
    venda = get_object_or_404(Venda, id=venda_id)
    
    # Verificar se o usuário tem permissão para visualizar esta venda
    if not (is_master(request.user) or is_gerente(request.user)) and venda.vendedor != request.user:
        messages.error(request, 'Você não tem permissão para visualizar este contrato.')
        return redirect('dashboard')
    
    # Data atual formatada
    data_atual = timezone.now().strftime('%d/%m/%Y')
    
    # Valor padrão para a venda (pode ser substituído por um valor real se disponível)
    valor_venda = 50000.00
    
    # Dados base do contrato
    context = {
        'cliente': {
            'nome': venda.nome_cliente or "Nome do Cliente",
            'contato': venda.contato or "Telefone do Cliente",
            'cpf': "000.000.000-00",  # Campo não existe no modelo, usando valor padrão
            'rg': "00.000.000-0",     # Campo não existe no modelo, usando valor padrão
            'endereco': "Endereço do Cliente",  # Campo não existe no modelo, usando valor padrão
            'nacionalidade': 'brasileiro(a)',
            'estado_civil': 'solteiro(a)',
            'profissao': 'profissão',
        },
        'veiculo': {
            'marca': "Honda",  # Campo não existe no modelo, usando valor padrão
            'modelo': venda.modelo_interesse or "Modelo do Veículo",
            'ano': "2023",  # Campo não existe no modelo, usando valor padrão
            'modelo_ano': "2024",  # Campo não existe no modelo, usando valor padrão
            'cor': "Prata",  # Campo não existe no modelo, usando valor padrão
            'chassi': "0000000000000000",  # Campo não existe no modelo, usando valor padrão
            'placa': "AAA-0000",  # Campo não existe no modelo, usando valor padrão
            'renavam': "00000000000",  # Campo não existe no modelo, usando valor padrão
            'km': 0,  # Campo não existe no modelo, usando valor padrão
            'motor': "",  # Campo para número do motor
        },
        'venda': {
            'valor_total': valor_venda,
            'valor_total_extenso': valor_por_extenso(valor_venda),
            'forma_pagamento': venda.forma_pagamento or "À Vista",
            'forma_pagamento_detalhada': "Pagamento à vista via transferência bancária.",  # Campo não existe no modelo, usando valor padrão
            'prazo_entrega': 5,  # Campo não existe no modelo, usando valor padrão
            'data_venda': data_atual,  # Usando a data atual (Now)
            'observacoes': venda.observacoes or "",
        },
        'vendedor': {
            'nome': 'MARKETING PRADO MOTORS',
            'cnpj': '02.968.496/0001-17',
            'endereco': 'Rua Bruno Andrea, 24 - Parque das Palmeiras',
            'cidade': 'Angra dos Reis',
            'estado': 'RJ',
            'cep': '23.906-410',
            'telefone': '(24) 3365-3303',
            'email': 'motorsprado@gmail.com',
        },
        'vendedor_texto_completo': 'Paraty auto zero Ltda., pessoa jurídica de direito privado, inscrita sob CNPJ 02.968.496/0001-17, com sede na Rua Bruno Andrea N° 24 – Parque das palmeiras- Angra dos reis – RJ – CEP: 23.906-410, neste ato representada por Alessandro Correa Barbosa, brasileiro, empresário, portador da carteira de identidade RG: 21.818.188-1, inscrito no CPF: 118.921.797-09.',
        'data_atual': data_atual,
    }
    
    # Adicionar dados específicos para consignação
    if tipo_contrato == 'consignacao':
        context['venda'].update({
            'prazo_consignacao': 30,  # Exemplo: 30 dias
            'comissao': 5,            # Exemplo: 5% de comissão
        })
    
    # Escolher o template baseado no tipo de contrato
    templates = {
        'compra_venda': 'core/contratos_html/contrato_venda.html',
        'consignacao': 'core/contratos_html/contrato_consignacao.html',
        'sem_garantia': 'core/contratos_html/contrato_sem_garantia.html',
        'veiculo_usado': 'core/contratos_html/contrato_veiculo_usado.html',
        'sem_emplacamento': 'core/contratos_html/liberacao_sem_emplacamento.html',
        'sem_intencao': 'core/contratos_html/liberacao_sem_intencao.html',
    }
    
    if tipo_contrato not in templates:
        messages.error(request, 'Tipo de contrato inválido.')
        return redirect('venda-list')
    
    # Verificar se é uma requisição para nova aba
    if request.GET.get('nova_aba'):
        return render(request, templates[tipo_contrato], context)
    
    # Se não for nova aba, renderiza a página com o iframe
    # Cria URL absoluta para garantir que o iframe carregue corretamente
    iframe_url = request.build_absolute_uri(f"{request.path}?nova_aba=true")
    
    return render(request, 'core/contrato_view.html', {
        'contrato_url': iframe_url,
        'tipo_contrato': tipo_contrato
    })

# Views de Consignação
class ConsignacaoListView(LoginRequiredMixin, ListView):
    model = Consignacao
    template_name = 'core/consignacao_list.html'
    context_object_name = 'consignacoes'
    paginate_by = 10

    def get_queryset(self):
        queryset = Consignacao.objects.all().select_related('vendedor_responsavel') if is_master(self.request.user) or is_gerente(self.request.user) else Consignacao.objects.filter(vendedor_responsavel=self.request.user)
        
        # Filtro por status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filtro por vendedor
        vendedor_id = self.request.GET.get('vendedor')
        if vendedor_id and (is_master(self.request.user) or is_gerente(self.request.user)):
            queryset = queryset.filter(vendedor_responsavel_id=vendedor_id)
            
        # Filtros estilo Excel para cada coluna
        # Filtro por marca/modelo
        veiculo = self.request.GET.get('veiculo')
        if veiculo:
            queryset = queryset.filter(Q(marca__icontains=veiculo) | Q(modelo__icontains=veiculo))
            
        # Filtro por proprietário
        proprietario = self.request.GET.get('proprietario')
        if proprietario:
            queryset = queryset.filter(nome_proprietario__icontains=proprietario)
            
        # Filtro por placa
        placa = self.request.GET.get('placa')
        if placa:
            queryset = queryset.filter(placa__icontains=placa)
            
        # Filtro por valores (range)
        valor_min = self.request.GET.get('valor_min')
        valor_max = self.request.GET.get('valor_max')
        if valor_min:
            queryset = queryset.filter(valor_consignacao__gte=float(valor_min))
        if valor_max:
            queryset = queryset.filter(valor_consignacao__lte=float(valor_max))
            
        # Filtro por data de entrada (range)
        data_inicio = self.request.GET.get('data_inicio')
        data_fim = self.request.GET.get('data_fim')
        if data_inicio:
            queryset = queryset.filter(data_entrada__gte=data_inicio)
        if data_fim:
            queryset = queryset.filter(data_entrada__lte=data_fim)
        
        # Ordenação
        ordem = self.request.GET.get('ordem', '-data_entrada')  # Padrão: mais recente primeiro
        if ordem == 'data_asc':
            queryset = queryset.order_by('data_entrada')
        elif ordem == 'data_desc':
            queryset = queryset.order_by('-data_entrada')
        elif ordem == 'veiculo_asc':
            queryset = queryset.order_by('marca', 'modelo')
        elif ordem == 'veiculo_desc':
            queryset = queryset.order_by('-marca', '-modelo')
        elif ordem == 'proprietario_asc':
            queryset = queryset.order_by('nome_proprietario')
        elif ordem == 'proprietario_desc':
            queryset = queryset.order_by('-nome_proprietario')
        elif ordem == 'valor_asc':
            queryset = queryset.order_by('valor_consignacao')
        elif ordem == 'valor_desc':
            queryset = queryset.order_by('-valor_consignacao')
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['show_vendedor'] = is_master(self.request.user) or is_gerente(self.request.user)
        
        # Adiciona a ordem atual ao contexto
        context['ordem_atual'] = self.request.GET.get('ordem', '-data_entrada')
        context['status_atual'] = self.request.GET.get('status', '')
        
        # Adiciona todos os parâmetros de filtro ao contexto
        context['filtros'] = {
            'veiculo': self.request.GET.get('veiculo', ''),
            'proprietario': self.request.GET.get('proprietario', ''),
            'placa': self.request.GET.get('placa', ''),
            'valor_min': self.request.GET.get('valor_min', ''),
            'valor_max': self.request.GET.get('valor_max', ''),
            'data_inicio': self.request.GET.get('data_inicio', ''),
            'data_fim': self.request.GET.get('data_fim', ''),
        }
        
        # Adiciona lista de vendedores para o filtro
        if context['show_vendedor']:
            context['vendedores'] = User.objects.filter(groups__name='vendedores')
        
        # Adiciona o vendedor selecionado ao contexto
        vendedor_id = self.request.GET.get('vendedor')
        if vendedor_id:
            vendedor = User.objects.filter(id=vendedor_id).first()
            context['vendedor_selecionado'] = vendedor_id
            context['vendedor_nome'] = vendedor.get_full_name() or vendedor.username if vendedor else ''
        
        # Adiciona a data de hoje no contexto para verificação no template
        context['hoje'] = timezone.now().date()
        
        # Estatísticas
        context['total_disponiveis'] = Consignacao.objects.filter(status='DISPONÍVEL').count()
        context['total_vendidos'] = Consignacao.objects.filter(status='VENDIDO').count()
        
        # Próximas a vencer (consignações que vencem nos próximos 7 dias)
        hoje = timezone.now().date()
        data_limite = hoje + timedelta(days=7)
        context['proximas_vencer'] = Consignacao.objects.filter(
            status='DISPONÍVEL', 
            data_limite__gte=hoje,
            data_limite__lte=data_limite
        ).count()
        
        return context

class ConsignacaoCreateView(LoginRequiredMixin, CreateView):
    model = Consignacao
    form_class = ConsignacaoForm
    template_name = 'core/consignacao_form.html'
    success_url = reverse_lazy('consignacao-list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Se não for gerente ou master, pré-seleciona o vendedor atual
        if not is_gerente(self.request.user):
            form.fields['vendedor_responsavel'].initial = self.request.user
            form.fields['vendedor_responsavel'].widget.attrs['readonly'] = True
        return form

    def form_valid(self, form):
        moto_estoque = form.cleaned_data.get('moto_estoque')
        if not moto_estoque:
            # Tenta encontrar o proprietário pelo nome (opcional)
            proprietario = None
            nome_proprietario = form.cleaned_data.get('nome_proprietario')
            if nome_proprietario:
                proprietario = Cliente.objects.filter(nome__iexact=nome_proprietario).first()
            # Cria a moto no estoque
            moto_estoque = EstoqueMoto.objects.create(
                marca=form.cleaned_data.get('marca'),
                modelo=form.cleaned_data.get('modelo'),
                ano=form.cleaned_data.get('ano'),
                cor=form.cleaned_data.get('cor'),
                placa=form.cleaned_data.get('placa'),
                renavam=form.cleaned_data.get('renavam'),
                chassi=form.cleaned_data.get('chassi'),
                categoria='CONSIGNACAO',
                status='DISPONIVEL',
                data_chegada=form.cleaned_data.get('data_entrada'),
                observacao=form.cleaned_data.get('observacoes'),
                proprietario=proprietario
            )
            messages.success(self.request, 'Moto cadastrada automaticamente no estoque!')
        # (Opcional) Poderia salvar o vínculo da consignação com a moto criada, se o modelo tivesse esse campo
        return super().form_valid(form)

class ConsignacaoUpdateView(LoginRequiredMixin, UpdateView):
    model = Consignacao
    form_class = ConsignacaoForm
    template_name = 'core/consignacao_form.html'
    success_url = reverse_lazy('consignacao-list')

    def get_queryset(self):
        if is_master(self.request.user) or is_gerente(self.request.user):
            return Consignacao.objects.all()
        return Consignacao.objects.filter(vendedor_responsavel=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Consignação atualizada com sucesso!")
        return super().form_valid(form)

class ConsignacaoDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Consignacao
    template_name = 'core/consignacao_confirm_delete.html'
    success_url = reverse_lazy('consignacao-list')
    
    def test_func(self):
        # Apenas gerentes e master podem excluir consignações
        return is_gerente(self.request.user)

    def get_queryset(self):
        if is_master(self.request.user) or is_gerente(self.request.user):
            return Consignacao.objects.all()
        return Consignacao.objects.none()

class ConsignacaoDetailView(LoginRequiredMixin, DetailView):
    model = Consignacao
    template_name = 'core/consignacao_detail.html'
    context_object_name = 'consignacao'

    def get_queryset(self):
        if is_master(self.request.user) or is_gerente(self.request.user):
            return Consignacao.objects.all()
        return Consignacao.objects.filter(vendedor_responsavel=self.request.user)

@login_required
def registrar_venda_consignacao(request, pk):
    consignacao = get_object_or_404(Consignacao, pk=pk)
    
    # Verificar permissões
    if not (is_master(request.user) or is_gerente(request.user) or request.user == consignacao.vendedor_responsavel):
        messages.error(request, "Você não tem permissão para registrar a venda desta consignação.")
        return redirect('consignacao-list')
    
    # Verificar se a consignação já foi vendida
    if consignacao.status == 'VENDIDO':
        messages.warning(request, "Esta consignação já foi vendida.")
        return redirect('consignacao-detail', pk=pk)
    
    # Inicializar contexto para o template
    context = {
        'form': None,
        'consignacao': consignacao,
        'valor_venda': 0,
        'valor_comissao': 0,
        'valor_proprietario': 0
    }
    
    if request.method == 'POST':
        form = ConsignacaoVendaForm(request.POST, instance=consignacao)
        
        # Se o botão "Calcular" foi clicado
        if 'calcular' in request.POST and form.is_valid():
            # Não salve o formulário, apenas faça os cálculos
            valor_venda = form.cleaned_data.get('valor_venda') or 0
            comissao_pct = consignacao.comissao_percentual
            
            # Calcular valores
            valor_comissao = (valor_venda * comissao_pct) / 100
            valor_proprietario = valor_venda - valor_comissao
            
            # Adicionar ao contexto
            context.update({
                'form': form,
                'valor_venda': valor_venda,
                'valor_comissao': valor_comissao,
                'valor_proprietario': valor_proprietario
            })
            
            return render(request, 'core/consignacao_venda_form.html', context)
            
        # Se o botão "Confirmar Venda" foi clicado
        elif 'confirmar' in request.POST and form.is_valid():
            form.instance.status = 'VENDIDO'
            if not form.instance.data_venda:
                form.instance.data_venda = timezone.now().date()
            form.save()
            messages.success(request, "Venda registrada com sucesso!")
            return redirect('consignacao-detail', pk=pk)
        else:
            context['form'] = form
    else:
        form = ConsignacaoVendaForm(instance=consignacao, initial={'status': 'VENDIDO', 'data_venda': timezone.now().date()})
        context['form'] = form
    
    return render(request, 'core/consignacao_venda_form.html', context)

@login_required
def gerar_contrato_consignacao(request, pk):
    consignacao = get_object_or_404(Consignacao, pk=pk)
    
    # Verificar permissões
    if not (is_master(request.user) or is_gerente(request.user) or request.user == consignacao.vendedor_responsavel):
        messages.error(request, "Você não tem permissão para gerar contratos para esta consignação.")
        return redirect('consignacao-list')
    
    # Data atual formatada
    data_atual = timezone.now().strftime('%d/%m/%Y')
    
    # Dados para o contrato
    context = {
        'consignacao': consignacao,
        'proprietario': {
            'nome': consignacao.nome_proprietario,
            'cpf': consignacao.cpf_proprietario or '000.000.000-00',
            'rg': consignacao.rg_proprietario or '00.000.000-0',
            'endereco': consignacao.endereco_proprietario or 'Endereço do Proprietário',
            'contato': consignacao.contato_proprietario,
        },
        'veiculo': {
            'marca': consignacao.marca,
            'modelo': consignacao.modelo,
            'ano': consignacao.ano,
            'cor': consignacao.cor,
            'placa': consignacao.placa,
            'chassi': consignacao.chassi or 'N/A',
            'renavam': consignacao.renavam or 'N/A',
            'motor': "",  # Campo para número do motor
        },
        'contrato': {
            'valor_consignacao': consignacao.valor_consignacao,
            'valor_consignacao_extenso': valor_por_extenso(consignacao.valor_consignacao),
            'valor_minimo': consignacao.valor_minimo,
            'valor_minimo_extenso': valor_por_extenso(consignacao.valor_minimo or consignacao.valor_consignacao),
            'comissao_percentual': consignacao.comissao_percentual,
            'data_entrada': consignacao.data_entrada,
            'data_limite': consignacao.data_limite,
            'prazo_dias': (consignacao.data_limite - consignacao.data_entrada).days,
            'data_atual': data_atual,  # Adicionando a data atual também no contrato
        },
        'loja': {
            'nome': 'MARKETING PRADO MOTORS',
            'cnpj': '02.968.496/0001-17',
            'endereco': 'Rua Bruno Andrea, 24 - Parque das Palmeiras',
            'cidade': 'Angra dos Reis',
            'estado': 'RJ',
            'cep': '23.906-410',
            'telefone': '(24) 3365-3303',
            'email': 'motorsprado@gmail.com',
        },
        'loja_texto_completo': 'Paraty auto zero Ltda., pessoa jurídica de direito privado, inscrita sob CNPJ 02.968.496/0001-17, com sede na Rua Bruno Andrea N° 24 – Parque das palmeiras- Angra dos reis – RJ – CEP: 23.906-410, neste ato representada por Alessandro Correa Barbosa, brasileiro, empresário, portador da carteira de identidade RG: 21.818.188-1, inscrito no CPF: 118.921.797-09.',
        'data_atual': data_atual,
    }
    
    # Determinar qual template usar baseado no status da consignação
    if consignacao.status == 'VENDIDO':
        template_contrato = 'core/contratos_html/contrato_veiculo_usado.html'
        tipo_contrato = 'Veículo Usado'
        
        # Adicionar dados do comprador quando vendido - usar apenas os campos disponíveis no modelo
        context['cliente'] = {
            'nome': consignacao.nome_comprador or "Nome do Comprador",
            'cpf': "000.000.000-00",  # Campos não disponíveis no modelo, usando valor padrão
            'rg': "00.000.000-0",
            'endereco': "Endereço do Comprador", 
            'contato': "Telefone do Comprador",
            'nacionalidade': 'brasileiro(a)',
            'estado_civil': 'solteiro(a)',
            'profissao': 'profissão',
        }
        
        # Adicionar dados da venda
        valor_venda = consignacao.valor_venda or 0
        context['venda'] = {
            'valor_total': valor_venda,
            'valor_total_extenso': valor_por_extenso(valor_venda),
            'forma_pagamento': "À Vista",  # Campo não disponível no modelo, usando valor padrão
            'data_venda': consignacao.data_venda.strftime('%d/%m/%Y') if consignacao.data_venda else data_atual,
        }
    else:
        template_contrato = 'core/contratos_html/contrato_consignacao.html'
        tipo_contrato = 'Consignação'
    
    # Verificar se é uma requisição para nova aba
    if request.GET.get('nova_aba'):
        return render(request, template_contrato, context)
    
    # Se não for nova aba, renderiza a página com o iframe
    # Cria URL absoluta para garantir que o iframe carregue corretamente
    iframe_url = request.build_absolute_uri(f"{request.path}?nova_aba=true")
    
    return render(request, 'core/contrato_view.html', {
        'contrato_url': iframe_url,
        'tipo_contrato': tipo_contrato
    })

# Gerenciamento de Usuários
class GerenciamentoUsuariosMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_gerente(self.request.user)

class UsuarioListView(GerenciamentoUsuariosMixin, ListView):
    model = User
    template_name = 'core/usuario_list.html'
    context_object_name = 'usuarios'
    
    def get_queryset(self):
        return User.objects.all().select_related('perfil')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_master'] = is_master(self.request.user)
        return context

class UsuarioCreateView(GerenciamentoUsuariosMixin, CreateView):
    model = User
    form_class = UsuarioCreateForm
    template_name = 'core/usuario_form.html'
    success_url = reverse_lazy('usuario-list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['perfil_form'] = PerfilForm(self.request.POST)
        else:
            context['perfil_form'] = PerfilForm()
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        perfil_form = context['perfil_form']
        if form.is_valid() and perfil_form.is_valid():
            user = form.save()
            
            # Adicionar ao grupo de vendedores
            grupo_vendedores, created = Group.objects.get_or_create(name='vendedores')
            user.groups.add(grupo_vendedores)
            
            # Salvar perfil
            perfil = perfil_form.save(commit=False)
            perfil.usuario = user
            perfil.save()
            
            messages.success(self.request, "Usuário criado com sucesso!")
            return super().form_valid(form)
        else:
            return self.render_to_response(self.get_context_data(form=form))

class UsuarioUpdateView(GerenciamentoUsuariosMixin, UpdateView):
    model = User
    form_class = UsuarioUpdateForm
    template_name = 'core/usuario_form.html'
    success_url = reverse_lazy('usuario-list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            try:
                perfil = self.object.perfil
                context['perfil_form'] = PerfilForm(self.request.POST, instance=perfil)
            except Perfil.DoesNotExist:
                context['perfil_form'] = PerfilForm(self.request.POST)
        else:
            try:
                perfil = self.object.perfil
                context['perfil_form'] = PerfilForm(instance=perfil)
            except Perfil.DoesNotExist:
                context['perfil_form'] = PerfilForm()
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        perfil_form = context['perfil_form']
        if form.is_valid() and perfil_form.is_valid():
            user = form.save()
            
            # Salvar perfil
            try:
                perfil = user.perfil
                perfil_form = PerfilForm(self.request.POST, instance=perfil)
            except Perfil.DoesNotExist:
                perfil = perfil_form.save(commit=False)
                perfil.usuario = user
            
            perfil_form.save()
            
            messages.success(self.request, "Usuário atualizado com sucesso!")
            return super().form_valid(form)
        else:
            return self.render_to_response(self.get_context_data(form=form))

class AlterarSenhaView(GerenciamentoUsuariosMixin, FormView):
    template_name = 'core/alterar_senha.html'
    form_class = AlterarSenhaForm
    success_url = reverse_lazy('usuario-list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = get_object_or_404(User, pk=self.kwargs['pk'])
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['usuario'] = get_object_or_404(User, pk=self.kwargs['pk'])
        return context
    
    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Senha alterada com sucesso!")
        return super().form_valid(form)

@csrf_exempt
def salvar_assinatura(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            assinatura_data = data.get('assinatura')
            tipo = data.get('tipo', 'cliente')
            id_venda = data.get('id_venda')
            id_consignacao = data.get('id_consignacao')
            
            if not assinatura_data:
                return JsonResponse({'status': 'erro', 'mensagem': 'Dados da assinatura não fornecidos'}, status=400)
                
            # Verificar se está associada a uma venda ou consignação
            venda = None
            consignacao = None
            
            if id_venda:
                try:
                    venda = Venda.objects.get(id=id_venda)
                except Venda.DoesNotExist:
                    return JsonResponse({'status': 'erro', 'mensagem': 'Venda não encontrada'}, status=404)
            
            if id_consignacao:
                try:
                    consignacao = Consignacao.objects.get(id=id_consignacao)
                except Consignacao.DoesNotExist:
                    return JsonResponse({'status': 'erro', 'mensagem': 'Contrato de consignação não encontrado'}, status=404)
            
            if not venda and not consignacao:
                return JsonResponse({'status': 'erro', 'mensagem': 'É necessário fornecer um ID de venda ou consignação'}, status=400)
            
            # Criar a assinatura
            assinatura = AssinaturaDigital(
                venda=venda,
                consignacao=consignacao,
                imagem_assinatura=assinatura_data,
                tipo=tipo
            )
            assinatura.save()
            
            return JsonResponse({'status': 'sucesso', 'mensagem': 'Assinatura salva com sucesso', 'id': assinatura.id})
            
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)
    
    return JsonResponse({'status': 'erro', 'mensagem': 'Método não permitido'}, status=405)

class ContratoDetailView(LoginRequiredMixin, DetailView):
    model = Venda
    template_name = 'core/contrato_detalhes.html'
    context_object_name = 'contrato'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contrato = self.object
        # Buscar assinaturas relacionadas
        assinaturas = AssinaturaDigital.objects.filter(venda=contrato)
        context['assinaturas'] = assinaturas
        return context

def motos_do_cliente_ajax(request, cliente_id):
    motos = EstoqueMoto.objects.filter(proprietario_id=cliente_id)
    data = {
        'motos': [
            {'id': moto.id, 'label': f'{moto.marca} {moto.modelo} - {moto.placa}'}
            for moto in motos
        ]
    }
    return JsonResponse(data)

class EstoqueMotoListView(ListView):
    model = EstoqueMoto
    template_name = 'core/estoque_moto_list.html'
    context_object_name = 'motos'
    paginate_by = 10

    def get_queryset(self):
        queryset = EstoqueMoto.objects.all()
        # Filtros básicos (marca, modelo, placa, categoria, status)
        marca = self.request.GET.get('marca')
        modelo = self.request.GET.get('modelo')
        placa = self.request.GET.get('placa')
        categoria = self.request.GET.get('categoria')
        status = self.request.GET.get('status')
        if marca:
            queryset = queryset.filter(marca__icontains=marca)
        if modelo:
            queryset = queryset.filter(modelo__icontains=modelo)
        if placa:
            queryset = queryset.filter(placa__icontains=placa)
        if categoria:
            queryset = queryset.filter(categoria=categoria)
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Estatísticas para cards
        context['total_disponiveis'] = EstoqueMoto.objects.filter(status='DISPONIVEL').count()
        context['total_vendidas'] = EstoqueMoto.objects.filter(status='VENDIDO').count()
        context['total_oficina'] = EstoqueMoto.objects.filter(status='OFICINA').count()
        context['total_pendencia'] = EstoqueMoto.objects.filter(status='PENDENCIA').count()
        # Filtros atuais
        context['filtros'] = {
            'marca': self.request.GET.get('marca', ''),
            'modelo': self.request.GET.get('modelo', ''),
            'placa': self.request.GET.get('placa', ''),
            'categoria': self.request.GET.get('categoria', ''),
            'status': self.request.GET.get('status', ''),
        }
        return context

class EstoqueMotoCreateView(CreateView):
    model = EstoqueMoto
    form_class = EstoqueMotoForm
    template_name = 'core/estoque_moto_form.html'
    success_url = reverse_lazy('estoque-moto-list')

class EstoqueMotoUpdateView(UpdateView):
    model = EstoqueMoto
    form_class = EstoqueMotoForm
    template_name = 'core/estoque_moto_form.html'
    success_url = reverse_lazy('estoque-moto-list')

class EstoqueMotoDeleteView(DeleteView):
    model = EstoqueMoto
    template_name = 'core/estoque_moto_confirm_delete.html'
    success_url = reverse_lazy('estoque-moto-list')

class ClienteListView(LoginRequiredMixin, ListView):
    model = Cliente
    template_name = 'core/cliente_list.html'
    context_object_name = 'clientes'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                models.Q(nome__icontains=search_query) |
                models.Q(cpf__icontains=search_query) |
                models.Q(telefone__icontains=search_query)
            )
        return queryset.order_by('nome')

class ClienteCreateView(LoginRequiredMixin, CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'core/cliente_form.html'
    success_url = reverse_lazy('cliente-list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Cliente cadastrado com sucesso!')
        return super().form_valid(form)

class ClienteUpdateView(LoginRequiredMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'core/cliente_form.html'
    success_url = reverse_lazy('cliente-list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Cliente atualizado com sucesso!')
        return super().form_valid(form)

class ClienteDeleteView(LoginRequiredMixin, DeleteView):
    model = Cliente
    template_name = 'core/cliente_confirm_delete.html'
    success_url = reverse_lazy('cliente-list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Cliente excluído com sucesso!')
        return super().delete(request, *args, **kwargs)

def dados_moto_estoque_ajax(request, moto_id):
    try:
        moto = EstoqueMoto.objects.get(id=moto_id, categoria='CONSIGNACAO')
        data = {
            'marca': moto.marca,
            'modelo': moto.modelo,
            'ano': moto.ano,
            'cor': moto.cor,
            'placa': moto.placa,
            'renavam': moto.renavam,
            'chassi': moto.chassi,
        }
        return JsonResponse({'success': True, 'moto': data})
    except EstoqueMoto.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Moto não encontrada ou não é da categoria Consignação.'})
