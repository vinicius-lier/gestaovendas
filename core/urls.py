from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    
    # URLs para Vendas
    path('vendas/', views.VendaListView.as_view(), name='venda-list'),
    path('vendas/nova/', views.VendaCreateView.as_view(), name='venda-create'),
    path('vendas/<int:pk>/editar/', views.VendaUpdateView.as_view(), name='venda-update'),
    path('vendas/<int:pk>/excluir/', views.VendaDeleteView.as_view(), name='venda-delete'),
    path('contrato/<int:venda_id>/<str:tipo_contrato>/', views.gerar_contrato, name='gerar-contrato'),
    
    # URLs para Consignações
    path('consignacoes/', views.ConsignacaoListView.as_view(), name='consignacao-list'),
    path('consignacoes/nova/', views.ConsignacaoCreateView.as_view(), name='consignacao-create'),
    path('consignacoes/<int:pk>/', views.ConsignacaoDetailView.as_view(), name='consignacao-detail'),
    path('consignacoes/<int:pk>/editar/', views.ConsignacaoUpdateView.as_view(), name='consignacao-update'),
    path('consignacoes/<int:pk>/excluir/', views.ConsignacaoDeleteView.as_view(), name='consignacao-delete'),
    path('consignacoes/<int:pk>/vender/', views.registrar_venda_consignacao, name='consignacao-vender'),
    path('consignacoes/<int:pk>/contrato/', views.gerar_contrato_consignacao, name='gerar-contrato-consignacao'),
    
    # Gerenciamento de Usuários
    path('usuarios/', views.UsuarioListView.as_view(), name='usuario-list'),
    path('usuarios/novo/', views.UsuarioCreateView.as_view(), name='usuario-create'),
    path('usuarios/<int:pk>/editar/', views.UsuarioUpdateView.as_view(), name='usuario-update'),
    path('usuarios/<int:pk>/alterar-senha/', views.AlterarSenhaView.as_view(), name='alterar-senha'),
    
    # Outros URLs
    path('resumo-gerencial/', views.resumo_gerencial, name='resumo-gerencial'),
    path('importar-vendas/', views.importar_vendas, name='importar-vendas'),
    path('modelo-importacao/', views.download_modelo_importacao, name='modelo-importacao'),
] 