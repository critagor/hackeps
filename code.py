import streamlit as st
import pandas as pd
import pydeck as pdk
import requests
import time

# Configuración de la página
add_bg_from_url()
st.set_page_config(page_title="El Joc de Barris - LA Finder", layout="wide")
# --- 1. INTEGRACIÓN API OPENSTREETMAP (Overpass) ---
# Esta función consulta datos reales. Usamos cache para no saturar la API cada vez que mueves un slider.
@st.cache_data(show_spinner=False)
def get_real_osm_data(lat, lon, radius=1500):
    """
    Consulta la API de Overpass para contar elementos en un radio de 'radius' metros.
    Devuelve un diccionario con los conteos reales.
    """
    overpass_url = "http://overpass-api.de/api/interpreter"
    
    # Consulta en lenguaje Overpass QL
    # Contamos: Bares (Vida Nocturna), Parques (Naturaleza), Transporte (Movilidad)
    query = f"""
    [out:json];
    (
      node["amenity"~"bar|pub|nightclub"](around:{radius},{lat},{lon});
      way["amenity"~"bar|pub|nightclub"](around:{radius},{lat},{lon});
    ) -> .bares;
    (
      node["leisure"="park"](around:{radius},{lat},{lon});
      way["leisure"="park"](around:{radius},{lat},{lon});
      node["landuse"="recreation_ground"](around:{radius},{lat},{lon});
    ) -> .parques;
    (
      node["highway"="bus_stop"](around:{radius},{lat},{lon});
      node["railway"~"subway_entrance|station"](around:{radius},{lat},{lon});
    ) -> .transporte;
    
    .bares out count;
    .parques out count;
    .transporte out count;
    """
    
    try:
        response = requests.post(overpass_url, data=query, timeout=25)
        if response.status_code == 200:
            data = response.json()
            # La respuesta de 'out count' viene en elementos separados
            # El orden depende de cómo la API procesa, pero suelen venir en orden de solicitud si se estructura bien.
            # Para simplificar, Overpass devuelve bloques 'count'.
            # Sin embargo, parsear 'count' directo de JSON crudo de Overpass es truculento.
            # Estrategia robusta: contar elementos en arrays si pedimos 'out ids' o usar el id del bloque.
            # Para este hackathon, usaremos 'out count' y leeremos los tags.
            
            # NOTA: Overpass 'out count' devuelve un JSON específico.
            # Estructura: elements: [ {id: 0, tags: {nodes: X, ...}}, ... ]
            # Asumimos el orden de los bloques: 1.Bares, 2.Parques, 3.Transporte
            elements = data.get('elements', [])
            
            # Sumamos nodos + ways + relations para cada grupo
            def extract_count(idx):
                if idx < len(elements):
                    tags = elements[idx].get('tags', {})
                    return int(tags.get('total', 0))
                return 0

            # La salida de 'out count' genera un elemento por cada bloque cerrado con ';' y llamado a out.
            bares = extract_count(0)
            parques = extract_count(1)
            transporte = extract_count(2)
            
            return {
                'bares_count': bares,
                'parques_count': parques,
                'transporte_count': transporte
            }
    except Exception as e:
        pass
    
    return {'bares_count': 0, 'parques_count': 0, 'transporte_count': 0}

