import dash
from dash import dcc, html
import plotly.express as px
import pandas as pd
import numpy as np
import dash_leaflet as dl
import geopandas as gpd
import os  # Import os module

# Inicializar app
app = dash.Dash(__name__)
server = app.server  # Importante para Render
app.title = "Dashboard GNCV"

# Cargar datos
try:
    # Ajustar ruta para usar path relativo
    csv_path = "Consulta_Precios_Promedio_de_Gas_Natural_Comprimido_Vehicular__AUTOMATIZADO__20250314.csv"
    df = pd.read_csv(csv_path, encoding="latin1")
    
    # Convertir fecha a datetime
    fecha_col = 'FECHA_PRECIO'
    precio_col = 'PRECIO_PROMEDIO_PUBLICADO'
    departamento_col = 'DEPARTAMENTO_EDS'
    
    df[fecha_col] = pd.to_datetime(df[fecha_col])
    
    # Crear columnas ANIO y MES
    df['ANIO'] = df[fecha_col].dt.year
    df['MES'] = df[fecha_col].dt.month
    
    # -------------------------
    # GRÁFICOS ESTADÍSTICOS
    # -------------------------
    fig_hist = px.histogram(df, x=precio_col, nbins=30, title="Distribución de Precios Promedio")
    fig_box = px.box(df, x=departamento_col, y=precio_col, title="Boxplot por Departamento")
    
    df_line = df.groupby([fecha_col, departamento_col])[precio_col].mean().reset_index()
    fig_line = px.line(df_line, x=fecha_col, y=precio_col, color=departamento_col, title="Evolución por Departamento")
    
    df_trend = df.groupby(fecha_col)[precio_col].mean().reset_index()
    fig_trend = px.line(df_trend, x=fecha_col, y=precio_col, title="Tendencia Global de Precios")
    
    df_anual_mes = df.groupby(['ANIO', 'MES'])[precio_col].mean().reset_index()
    fig_anual_mes = px.line(df_anual_mes, x='MES', y=precio_col, color='ANIO', title="Tendencia por Año y Mes")
    
    precio_por_departamento = df.groupby(departamento_col)[precio_col].mean().sort_values()
    fig_bar = px.bar(x=precio_por_departamento.values, y=precio_por_departamento.index, orientation='h', title="Precio Promedio por Departamento")
    
    top_municipios = df.groupby('MUNICIPIO_EDS')[precio_col].mean().nlargest(10)
    fig_top_municipios = px.bar(x=top_municipios.values, y=top_municipios.index, orientation='h', title="Top 10 Municipios con Precios Más Altos")
    
    corr_matrix = df.select_dtypes(include=np.number).corr().round(2)
    fig_corr = px.imshow(corr_matrix, text_auto=True, color_continuous_scale='RdBu_r', title="Matriz de Correlación")
    
    graficos_disponibles = True
    
except Exception as e:
    print(f"Error al cargar datos o crear gráficos: {e}")
    graficos_disponibles = False


