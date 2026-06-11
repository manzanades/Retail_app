# retail_app/views.py
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
from django.db.models import Sum, Avg
from .models import FactVentas, DimCliente, DimProducto, DimCanal
import os
import datetime
import pandas as pd
import json

DIR_RAW = os.path.join(settings.BASE_DIR, "data_lake", "raw")
DIR_PROCESSED = os.path.join(settings.BASE_DIR, "data_lake", "processed")

def ingestar_venta_manual(request):
    DIR_RAW_POS = os.path.join(DIR_RAW, "ventas_pos")
    DIR_RAW_ONLINE = os.path.join(DIR_RAW, "ventas_online")
    
    os.makedirs(DIR_RAW_POS, exist_ok=True)
    os.makedirs(DIR_RAW_ONLINE, exist_ok=True)
    os.makedirs(DIR_PROCESSED, exist_ok=True)

    archivos = os.listdir(DIR_RAW_POS)
    fechas_disponibles = sorted(list(set([
        f.replace(".csv", "") for f in archivos if f.endswith(".csv")
    ])))

    if request.method == "POST":
        if 'procesar_lote_dia' in request.POST:
            fecha_sel = request.POST.get('fecha_lote')
            
            if not fecha_sel:
                messages.error(request, "Por favor, selecciona una fecha válida de la lista.")
                return redirect('ingestar_venta_manual')

            file_pos = os.path.join(DIR_RAW_POS, f"{fecha_sel}.csv")
            file_online = os.path.join(DIR_RAW_ONLINE, f"{fecha_sel}.csv")

            if not os.path.exists(file_pos) and not os.path.exists(file_online):
                messages.error(request, f"No se encontraron los registros RAW para el día {fecha_sel}.")
                return redirect('ingestar_venta_manual')

            lista_dfs = []

            # Ingesta POS: Se añade encoding y reemplazo de valores vacíos en comunas
            if os.path.exists(file_pos):
                df_pos_raw = pd.read_csv(file_pos, encoding='latin-1').drop_duplicates()
                df_pos_raw['id_canal'] = 1
                df_pos_raw = df_pos_raw.rename(columns={'precio_unitario': 'precio_final', 'tienda': 'tienda_local'})
                # Reemplaza celdas de comunas vacías para evitar conflictos de texto
                df_pos_raw['tienda_local'] = df_pos_raw['tienda_local'].fillna('Santiago Centro')
                lista_dfs.append(df_pos_raw[['id_venta', 'fecha', 'id_cliente', 'id_producto', 'id_canal', 'cantidad', 'precio_final', 'tienda_local']])

            # Ingesta Online
            if os.path.exists(file_online):
                df_online_raw = pd.read_csv(file_online, encoding='latin-1').drop_duplicates()
                df_online_raw['id_canal'] = 2
                df_online_raw = df_online_raw.rename(columns={'id_orden': 'id_venta', 'total': 'precio_final', 'canal': 'tienda_local'})
                df_online_raw['cantidad'] = 1
                df_online_raw['id_producto'] = 2001 
                lista_dfs.append(df_online_raw[['id_venta', 'fecha', 'id_cliente', 'id_producto', 'id_canal', 'cantidad', 'precio_final', 'tienda_local']])

            registros_nuevos = 0
            if lista_dfs:
                df_consolidado = pd.concat(lista_dfs, ignore_index=True)
                
                ruta_proc = os.path.join(DIR_PROCESSED, "ventas_consolidado.csv")
                if os.path.exists(ruta_proc):
                    df_consolidado.to_csv(ruta_proc, mode='a', header=False, index=False, encoding='latin-1')
                else:
                    df_consolidado.to_csv(ruta_proc, index=False, encoding='latin-1')

                # Poblamos el catálogo maestro completo antes de insertar las ventas
                asegurar_dimensiones_maestras()
                
                for _, fila in df_consolidado.iterrows():
                    try:
                        cliente_obj = DimCliente.objects.get(id_cliente=int(fila['id_cliente']))
                        producto_obj = DimProducto.objects.get(id_producto=int(fila['id_producto']))
                        canal_obj = DimCanal.objects.get(id_canal=int(fila['id_canal']))
                        
                        importe = int(fila['cantidad']) * int(fila['precio_final'])
                        utilidad_calc = int(importe * 0.15)
                        fecha_dt = datetime.datetime.strptime(str(fila['fecha']), "%Y-%m-%d").date()

                        if not FactVentas.objects.filter(id_venta=int(fila['id_venta']), id_producto=producto_obj).exists():
                            FactVentas.objects.create(
                                id_venta=int(fila['id_venta']), id_fecha=fecha_dt, id_cliente=cliente_obj,
                                id_producto=producto_obj, id_canal=canal_obj, cantidad=int(fila['cantidad']),
                                precio_final=int(fila['precio_final']), importe_total=importe,
                                utilidad=utilidad_calc, tienda_local=str(fila['tienda_local']).strip()
                            )
                            registros_nuevos += 1
                    except Exception as e:
                        print(f"Error cargando tupla: {e}")

            messages.success(request, f"¡Jornada Batch {fecha_sel} procesada! Capa Processed actualizada y {registros_nuevos} hechos añadidos a MySQL.")
            return redirect('ingestar_venta_manual')

    return render(request, 'formulario_ingesta.html', {'fechas_disponibles': fechas_disponibles})


