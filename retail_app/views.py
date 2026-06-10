# retail_app/views.py
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
from .models import FactVentas, DimCliente, DimProducto, DimCanal
import os
import datetime
import pandas as pd

DIR_RAW = os.path.join(settings.BASE_DIR, "data_lake", "raw")
DIR_PROCESSED = os.path.join(settings.BASE_DIR, "data_lake", "processed")

def ingestar_venta_manual(request):
    DIR_RAW_POS = os.path.join(DIR_RAW, "ventas_pos")
    DIR_RAW_ONLINE = os.path.join(DIR_RAW, "ventas_online")
    
    # Asegurar que los directorios existan de antemano
    os.makedirs(DIR_RAW_POS, exist_ok=True)
    os.makedirs(DIR_RAW_ONLINE, exist_ok=True)
    os.makedirs(DIR_PROCESSED, exist_ok=True)

    # ESCANER: Lee directamente la capa RAW para ver qué fechas de las 2 semanas están listas
    archivos = os.listdir(DIR_RAW_POS)
    fechas_disponibles = sorted(list(set([
        f.replace(".csv", "") for f in archivos if f.endswith(".csv")
    ])))

    if request.method == "POST":
        # === PROCESAMIENTO BATCH DE UN DÍA SELECCIONADO ===
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

            # --- FASE ETL: LEER DESDE RAW, TRANSFORMAR E INTEGRAR EN PROCESSED ---
            lista_dfs = []

            if os.path.exists(file_pos):
                df_pos_raw = pd.read_csv(file_pos).drop_duplicates()
                df_pos_raw['id_canal'] = 1
                df_pos_raw = df_pos_raw.rename(columns={'precio_unitario': 'precio_final', 'tienda': 'tienda_local'})
                lista_dfs.append(df_pos_raw[['id_venta', 'fecha', 'id_cliente', 'id_producto', 'id_canal', 'cantidad', 'precio_final', 'tienda_local']])

            if os.path.exists(file_online):
                df_online_raw = pd.read_csv(file_online).drop_duplicates()
                df_online_raw['id_canal'] = 2
                df_online_raw = df_online_raw.rename(columns={'id_orden': 'id_venta', 'total': 'precio_final', 'canal': 'tienda_local'})
                df_online_raw['cantidad'] = 1
                df_online_raw['id_producto'] = 2001 # Producto base mapeado para la simulación
                lista_dfs.append(df_online_raw[['id_venta', 'fecha', 'id_cliente', 'id_producto', 'id_canal', 'cantidad', 'precio_final', 'tienda_local']])

            registros_nuevos = 0
            if lista_dfs:
                df_consolidado = pd.concat(lista_dfs, ignore_index=True)
                
                # Guardar acumulativamente en la capa PROCESSED del Data Lake (Pauta Parte 2)
                ruta_proc = os.path.join(DIR_PROCESSED, "ventas_consolidado.csv")
                if os.path.exists(ruta_proc):
                    df_consolidado.to_csv(ruta_proc, mode='a', header=False, index=False)
                else:
                    df_consolidado.to_csv(ruta_proc, index=False)

                # Asegurar consistencia dimensional en MySQL antes de poblar hechos
                asegurar_dimensiones_maestras()
                
                # Carga incremental uno a uno verificando duplicados (Pauta Parte 4 y 6)
                for _, fila in df_consolidado.iterrows():
                    try:
                        cliente_obj = DimCliente.objects.get(id_cliente=int(fila['id_cliente']))
                        producto_obj = DimProducto.objects.get(id_producto=int(fila['id_producto']))
                        canal_obj = DimCanal.objects.get(id_canal=int(fila['id_canal']))
                        
                        importe = int(fila['cantidad']) * int(fila['precio_final'])
                        utilidad_calc = int(importe * 0.15)
                        fecha_dt = datetime.datetime.strptime(str(fila['fecha']), "%Y-%m-%d").date()

                        # Inserción incremental estricta basada en clave compuesta
                        if not FactVentas.objects.filter(id_venta=int(fila['id_venta']), id_producto=producto_obj).exists():
                            FactVentas.objects.create(
                                id_venta=int(fila['id_venta']), id_fecha=fecha_dt, id_cliente=cliente_obj,
                                id_producto=producto_obj, id_canal=canal_obj, cantidad=int(fila['cantidad']),
                                precio_final=int(fila['precio_final']), importe_total=importe,
                                utilidad=utilidad_calc, tienda_local=str(fila['tienda_local'])
                            )
                            registros_nuevos += 1
                    except Exception as e:
                        print(f"Error cargando tupla: {e}")

            messages.success(request, f"¡Jornada Batch {fecha_sel} procesada! Capa Processed actualizada en el Data Lake y {registros_nuevos} nuevos hechos cargados en MySQL.")
            return redirect('ingestar_venta_manual')

    return render(request, 'formulario_ingesta.html', {'fechas_disponibles': fechas_disponibles})


def asegurar_dimensiones_maestras():
    """Registra catálogos base en MySQL para evitar quiebres de llaves foráneas en la demo"""
    if not DimCanal.objects.filter(id_canal=1).exists(): DimCanal.objects.create(id_canal=1, nombre_canal="Físico", sub_canal="Tienda")
    if not DimCanal.objects.filter(id_canal=2).exists(): DimCanal.objects.create(id_canal=2, nombre_canal="Digital", sub_canal="Web")
    if not DimProducto.objects.filter(id_producto=2001).exists():
        DimProducto.objects.create(id_producto=2001, nombre_producto="Notebook Lenovo", categoria="Tecnologia", precio_base=140000, proveedor="Lenovo")
    if not DimCliente.objects.filter(id_cliente=101).exists():
        DimCliente.objects.create(id_cliente=101, nombre="Juan", apellido="Perez", email="juan@email.com", segmento="Premium", ciudad="Santiago")