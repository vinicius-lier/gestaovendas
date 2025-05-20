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

class Consignacao(models.Model):
    STATUS_CHOICES = [
        ('DISPONÍVEL', 'DISPONÍVEL'),
        ('VENDIDO', 'VENDIDO'),
        ('DEVOLVIDO', 'DEVOLVIDO'),
        ('CANCELADO', 'CANCELADO'),
    ]
    
    # Dados do proprietário
    nome_proprietario = models.CharField(max_length=100)
    cpf_proprietario = models.CharField(max_length=14, blank=True, null=True)
    rg_proprietario = models.CharField(max_length=20, blank=True, null=True)
    endereco_proprietario = models.CharField(max_length=200, blank=True, null=True)
    contato_proprietario = models.CharField(max_length=100)
    
    # Dados do veículo
    marca = models.CharField(max_length=50)
    modelo = models.CharField(max_length=100)
    ano = models.CharField(max_length=4)
    cor = models.CharField(max_length=50)
    placa = models.CharField(max_length=8)
    renavam = models.CharField(max_length=11, blank=True, null=True)
    chassi = models.CharField(max_length=17, blank=True, null=True)
    
    # Dados da consignação
    valor_consignacao = models.DecimalField(max_digits=10, decimal_places=2)
    valor_minimo = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    comissao_percentual = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)
    data_entrada = models.DateField(default=timezone.now)
    data_limite = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DISPONÍVEL')
    observacoes = models.TextField(blank=True, null=True)
    
    # Relacionamentos
    vendedor_responsavel = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Campos para quando for vendido
    data_venda = models.DateField(blank=True, null=True)
    valor_venda = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    nome_comprador = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        verbose_name = 'Consignação'
        verbose_name_plural = 'Consignações'
    
    def __str__(self):
        return f"{self.modelo} - {self.placa} ({self.nome_proprietario})"
        
    @property
    def valor_comissao(self):
        if self.valor_venda:
            return (self.valor_venda * self.comissao_percentual) / 100
        return 0
        
    @property
    def valor_proprietario(self):
        if self.valor_venda:
            return self.valor_venda - self.valor_comissao
        return 0
