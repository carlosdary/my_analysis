import streamlit as st
import pandas as pd
import pymysql
from datetime import datetime
import plotly.express as px

# Configurar la página
st.set_page_config(layout="wide")

# Estilo CSS personalizado
st.markdown("""
    <style>
        /* Reducir tamaño fuente del título principal */
        .css-18e3th9 h1 {
            font-size: 1.8rem !important;
        }

        .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-top: 0.5rem !important;
        }

        /* Menú filtros: ancho moderado */
        [data-testid="stVerticalBlock"] > div:first-child {
            min-width: 270px !important;
            max-width: 270px !important;
        }

        /* Ajustar gráficos y tablas */
        .stPlotlyChart {
            margin-top: 1rem;
            margin-bottom: 1rem;
        }

        .stDataFrame {
            margin-top: 0.5rem;
            max-height: 300px;
            overflow-y: auto;
        }

        .separator {
            border-left: 2px solid #ccc;
            height: 100%;
            padding-left: 20px;
        }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def consultar_datos(tabla, ciudad, olt, ibs, inicio, fin):
    conn = pymysql.connect(
        host='10.165.1.197',
        user='user_rnpo',
        password='5qQJ*v6ecfg8',
        database='olt_measurements'
    )
    query = f"""
    SELECT * FROM {tabla}
    WHERE country = %s AND olt = %s AND ibs = %s
      AND startTime >= %s AND finishTime <= %s
    """
    df = pd.read_sql(query, conn, params=(ciudad, olt, ibs, inicio, fin))
    conn.close()
    return df

@st.cache_data
def obtener_valores_unicos(columna, filtros=None):
    conn = pymysql.connect(
        host='10.165.1.197',
        user='user_rnpo',
        password='5qQJ*v6ecfg8',
        database='olt_measurements'
    )
    query = f"SELECT DISTINCT {columna} FROM Download_test"
    condiciones = []
    valores = []
    if filtros:
        for k, v in filtros.items():
            condiciones.append(f"{k} = %s")
            valores.append(v)
        if condiciones:
            query += " WHERE " + " AND ".join(condiciones)

    cursor = conn.cursor()
    cursor.execute(query, tuple(valores))
    resultados = [row[0] for row in cursor.fetchall()]
    conn.close()
    return resultados

def clasificar_velocidad(raw_speed_mbps, plan_speed):
    if pd.isnull(plan_speed) or plan_speed == 0:
        return "Plan desconocido"
    diff = (raw_speed_mbps - plan_speed) / plan_speed
    if -0.15 <= diff <= 0.15:
        return "Normal"
    elif 0.15 < diff < 0.20:
        return "Ligeramente por encima"
    elif -0.20 < diff < -0.15:
        return "Ligeramente por debajo"
    elif diff >= 0.20:
        return "Muy por encima"
    elif diff <= -0.20:
        return "Muy por debajo"
    else:
        return "Indefinido"

# Título principal
st.title("Análisis de pruebas de velocidad - Download & Upload Test")

# Layout de columnas con proporción 1 : 3.7
col_filtros, col_datos = st.columns([1, 3.7], gap="medium")

# Filtros colapsables
with col_filtros:
    with st.expander("🔍 Mostrar / Ocultar filtros", expanded=True):
        st.header("Filtros")
        ciudades = obtener_valores_unicos("country")
        ciudad = st.selectbox("Selecciona una ciudad:", sorted(ciudades))
        olts = obtener_valores_unicos("olt", {"country": ciudad})
        olt = st.selectbox("Selecciona una OLT:", sorted(olts))
        ibs_list = obtener_valores_unicos("ibs", {"country": ciudad, "olt": olt})
        ibs = st.selectbox("Selecciona un IBS:", sorted(ibs_list))

        # Rango de fechas y horas
        fecha_inicio = st.date_input("Fecha de inicio:", datetime.now().date())
        hora_inicio = st.time_input("Hora de inicio:", datetime.now().replace(hour=0, minute=0).time())
        fecha_fin = st.date_input("Fecha de fin:", datetime.now().date())
        hora_fin = st.time_input("Hora de fin:", datetime.now().replace(hour=23, minute=59).time())
        consultar = st.button("Consultar")

# Procesar fechas
inicio = pd.to_datetime(f"{fecha_inicio} {hora_inicio}")
fin = pd.to_datetime(f"{fecha_fin} {hora_fin}")

if consultar:
    df_download = consultar_datos("Download_test", ciudad, olt, ibs, inicio, fin)
    df_upload = consultar_datos("Upload_test", ciudad, olt, ibs, inicio, fin)

    for df in [df_download, df_upload]:
        if not df.empty:
            df['RawSpeed_Mbps'] = (df['RawSpeed'] * 8) / 1_000_000
            df['plan'] = pd.to_numeric(df['plan'], errors='coerce')
            df['Evaluación del plan'] = df.apply(lambda row: clasificar_velocidad(row['RawSpeed_Mbps'], row['plan']), axis=1)

    with col_datos:
        st.markdown("<div class='separator'>", unsafe_allow_html=True)

        # Gráficos
        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.markdown("### 📉 Download")
            if df_download.empty:
                st.warning("No se encontraron datos en Download_test para los filtros seleccionados.")
            else:
                fig = px.line(df_download, x='startTime', y='RawSpeed_Mbps', markers=True)
                plan_speed = df_download['plan'].dropna().iloc[0] if not df_download['plan'].dropna().empty else None
                if plan_speed:
                    fig.add_hline(y=plan_speed, line_dash="dash", line_color="red")
                    fig.add_annotation(
                        x=df_download['startTime'].max(),
                        y=plan_speed,
                        text=f"Plan: {plan_speed:.2f} Mbps",
                        showarrow=False,
                        font=dict(color="red"),
                        xanchor="left"
                    )
                fig.update_layout(height=280, title="Download")
                st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.markdown("### 📈 Upload")
            if df_upload.empty:
                st.warning("No se encontraron datos en Upload_test para los filtros seleccionados.")
            else:
                fig = px.line(df_upload, x='startTime', y='RawSpeed_Mbps', markers=True)
                plan_speed = df_upload['plan'].dropna().iloc[0] if not df_upload['plan'].dropna().empty else None
                if plan_speed:
                    fig.add_hline(y=plan_speed, line_dash="dash", line_color="red")
                    fig.add_annotation(
                        x=df_upload['startTime'].max(),
                        y=plan_speed,
                        text=f"Plan: {plan_speed:.2f} Mbps",
                        showarrow=False,
                        font=dict(color="red"),
                        xanchor="left"
                    )
                fig.update_layout(height=280, title="Upload")
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # Tablas con altura reducida
        c3, c4 = st.columns(2, gap="large")
        with c3:
            st.markdown("### 🗃️ Resultados")
            if df_download.empty:
                st.warning("No hay datos para mostrar en Download_test.")
            else:
                st.dataframe(df_download[['startTime', 'finishTime', 'RawSpeed_Mbps', 'plan', 'Evaluación del plan']],
                             use_container_width=True, height=280)

        with c4:
            st.markdown("### 🗃️ Resultados")
            if df_upload.empty:
                st.warning("No hay datos para mostrar en Upload_test.")
            else:
                st.dataframe(df_upload[['startTime', 'finishTime', 'RawSpeed_Mbps', 'plan', 'Evaluación del plan']],
                             use_container_width=True, height=280)

        st.markdown("</div>", unsafe_allow_html=True)
