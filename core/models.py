from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Create your models here.

class Perfil(models.Model):
    TIPO_CHOICES = [
        ('master', 'Master'),
        ('gerente', 'Gerente'),
        ('vendedor', 'Vendedor'),
    ]
    
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    
    def __str__(self):
        return f"{self.usuario.username} - {self.tipo}"

class Venda(models.Model):
    ORIGEM_CHOICES = [
        ('LOJA', 'LOJA'),
        ('VENDEDOR', 'VENDEDOR'),
        ('CHATBOT', 'CHATBOT'),
        ('COCKPIT', 'COCKPIT'),
        ('INSTAGRAM', 'INSTAGRAM'),
        ('MONTEIRO', 'MONTEIRO'),
    ]
    FORMA_PAGAMENTO_CHOICES = [
        ('A VISTA', 'A VISTA'),
        ('A VISTA COM TROCA', 'A VISTA COM TROCA'),
        ('FINANCIAMENTO', 'FINANCIAMENTO'),
        ('FINANCIAMENTO COM TROCA', 'FINANCIAMENTO COM TROCA'),
        ('SEM INFORMAÇÃO', 'SEM INFORMAÇÃO'),
    ]
    STATUS_CHOICES = [
        ('VENDIDO', 'VENDIDO'),
        ('EM NEGOCIAÇÃO', 'EM NEGOCIAÇÃO'),
        ('RECUSA DE CRÉDITO', 'RECUSA DE CRÉDITO'),
        ('NEGOCIAÇÃO ENCERRADA', 'NEGOCIAÇÃO ENCERRADA'),
    ]

    nome_cliente = models.CharField(max_length=100, blank=True, null=True)
    contato = models.CharField(max_length=100, blank=True, null=True)
    origem = models.CharField(max_length=20, choices=ORIGEM_CHOICES, blank=True, null=True)
    modelo_interesse = models.CharField(max_length=100, blank=True, null=True)
    forma_pagamento = models.CharField(max_length=30, choices=FORMA_PAGAMENTO_CHOICES, blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, blank=True, null=True)
    observacoes = models.TextField(blank=True, null=True)
    data_atendimento = models.DateField(blank=True, null=True)
    vendedor = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)

    def __str__(self):
        return f"{self.nome_cliente} - {self.modelo_interesse} ({self.data_atendimento})"
