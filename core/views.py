from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db.models import Sum, Count, Q
from django.contrib.auth.models import User
from .models import Venda, Perfil
from .forms import VendaForm
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from django.http import JsonResponse, FileResponse
from django.contrib import messages
from django.core.files.storage import default_storage
from django.conf import settings
import shutil
import os

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
        vendedor_id = self.request.GET.get('vendedor')
        if vendedor_id and (is_master(self.request.user) or is_gerente(self.request.user)):
            queryset = queryset.filter(vendedor_id=vendedor_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['show_vendedor'] = is_master(self.request.user) or is_gerente(self.request.user)
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
