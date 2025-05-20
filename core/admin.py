from django.contrib import admin
from .models import Perfil, Venda, Consignacao, AssinaturaDigital

# Register your models here.
admin.site.register(Perfil)
admin.site.register(Venda)
admin.site.register(Consignacao)

@admin.register(AssinaturaDigital)
class AssinaturaDigitalAdmin(admin.ModelAdmin):
    list_display = ('id', 'tipo', 'get_referencia', 'data_criacao')
    list_filter = ('tipo', 'data_criacao')
    search_fields = ('id', 'tipo')
    
    def get_referencia(self, obj):
        if obj.venda:
            return f"Venda #{obj.venda.id}"
        return f"Consignação #{obj.consignacao.id}"
    get_referencia.short_description = 'Referência'
