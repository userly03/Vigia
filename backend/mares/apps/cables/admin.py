from django.contrib import admin

from .models import Cable, CableTramo, PuntoAmarre, Sello


@admin.register(Cable)
class CableAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'slug', 'longitud_km', 'fuente', 'actualizado')
    search_fields = ('nombre', 'slug')


@admin.register(PuntoAmarre)
class PuntoAmarreAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'pais')
    search_fields = ('nombre', 'pais')


@admin.register(CableTramo)
class CableTramoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cable', 'tiene_corredor')
    list_select_related = ('cable',)

    @admin.display(boolean=True, description='Corredor')
    def tiene_corredor(self, obj: CableTramo) -> bool:
        return obj.corredor is not None


@admin.register(Sello)
class SelloAdmin(admin.ModelAdmin):
    list_display = ('ts', 'hash')
    readonly_fields = ('ts', 'contenido', 'hash_anterior', 'hash')   # un sello no se edita: se rompería la cadena