try:
    # Buscar todas las variantes posibles del nombre del archivo shapefile
    # Considerar mayúsculas/minúsculas y diferentes directorios
    possible_paths = [
        # Formato minúscula (como aparece en GitHub)
        "COLOMBIA/COLOMBIA.shp",
        # Formato mayúscula (como se menciona en el código original)
        "COLOMBIA/COLOMBIA.SHP",
        # Rutas relativas alternativas
        os.path.join(os.path.dirname(__file__), "COLOMBIA", "COLOMBIA.shp"),
        os.path.join(os.path.dirname(__file__), "COLOMBIA", "COLOMBIA.SHP"),
        # Rutas absolutas de desarrollo
        "/app/COLOMBIA/COLOMBIA.shp",
        "/app/COLOMBIA/COLOMBIA.SHP"
    ]
    
    # Intentar imprimir los contenidos del directorio COLOMBIA para debug
    try:
        if os.path.exists("COLOMBIA"):
            print("Contenido del directorio COLOMBIA:")
            for file in os.listdir("COLOMBIA"):
                print(f" - {file}")
    except Exception as e:
        print(f"No se pudo listar el directorio COLOMBIA: {e}")

    # Buscar el archivo en rutas posibles
    shapefile_path = None
    for path in possible_paths:
        if os.path.exists(path):
            print(f"Shapefile encontrado en: {path}")
            shapefile_path = path
            break

    if shapefile_path is None:
        raise FileNotFoundError("No se encontró el archivo shapefile en ninguna de las rutas especificadas.")

    # Cargar el shapefile
    print(f"Intentando cargar shapefile desde: {shapefile_path}")
    gdf_colombia = gpd.read_file(shapefile_path, encoding="latin1")
    print(f"Shapefile cargado exitosamente. Columnas: {gdf_colombia.columns.tolist()}")

    departamento_geo_col = 'DPTO_CNMBR'  # Ajusta según el nombre de la columna en tu shapefile

    # Normalización de nombres de departamentos para los mapas
    df[departamento_col] = df[departamento_col].str.upper().str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
    gdf_colombia[departamento_geo_col] = gdf_colombia[departamento_geo_col].str.upper().str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')

    # Datos para los mapas
    ultimo_mes = df[fecha_col].max()
    primer_mes = df[fecha_col].min()
    df_ultimo_mes = df[df[fecha_col] == ultimo_mes]
    df_primer_mes = df[df[fecha_col] == primer_mes]

    # Mapa 1: Precios por Departamento
    precio_por_dpto = df_ultimo_mes.groupby(departamento_col)[precio_col].mean().reset_index()
    gdf_merged = gdf_colombia.merge(precio_por_dpto, left_on=departamento_geo_col, right_on=departamento_col, how='left')
    gdf_merged = gdf_merged.to_crs("EPSG:4326")
    gdf_json = gdf_merged.__geo_interface__

    fig_mapa1 = px.choropleth(
        gdf_merged,
        geojson=gdf_json,
        locations=departamento_geo_col,
        featureidkey=f"properties.{departamento_geo_col}",
        color=precio_col,
        color_continuous_scale="sunsetdark",
        labels={precio_col: "Precio Promedio (COP)"},
        title=f"📍 Precios de GNCV por Departamento - {ultimo_mes.strftime('%B %Y')}",
        hover_data={departamento_col: True, precio_col: ":,.0f"}
    )
    fig_mapa1.update_geos(fitbounds="locations", visible=False)
    fig_mapa1.update_layout(margin={"r":0,"t":50,"l":0,"b":0}, template="plotly_white")

    # Mapa 2: Puntos en municipios
    puntos = df_ultimo_mes[["MUNICIPIO_EDS", "DEPARTAMENTO_EDS", precio_col, "LATITUD_MUNICIPIO", "LONGITUD_MUNICIPIO"]].dropna()
    markers = [
        dl.CircleMarker(
            center=(row["LATITUD_MUNICIPIO"], row["LONGITUD_MUNICIPIO"]),
            radius=5,
            color="black",
            fillColor="orange",
            fillOpacity=0.8,
            children=dl.Tooltip(f"{row['MUNICIPIO_EDS']} ({row['DEPARTAMENTO_EDS']}): ${row[precio_col]:,.0f}")
        )
        for _, row in puntos.iterrows()
    ]

    mapa2 = dl.Map(center=[4.57, -74.3], zoom=6, children=[
        dl.TileLayer(),
        dl.LayerGroup(markers)
    ], style={'width': '100%', 'height': '500px'})

    # Mapa 3: Variación Porcentual
    precio_inicial = df_primer_mes.groupby(departamento_col)[precio_col].mean().reset_index()
    precio_inicial.rename(columns={precio_col: 'precio_inicial'}, inplace=True)
    precio_final = df_ultimo_mes.groupby(departamento_col)[precio_col].mean().reset_index()
    precio_final.rename(columns={precio_col: 'precio_final'}, inplace=True)
    precio_comparacion = precio_inicial.merge(precio_final, on=departamento_col)
    precio_comparacion['variacion_porcentual'] = ((precio_comparacion['precio_final'] - precio_comparacion['precio_inicial']) / precio_comparacion['precio_inicial']) * 100
    gdf_variacion = gdf_colombia.merge(precio_comparacion, left_on=departamento_geo_col, right_on=departamento_col, how='left')
    gdf_variacion = gdf_variacion.to_crs("EPSG:4326")
    gdf_var_json = gdf_variacion.__geo_interface__

    vmax = max(abs(gdf_variacion['variacion_porcentual'].min()), abs(gdf_variacion['variacion_porcentual'].max()))

    fig_mapa3 = px.choropleth(
        gdf_variacion,
        geojson=gdf_var_json,
        locations=departamento_geo_col,
        featureidkey=f"properties.{departamento_geo_col}",
        color='variacion_porcentual',
        color_continuous_scale="RdBu",
        range_color=[-vmax, vmax],
        labels={"variacion_porcentual": "Variación (%)"},
        title=f"📊 Variación Porcentual del Precio de GNCV ({primer_mes.strftime('%B %Y')} - {ultimo_mes.strftime('%B %Y')})",
        hover_data={departamento_col: True, 'variacion_porcentual': ".2f"}
    )
    fig_mapa3.update_geos(fitbounds="locations", visible=False)
    fig_mapa3.update_layout(margin={"r":0,"t":50,"l":0,"b":0}, template="plotly_white")
    
    mapas_disponibles = True
    print("Mapas creados exitosamente")
