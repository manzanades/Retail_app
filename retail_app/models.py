from django.db import models

# --- DIMENSIONES OBLIGATORIAS ---
class DimCliente(models.Model):
    id_cliente = models.IntegerField(primary_key=True)
    nombre = models.CharField(max_length=50)
    apellido = models.CharField(max_length=50)
    email = models.EmailField()
    segmento = models.CharField(max_length=30)
    ciudad = models.CharField(max_length=50)

class DimProducto(models.Model):
    id_producto = models.IntegerField(primary_key=True)
    nombre_producto = models.CharField(max_length=100)
    categoria = models.CharField(max_length=50)
    precio_base = models.IntegerField()
    proveedor = models.CharField(max_length=50)

class DimCanal(models.Model):
    id_canal = models.IntegerField(primary_key=True)
    nombre_canal = models.CharField(max_length=50) # Físico o Digital
    sub_canal = models.CharField(max_length=50)    # Tienda, Web o App

# --- TABLA DE HECHOS (GRANULARIDAD: TRANSACCIONAL POR ÍTEM) ---
class FactVentas(models.Model):
    id_venta = models.IntegerField()
    id_fecha = models.DateField() # Representa la dimensión Tiempo de la pauta
    
    # Integridad de Datos garantizada por llaves foráneas nativas
    id_cliente = models.ForeignKey(DimCliente, on_delete=models.CASCADE)
    id_producto = models.ForeignKey(DimProducto, on_delete=models.CASCADE)
    id_canal = models.ForeignKey(DimCanal, on_delete=models.CASCADE)
    
    # Métricas requeridas para el análisis comercial del Dashboard futuro
    cantidad = models.IntegerField()
    precio_final = models.IntegerField()
    importe_total = models.IntegerField()
    utilidad = models.IntegerField()
    tienda_local = models.CharField(max_length=100) # Registra la sucursal o el subcanal

    class Meta:
        db_table = 'Fact_Ventas'
        unique_together = (('id_venta', 'id_producto'),) # Clave compuesta para evitar sobrescribir históricos