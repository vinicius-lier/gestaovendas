from django import forms
from .models import Venda

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