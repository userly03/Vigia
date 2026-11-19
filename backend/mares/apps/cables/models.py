"""
Cables submarinos y sus puntos de amarre.

Fuente de los datos: TeleGeography (submarinecablemap.com). Su licencia para uso comercial NO está confirmada:
por eso los datos no se versionan en git; se descargan con `manage.py cargar_cables` y la pantalla muestra
la atribución. Antes de ofrecer esto como producto hay que obtener una licencia.
"""
from django.conf import settings
from django.contrib.gis.db import models as gis_models
from django.db import connection, models

TRAMO_KM = 50.0


class Cable(models.Model):
    slug = models.SlugField(max_length=120, unique=True)
    nombre = models.CharField(max_length=200)
    color = models.CharField(max_length=9, blank=True, default='')
    geom = gis_models.MultiLineStringField(srid=4326)
    longitud_km = models.FloatField(null=True, blank=True)
    fuente = models.CharField(max_length=80, default='TeleGeography')
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cables_cable'
        ordering = ['nombre']

    def __str__(self) -> str:
        return self.nombre

    @classmethod
    def reconstruir_tramos(cls, metros: float | None = None) -> dict:
        """
        Recalcula la longitud de cada cable y lo trocea en tramos de ~TRAMO_KM, cada uno con su corredor
        (la ruta ensanchada `metros` a cada lado). Los cables miden miles de km: un solo polígono por cable hace
        que el índice espacial sea inútil. Con tramos pequeños, cada buque sólo se compara con los vecinos.

        Un tramo a menos de 0,1° del antimeridiano (±180°) queda SIN corredor: el buffer geográfico daría un
        polígono de ancho mundial. Para esos la consulta usa la distancia directa (ver views._CANDIDATOS).
        """
        metros = float(metros if metros is not None else getattr(settings, 'CABLES_CORREDOR_M', 2000))
        with connection.cursor() as cur:
            cur.execute('UPDATE cables_cable SET longitud_km = ST_Length(geom::geography) / 1000.0')
            cur.execute('DELETE FROM cables_tramo')
            cur.execute(
                """
                INSERT INTO cables_tramo (cable_id, geom, corredor)
                SELECT c.id, piece.geom,
                       CASE WHEN ST_XMax(piece.geom) > 179.9 OR ST_XMin(piece.geom) < -179.9 THEN NULL
                            ELSE ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Buffer(piece.geom::geography, %s)::geometry), 3))
                       END
                FROM cables_cable c
                CROSS JOIN LATERAL ST_Dump(c.geom) AS d
                CROSS JOIN LATERAL (
                  SELECT ST_LineSubstring(d.geom, g.i::float8 / n.n, (g.i + 1)::float8 / n.n) AS geom
                  FROM (SELECT GREATEST(1, CEIL(ST_Length(d.geom::geography) / %s))::int AS n) AS n,
                       generate_series(0, n.n - 1) AS g(i)
                ) AS piece
                WHERE GeometryType(d.geom) = 'LINESTRING' AND ST_NPoints(d.geom) >= 2
                """,
                [metros, TRAMO_KM * 1000.0],
            )
            cur.execute('ANALYZE cables_tramo')
        return {'tramos': CableTramo.objects.count(), 'sin_corredor': CableTramo.objects.filter(corredor__isnull=True).count()}


class CableTramo(models.Model):
    """Trozo de cable de ~TRAMO_KM km con su corredor de vigilancia. Se regenera con Cable.reconstruir_tramos()."""

    cable = models.ForeignKey(Cable, on_delete=models.CASCADE, related_name='tramos')
    geom = gis_models.LineStringField(srid=4326)
    corredor = gis_models.MultiPolygonField(srid=4326, null=True, blank=True)

    class Meta:
        db_table = 'cables_tramo'


class PuntoAmarre(models.Model):
    slug = models.SlugField(max_length=160, unique=True)
    nombre = models.CharField(max_length=200)
    pais = models.CharField(max_length=80, blank=True, default='')
    geom = gis_models.PointField(srid=4326)

    class Meta:
        db_table = 'cables_punto_amarre'
        ordering = ['nombre']

    def __str__(self) -> str:
        return self.nombre


class Sello(models.Model):
    """
    Foto sellada de las alertas ALTO/MEDIO con datos reales en un instante. Cada sello incluye el hash del anterior:
    cambiar o borrar uno rompe todos los siguientes. Sirve para validar DESPUÉS, sin poder ajustar el resultado.

    Límite: la cadena solo prueba el orden dentro de NUESTRA base de datos. Para probar que existía antes de un
    suceso hay que publicar el último hash fuera (p. ej. en el repositorio); quien opera la base podría reescribirla entera.
    """
    ts = models.DateTimeField(db_index=True)
    contenido = models.JSONField()
    hash_anterior = models.CharField(max_length=64, blank=True, default='')
    hash = models.CharField(max_length=64, unique=True)

    class Meta:
        db_table = 'cables_sello'
        ordering = ['-ts']