except FileNotFoundError as e:
    print(f"Error al cargar el archivo shapefile: {e}")
    mapas_disponibles = False
except Exception as e:
    print(f"Error al crear mapas: {e}")
    mapas_disponibles = False
finally:
    print("Finalización del bloque try-except para mapas.")

# Construir pestañas
tabs = []

# Añadir pestañas de mapas si están disponibles
if mapas_disponibles:
    print("Agregando pestañas de mapas al dashboard")
    tabs.extend([
        dcc.Tab(label="📍 Mapa por Departamento", children=[
            dcc.Graph(figure=fig_mapa1)
        ]),
        dcc.Tab(label="📌 Mapa por Municipio (Puntos)", children=[
            html.Div(mapa2, style={"padding": "1rem"})
        ]),
        dcc.Tab(label="📊 Variación de Precios", children=[
            dcc.Graph(figure=fig_mapa3)
        ])
    ])
else:
    print("Mapas no disponibles - No se agregaron pestañas de mapas")

# Añadir pestañas de gráficos estadísticos si están disponibles
if graficos_disponibles:
    print("Agregando pestañas de gráficos estadísticos al dashboard")
    tabs.extend([
        dcc.Tab(label='Histograma', children=[dcc.Graph(figure=fig_hist)]),
        dcc.Tab(label='Boxplot por Departamento', children=[dcc.Graph(figure=fig_box)]),
        dcc.Tab(label='Evolución por Departamento', children=[dcc.Graph(figure=fig_line)]),
        dcc.Tab(label='Tendencia Global', children=[dcc.Graph(figure=fig_trend)]),
        dcc.Tab(label='Tendencia Año/Mes', children=[dcc.Graph(figure=fig_anual_mes)]),
        dcc.Tab(label='Barras por Departamento', children=[dcc.Graph(figure=fig_bar)]),
        dcc.Tab(label='Top 10 Municipios', children=[dcc.Graph(figure=fig_top_municipios)]),
        dcc.Tab(label='Matriz de Correlación', children=[dcc.Graph(figure=fig_corr)])
    ])
else:
    print("Gráficos estadísticos no disponibles - No se agregaron pestañas de gráficos")

# Layout final
if len(tabs) > 0:
    app.layout = html.Div([
        html.H1("📈 Análisis de Precios de GNCV en Colombia", style={"textAlign": "center"}),
        html.Div([
            html.P("Análisis geoespacial y estadístico de precios de GNCV", 
                  style={"textAlign": "center", "fontStyle": "italic"})
        ]),
        dcc.Tabs(tabs)
    ])
    print("Dashboard creado con éxito con", len(tabs), "pestañas")
else:
    # Mostrar mensaje de error si no hay datos disponibles
    app.layout = html.Div([
        html.H1("Error al cargar el Dashboard", style={"textAlign": "center", "color": "red"}),
        html.P("No se pudieron cargar los datos necesarios. Verifica que los archivos estén en las rutas correctas.", 
               style={"textAlign": "center"}),
        html.Div([
            html.Pre("Este es un panel de administración para diagnosticar problemas:"),
            html.Ul([
                html.Li("Archivo CSV: " + ("✅ Encontrado" if graficos_disponibles else "❌ No encontrado")),
                html.Li("Archivos shapefile: " + ("✅ Encontrados" if mapas_disponibles else "❌ No encontrados"))
            ])
        ], style={"margin": "20px auto", "maxWidth": "600px", "border": "1px solid #ddd", "padding": "20px", "backgroundColor": "#f9f9f9"})
    ])
    print("Se mostró pantalla de error por falta de datos")
    

# Ejecutar el servidor
if __name__ == '__main__':
    app.run(debug=True, port=8051)
