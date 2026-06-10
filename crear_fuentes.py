# crear_fuentes.py
import os
import datetime
import random

# Definimos las rutas para que caigan directo en la estructura RAW del Data Lake
DIR_RAW_POS = os.path.join("data_lake", "raw", "ventas_pos")
DIR_RAW_ONLINE = os.path.join("data_lake", "raw", "ventas_online")

os.makedirs(DIR_RAW_POS, exist_ok=True)
os.makedirs(DIR_RAW_ONLINE, exist_ok=True)

fecha_inicio = datetime.date(2026, 4, 1)
comunas = ["Santiago", "Providencia", "Maipu", "Las Condes", "La Florida", "Ñuñoa"]
canales_digitales = ["web", "app"]

print(" Generando archivos origen directamente en la capa 'data_lake/raw/'...")

for i in range(14): # Generar las dos semanas (14 días)
    fecha_actual = fecha_inicio + datetime.timedelta(days=i)
    fecha_str = fecha_actual.strftime("%Y-%m-%d")
    
    # 1. Ventas POS (Físicas) -> data_lake/raw/ventas_pos/YYYY-MM-DD.csv
    file_pos = os.path.join(DIR_RAW_POS, f"{fecha_str}.csv")
    with open(file_pos, "w") as f:
        f.write("id_venta,fecha,id_cliente,id_producto,cantidad,precio_unitario,tienda\n")
        for j in range(6): # 6 registros mínimos para cumplir la pauta
            id_venta = f"10{i+1:02d}{j}"
            id_cliente = random.choice([101, 102, 103, 104, 105])
            id_producto = random.choice([2001, 2002, 2003, 2004, 2005])
            cantidad = random.randint(1, 3)
            precio = random.choice([150000, 300000, 50000, 20000, 80000])
            tienda = random.choice(comunas)
            f.write(f"{id_venta},{fecha_str},{id_cliente},{id_producto},{cantidad},{precio},{tienda}\n")
            
    # 2. Ventas Online (Digitales) -> data_lake/raw/ventas_online/YYYY-MM-DD.csv
    file_online = os.path.join(DIR_RAW_ONLINE, f"{fecha_str}.csv")
    with open(file_online, "w") as f:
        f.write("id_orden,fecha,id_cliente,total,canal\n")
        for j in range(6):
            id_orden = f"50{i+1:02d}{j}"
            id_cliente = random.choice([101, 102, 103, 104, 105, 106])
            total = random.choice([50000, 150000, 300000, 80000, 120000])
            canal = random.choice(canales_digitales)
            f.write(f"{id_orden},{fecha_str},{id_cliente},{total},{canal}\n")

print(" ¡Flujo de dos semanas inyectado en la capa RAW con éxito!")