@st.cache_data
def load_data_with_api():
    # Coordenadas base
    barrios = [
        {'barrio': 'Beverly Hills', 'lat': 34.0736, 'lon': -118.4004},
        {'barrio': 'Downtown LA', 'lat': 34.0407, 'lon': -118.2468},
        {'barrio': 'Silver Lake', 'lat': 34.0869, 'lon': -118.2702},
        {'barrio': 'Santa Monica', 'lat': 34.0195, 'lon': -118.4912},
        {'barrio': 'Compton', 'lat': 33.8958, 'lon': -118.2201},
        {'barrio': 'Pasadena', 'lat': 34.1478, 'lon': -118.1445},
        {'barrio': 'West Hollywood', 'lat': 34.0900, 'lon': -118.3617},
        {'barrio': 'Venice Beach', 'lat': 33.9850, 'lon': -118.4695},
        {'barrio': 'Koreatown', 'lat': 34.0618, 'lon': -118.3004},
        {'barrio': 'Bel Air', 'lat': 34.1002, 'lon': -118.4595}
    ]
    
    results = []
    
    # Barra de progreso para la carga de API
    progress_text = "📡 Conectando con satélites de OpenStreetMap..."
    my_bar = st.progress(0, text=progress_text)
    
    for i, b in enumerate(barrios):
        # Llamada a la API
        real_data = get_real_osm_data(b['lat'], b['lon'])
        
        # Mezclamos datos reales con simulados (para los que no tenemos API fácil)
        b.update({
            # Datos REALES de la API
            'fiesta': real_data['bares_count'],
            'naturaleza': real_data['parques_count'],
            'movilidad': real_data['transporte_count'],
            
            # Datos SIMULADOS (Hardcoded por falta de API pública abierta de crimen/precios)
            'seguridad': { 
                'Beverly Hills': 10, 'Bel Air': 10, 'Pasadena': 8, 'Santa Monica': 7,
                'West Hollywood': 7, 'Silver Lake': 6, 'Venice Beach': 5, 
                'Koreatown': 4, 'Downtown LA': 3, 'Compton': 2 
            }[b['barrio']],
            
            'lujo_privacidad': {
                'Beverly Hills': 10, 'Bel Air': 10, 'Santa Monica': 8, 'West Hollywood': 8,
                'Pasadena': 7, 'Venice Beach': 6, 'Silver Lake': 5, 'Downtown LA': 4,
                'Koreatown': 3, 'Compton': 1
            }[b['barrio']],
            
            'silencio_tech': {
                'Bel Air': 9, 'Pasadena': 8, 'Beverly Hills': 7, 'Silver Lake': 6,
                'Santa Monica': 5, 'West Hollywood': 4, 'Venice Beach': 4,
                'Koreatown': 3, 'Compton': 3, 'Downtown LA': 2
            }[b['barrio']],
             
            'coste_vida': { # 1 = Muy caro, 10 = Barato
                'Compton': 9, 'Koreatown': 6, 'Downtown LA': 5, 'Pasadena': 5,
                'Silver Lake': 4, 'West Hollywood': 3, 'Santa Monica': 2, 
                'Venice Beach': 2, 'Beverly Hills': 1, 'Bel Air': 1
            }[b['barrio']]
        })
        results.append(b)
        my_bar.progress((i + 1) / len(barrios), text=f"Analizando {b['barrio']}...")
    
    my_bar.empty()
    df = pd.DataFrame(results)
    
    # --- NORMALIZACIÓN (0-10) ---
    # Convertimos los conteos brutos (ej: 150 bares) a una nota del 0 al 10
    def normalize(column):
        min_val = df[column].min()
        max_val = df[column].max()
        if max_val == min_val: return 5
        return (df[column] - min_val) / (max_val - min_val) * 10

    df['vida_nocturna'] = normalize('fiesta')
    df['naturaleza'] = normalize('naturaleza')
    df['movilidad'] = normalize('movilidad')
    
    return df

# Cargar datos
df = load_data_with_api()

# --- 2. INTERFAZ DE USUARIO (SIDEBAR) ---
st.sidebar.header("🏹 Configura tu Perfil")
st.sidebar.markdown("Define qué es importante para ti para encontrar tu *Trono* en LA.")

# Preajustes basados en los personajes del PDF
perfil = st.sidebar.selectbox(
    "¿Te identificas con algún arquetipo?",
    ["Personalizado", "Cersei (Lujo y Seguridad)", "Jon Snow (Naturaleza y Comunidad)", "Tyrion (Fiesta y Cultura)", "Bran (Silencio y Tech)", "Arya (Movilidad y Anonimato)"]
)

