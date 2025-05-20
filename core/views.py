from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, FormView
from django.urls import reverse_lazy
from django.db.models import Sum, Count, Q
from django.contrib.auth.models import User
from .models import Venda, Perfil, Consignacao
from .forms import VendaForm, ConsignacaoForm, ConsignacaoVendaForm, PerfilForm, UsuarioCreateForm, UsuarioUpdateForm, AlterarSenhaForm
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from django.http import JsonResponse, FileResponse
from django.contrib import messages
from django.core.files.storage import default_storage
from django.conf import settings
import shutil
import os
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import Group

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
        vendas = Venda.objects.all()
        if vendedor_id:
            vendas = vendas.filter(vendedor_id=vendedor_id)
        numero_atendimentos = vendas.count()
        numero_fechamentos = vendas.filter(status='VENDIDO').count()
        
        # Ranking de vendedores por fechamentos (conversões)
        ranking = (
            Venda.objects.values('vendedor__username', 'vendedor_id')
            .annotate(
                total_atendimentos=Count('id'),
                fechamentos=Count('id', filter=Q(status='VENDIDO'))
            )
            .order_by('-fechamentos', '-total_atendimentos')
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
        numero_atendimentos = vendas.count()
        numero_fechamentos = vendas.filter(status='VENDIDO').count()
        context = {
            'numero_atendimentos': numero_atendimentos,
            'numero_fechamentos': numero_fechamentos,
            'vendas': vendas,
            'is_gerente': False,
        }
    return render(request, 'core/dashboard.html', context)

class VendaListView(LoginRequiredMixin, ListView):
    model = Venda
    template_name = 'core/venda_list.html'
    context_object_name = 'vendas'
    paginate_by = 10

    def get_queryset(self):
        queryset = Venda.objects.all().select_related('vendedor') if is_master(self.request.user) or is_gerente(self.request.user) else Venda.objects.filter(vendedor=self.request.user)
        
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
        
        return queryset

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
    
    vendas = Venda.objects.all()
    
    # Dados para gráficos
    vendas_por_vendedor = vendas.values('vendedor__username', 'vendedor_id').annotate(
        total_vendas=Count('id', filter=Q(status='VENDIDO')),
        total_atendimentos=Count('id')
    )
    
    # Gráfico de vendas por vendedor
    fig_vendas = px.bar(
        vendas_por_vendedor,
        x='vendedor__username',
        y='total_vendas',
        title='Vendas por Vendedor'
    )
    
    # Gráfico de atendimentos por vendedor
    fig_atendimentos = px.bar(
        vendas_por_vendedor,
        x='vendedor__username',
        y='total_atendimentos',
        title='Atendimentos por Vendedor'
    )
    
    context = {
        'vendas_por_vendedor': vendas_por_vendedor,
        'grafico_vendas': fig_vendas.to_html(),
        'grafico_atendimentos': fig_atendimentos.to_html(),
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

@login_required
def gerar_contrato(request, venda_id, tipo_contrato):
    venda = get_object_or_404(Venda, id=venda_id)
    
    # Verificar se o usuário tem permissão para visualizar esta venda
    if not (is_master(request.user) or is_gerente(request.user)) and venda.vendedor != request.user:
        messages.error(request, 'Você não tem permissão para visualizar este contrato.')
        return redirect('dashboard')
    
    # Data atual formatada
    data_atual = timezone.now().strftime('%d/%m/%Y')
    
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
        },
        'venda': {
            'valor_total': 50000.00,  # Campo não existe no modelo, usando valor padrão
            'valor_total_extenso': "cinquenta mil reais",  # Campo não existe no modelo, usando valor padrão
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
        messages.success(self.request, "Consignação cadastrada com sucesso!")
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
        },
        'contrato': {
            'valor_consignacao': consignacao.valor_consignacao,
            'valor_minimo': consignacao.valor_minimo,
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
        context['venda'] = {
            'valor_total': consignacao.valor_venda or 0,
            'valor_total_extenso': "valor em extenso",  # Você pode implementar uma função para converter número em extenso
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