def asegurar_dimensiones_maestras():
    """Garantiza el abanico completo de entidades para cumplir la integridad referencial"""
    # 1. Canales
    if not DimCanal.objects.filter(id_canal=1).exists(): DimCanal.objects.create(id_canal=1, nombre_canal="Físico", sub_canal="Tienda")
    if not DimCanal.objects.filter(id_canal=2).exists(): DimCanal.objects.create(id_canal=2, nombre_canal="Digital", sub_canal="Web")
    
    # 2. Catálogo de Productos Completo (Mockup match)
    productos_corporativos = [
        (2001, "Notebook Lenovo", "Tecnologia", 140000, "Lenovo"),
        (2002, "Refrigerador Samsung", "Hogar", 300000, "Samsung"),
        (2003, "Camisa Slim Fit", "Vestuario", 25000, "Zara"),
        (2004, "Crema Hidratante", "Belleza", 15000, "Loreal"),
        (2005, "Set de Bloques", "Juguetes", 20000, "Lego")
    ]
    for id_p, nom, cat, pre, prov in productos_corporativos:
        if not DimProducto.objects.filter(id_producto=id_p).exists():
            DimProducto.objects.create(id_producto=id_p, nombre_producto=nom, categoria=cat, precio_base=pre, proveedor=prov)
            
    # 3. Catálogo de Clientes de Prueba (101 al 106)
    clientes_sistema = [
        (101, "Juan", "Perez", "juan@email.com", "Premium", "Santiago"),
        (102, "Maria", "Gonzalez", "maria@email.com", "Regular", "Providencia"),
        (103, "Pedro", "Muñoz", "pedro@email.com", "Frecuente", "Maipu"),
        (104, "Ana", "Silva", "ana@email.com", "Regular", "Las Condes"),
        (105, "Luis", "Castro", "luis@email.com", "Premium", "La Florida"),
        (106, "Sofia", "Rojas", "sofia@email.com", "Frecuente", "Ñuñoa")
    ]
    for id_c, nom, ape, em, seg, ciu in clientes_sistema:
        if not DimCliente.objects.filter(id_cliente=id_c).exists():
            DimCliente.objects.create(id_cliente=id_c, nombre=nom, apellido=ape, email=em, segmento=seg, ciudad=ciu)


def dashboard_analitico(request):
    kpis = FactVentas.objects.aggregate(
        ventas_totales=Sum('importe_total'),
        utilidad_total=Sum('utilidad'),
        ticket_promedio=Avg('importe_total'),
        unidades_vendidas=Sum('cantidad')
    )
    
    v_totales = kpis['ventas_totales'] or 0
    u_total = kpis['utilidad_total'] or 0
    t_promedio = kpis['ticket_promedio'] or 0
    u_vendidas = kpis['unidades_vendidas'] or 0
    margen_porcentaje = (u_total / v_totales * 100) if v_totales > 0 else 0

    canal_query = FactVentas.objects.values('id_canal__nombre_canal').annotate(total=Sum('importe_total'))
    canales_labels = [c['id_canal__nombre_canal'] for c in canal_query]
    canales_data = [int(c['total']) for c in canal_query]

    cat_query = FactVentas.objects.values('id_producto__categoria').annotate(total=Sum('importe_total'))
    cat_labels = [c['id_producto__categoria'] for c in cat_query]
    cat_data = [int(c['total']) for c in cat_query]

    tendencia_query = FactVentas.objects.values('id_fecha').annotate(total=Sum('importe_total')).order_by('id_fecha')
    diaria_labels = [d['id_fecha'].strftime("%d/%m") for d in tendencia_query]
    diaria_data = [int(d['total']) for d in tendencia_query]

    context = {
        'ventas_totales': f"${v_totales:,.0f}".replace(",", "."),
        'margen_utilidad': f"{margen_porcentaje:.1f}%",
        'ticket_promedio': f"${t_promedio:,.0f}".replace(",", "."),
        'unidades_vendidas': f"{u_vendidas:,}".replace(",", "."),
        
        'canales_labels': json.dumps(canales_labels),
        'canales_data': json.dumps(canales_data),
        'cat_labels': json.dumps(cat_labels),
        'cat_data': json.dumps(cat_data),
        'diaria_labels': json.dumps(diaria_labels),
        'diaria_data': json.dumps(diaria_data),
    }
    return render(request, 'dashboard.html', context)
