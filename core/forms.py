from django import forms
from .models import Venda, Consignacao
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.forms import UserCreationForm, SetPasswordForm
from django.contrib.auth.models import User, Group
from .models import Perfil

class VendaForm(forms.ModelForm):
    class Meta:
        model = Venda
        fields = [
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
        widgets = {
            'data_atendimento': forms.DateInput(attrs={'type': 'date'}),
        } 

class ConsignacaoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Define a data limite padrão como 30 dias após a data atual
        if not self.initial.get('data_limite'):
            self.initial['data_limite'] = timezone.now().date() + timedelta(days=30)
        
        # Define a comissão padrão como 5%
        if not self.initial.get('comissao_percentual'):
            self.initial['comissao_percentual'] = 5.00
    
    class Meta:
        model = Consignacao
        fields = [
            # Dados do proprietário
            'nome_proprietario',
            'cpf_proprietario',
            'rg_proprietario',
            'endereco_proprietario',
            'contato_proprietario',
            
            # Dados do veículo
            'marca',
            'modelo',
            'ano',
            'cor',
            'placa',
            'renavam',
            'chassi',
            
            # Dados da consignação
            'valor_consignacao',
            'valor_minimo',
            'comissao_percentual',
            'data_entrada',
            'data_limite',
            'status',
            'observacoes',
            'vendedor_responsavel',
        ]
        widgets = {
            'data_entrada': forms.DateInput(attrs={'type': 'date'}),
            'data_limite': forms.DateInput(attrs={'type': 'date'}),
            'observacoes': forms.Textarea(attrs={'rows': 3}),
            'endereco_proprietario': forms.Textarea(attrs={'rows': 2}),
        }

class ConsignacaoVendaForm(forms.ModelForm):
    """Formulário para registrar a venda de um veículo em consignação"""
    
    class Meta:
        model = Consignacao
        fields = [
            'data_venda',
            'valor_venda',
            'nome_comprador',
            'status',
        ]
        widgets = {
            'data_venda': forms.DateInput(attrs={'type': 'date'}),
        }

class UsuarioCreateForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})
            
class UsuarioUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'is_active']
        widgets = {
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field != 'is_active':  # Não aplicar form-control ao checkbox
                self.fields[field].widget.attrs.update({'class': 'form-control'})
            
class PerfilForm(forms.ModelForm):
    class Meta:
        model = Perfil
        fields = ['tipo']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo'].widget.attrs.update({'class': 'form-control'})
        
class AlterarSenhaForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'}) 