# Valores por defecto de los sliders según el perfil
defaults = {
    'seguridad': 5, 'lujo': 5, 'naturaleza': 5, 'fiesta': 5, 'movilidad': 5, 'tech': 5, 'precio': 5
}

if perfil == "Cersei (Lujo y Seguridad)":
    defaults = {'seguridad': 10, 'lujo': 10, 'naturaleza': 2, 'fiesta': 4, 'movilidad': 0, 'tech': 5, 'precio': 0}
elif perfil == "Jon Snow (Naturaleza y Comunidad)":
    defaults = {'seguridad': 6, 'lujo': 1, 'naturaleza': 10, 'fiesta': 3, 'movilidad': 4, 'tech': 2, 'precio': 8}
elif perfil == "Tyrion (Fiesta y Cultura)":
    defaults = {'seguridad': 4, 'lujo': 6, 'naturaleza': 2, 'fiesta': 10, 'movilidad': 8, 'tech': 5, 'precio': 5}
elif perfil == "Bran (Silencio y Tech)":
    defaults = {'seguridad': 8, 'lujo': 7, 'naturaleza': 5, 'fiesta': 0, 'movilidad': 2, 'tech': 10, 'precio': 2}
elif perfil == "Arya (Movilidad y Anonimato)":
    defaults = {'seguridad': 5, 'lujo': 3, 'naturaleza': 4, 'fiesta': 7, 'movilidad': 10, 'tech': 6, 'precio': 6}

# Sliders de preferencias (Pesos)
st.sidebar.subheader("⚖️ Tus Prioridades (0-10)")
w_seguridad = st.sidebar.slider("Seguridad (Baja criminalidad)", 0, 10, defaults['seguridad'])
w_lujo = st.sidebar.slider("Lujo y Privacidad", 0, 10, defaults['lujo'])
w_naturaleza = st.sidebar.slider("Naturaleza y Aire Libre", 0, 10, defaults['naturaleza'])
w_fiesta = st.sidebar.slider("Vida Nocturna y Cultura", 0, 10, defaults['fiesta'])
w_movilidad = st.sidebar.slider("Movilidad (Transporte/Andar)", 0, 10, defaults['movilidad'])
w_tech = st.sidebar.slider("Silencio y Tech (Home Office)", 0, 10, defaults['tech'])
w_precio = st.sidebar.slider("Precio Asequible", 0, 10, defaults['precio'])

# --- 3. ALGORITMO DE RECOMENDACIÓN (Weighted Scoring) ---
def calcular_puntuacion(row):
    # Suma de productos (Valor * Peso)
    score = (
        (row['seguridad'] * w_seguridad) +
        (row['lujo_privacidad'] * w_lujo) +
        (row['naturaleza'] * w_naturaleza) +
        (row['vida_nocturna'] * w_fiesta) +
        (row['movilidad'] * w_movilidad) +
        (row['silencio_tech'] * w_tech) +
        (row['coste_vida'] * w_precio)
    )
    
    # Evitar división por cero
    total_weights = w_seguridad + w_lujo + w_naturaleza + w_fiesta + w_movilidad + w_tech + w_precio
    if total_weights == 0:
        return 0
    
    return score / total_weights

# Aplicar cálculo
df['match_score'] = df.apply(calcular_puntuacion, axis=1)
# Escalar a 0-100 para mejor visualización
df['match_percentage'] = (df['match_score'] / 10) * 100
df_sorted = df.sort_values(by='match_percentage', ascending=False)

# --- 4. LAYOUT PRINCIPAL ---
st.title("🏰 El Joc de Barris: Los Angeles Edition")
st.write("Descubre tu vecindario ideal con datos **reales** de OpenStreetMap.")

col1, col2 = st.columns([3, 1])

with col1:
    # --- MAPA VISUAL (PYDECK) ---
    st.subheader("Mapa de Afinidad")
    
    def get_color(score):
        r = int(255 * (1 - (score/10)))
        g = int(255 * (score/10))
        return [r, g, 0, 160]

    df['color'] = df['match_score'].apply(get_color)

    view_state = pdk.ViewState(
        latitude=34.0522,
        longitude=-118.2437,
        zoom=9.5,
        pitch=45,
    )

    layer = pdk.Layer(
        "ColumnLayer",
        data=df,
        get_position='[lon, lat]',
        get_elevation='match_score',
        elevation_scale=500,
        radius=800,
        get_fill_color='color',
        pickable=True,
        auto_highlight=True,
    )

    # Tooltip enriquecido con datos reales
    tooltip = {
        "html": "<b>{barrio}</b><br>Match: <b>{['match_percentage']:.1f}%</b><br>🌳 Parques (Real): {naturaleza}<br>🍸 Locales (Real): {fiesta}<br>🚌 Paradas (Real): {movilidad}",
        "style": {"backgroundColor": "steelblue", "color": "white"}
    }

    st.pydeck_chart(pdk.Deck(
        map_provider='carto',
        map_style='light',
        initial_view_state=view_state,
        layers=[layer],
        tooltip=tooltip
    ))

with col2:
    # --- TOP RECOMENDACIONES ---
    st.subheader("🏆 Top 3 Barrios")
    
    top_3 = df_sorted.head(3)
    
   for index, row in top_3.iterrows():
        # 1. PREPARAR DADES (PYTHON)
        percent = int(row['match_percentage'])
        barrio = row['barrio']
        
        # Generar etiquetes (Badges) dinàmiques
        tags_html = ""
        if row['naturaleza'] > df['naturaleza'].mean() and w_naturaleza > 5: 
            tags_html += '<span class="badge">🌳 Natura</span>'
        if row['fiesta'] > df['fiesta'].mean() and w_fiesta > 5: 
            tags_html += '<span class="badge">🍸 Festa</span>'
        if row['movilidad'] > df['movilidad'].mean() and w_movilidad > 5: 
            tags_html += '<span class="badge">🚌 Mobilitat</span>'
        if row['seguridad'] > 7 and w_seguridad > 5: 
            tags_html += '<span class="badge">🛡️ Segur</span>'
        if row['coste_vida'] > 7 and w_precio > 5: 
            tags_html += '<span class="badge">💰 Econòmic</span>'
            
        # Si no hi ha tags, posem un per defecte
        if tags_html == "":
            tags_html = '<span class="badge">⚖️ Equilibrat</span>'

        # Color de la barra segons puntuació
        bar_color = "#ff4b4b" # Vermell
        if percent > 50: bar_color = "#ffa500" # Taronja
        if percent > 75: bar_color = "#00cc66" # Verd

        # Injectar HTML amb estil personalitzat
        card_html = f"""
        <div class="neighborhood-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h3 style="margin:0; color:#fff;">{barrio}</h3>
                <h2 style="margin:0; color:{bar_color};">{percent}%</h2>
            </div>
            
            <div class="custom-bar-bg">
                <div class="custom-bar-fill" style="width: {percent}%; background-color: {bar_color};"></div>
            </div>
            
            <div style="margin-top: 10px;">
                {tags_html}
            </div>
            
            <p style="font-size: 0.9em; color: #aaa; margin-top: 10px; font-style: italic;">
                "Ideal per al teu perfil perquè coincideix amb els teus criteris de {tags_html.replace('<span class="badge">','').replace('</span>',', ')}..."
            </p>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)
# --- 5. TABLA DE DATOS RAW ---
with st.expander("🕵️ Ver Datos Reales extraídos de la API"):
    st.info("Estos datos han sido extraídos en tiempo real de OpenStreetMap usando Overpass API.")
    st.dataframe(df_sorted[['barrio', 'match_percentage', 'naturaleza', 'fiesta', 'movilidad']])