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
        [data-testid="stSidebar"] {
            background-color: #004080;
            color: white;
        }

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] h4 {
            color: white;
        }

        .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-top: 0.5rem !important;
        }

        [data-testid="stVerticalBlock"] > div:first-child {
            min-width: 270px !important;
            max-width: 270px !important;
        }

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

        button[kind="primary"] {
            background-color: #0066cc;
            color: white;
        }

        .css-18e3th9 h1 {
            font-size: 1.8rem !important;
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
    try:
        query = f"""
        SELECT * FROM {tabla}
        WHERE country = %s AND olt = %s AND ibs = %s
          AND startTime >= %s AND finishTime <= %s
        """
        df = pd.read_sql(query, conn, params=(ciudad, olt, ibs, inicio, fin))
    finally:
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
    try:
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
    finally:
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

col_filtros, col_datos = st.columns([1, 3.7], gap="medium")

with col_filtros:
    with st.expander("🔍 Mostrar / Ocultar filtros", expanded=True):
        st.header("Filtros")
        ciudades = obtener_valores_unicos("country")
        ciudad = st.selectbox("Selecciona una ciudad:", sorted(ciudades))
        olts = obtener_valores_unicos("olt", {"country": ciudad})
        olt = st.selectbox("Selecciona una OLT:", sorted(olts))
        ibs_list = obtener_valores_unicos("ibs", {"country": ciudad, "olt": olt})
        ibs = st.selectbox("Selecciona un IBS:", sorted(ibs_list))

        fecha_inicio = st.date_input("Fecha de inicio:", datetime.now().date())
        hora_inicio = st.time_input("Hora de inicio:", datetime.now().replace(hour=0, minute=0).time())
        fecha_fin = st.date_input("Fecha de fin:", datetime.now().date())
        hora_fin = st.time_input("Hora de fin:", datetime.now().replace(hour=23, minute=59).time())
        consultar = st.button("Consultar")

if consultar:
    inicio = pd.to_datetime(f"{fecha_inicio} {hora_inicio}")
    fin = pd.to_datetime(f"{fecha_fin} {hora_fin}")

    df_download = consultar_datos("Download_test", ciudad, olt, ibs, inicio, fin)
    df_upload = consultar_datos("Upload_test", ciudad, olt, ibs, inicio, fin)

    for df in [df_download, df_upload]:
        if not df.empty:
            df['RawSpeed_Mbps'] = (df['RawSpeed'] * 8) / 1_000_000
            df['plan'] = pd.to_numeric(df['plan'], errors='coerce')
            df['Evaluación del plan'] = df.apply(lambda row: clasificar_velocidad(row['RawSpeed_Mbps'], row['plan']), axis=1)

    with col_datos:
        st.markdown("<div class='separator'>", unsafe_allow_html=True)

        c1, c2 = st.columns(2, gap="large")
        for label, df, title in [("Download", df_download, "📉 Download"), ("Upload", df_upload, "📈 Upload")]:
            with c1 if label == "Download" else c2:
                st.markdown(f"### {title}")
                if df.empty:
                    st.warning(f"No se encontraron datos en {label}_test para los filtros seleccionados.")
                else:
                    fig = px.line(df, x='startTime', y='RawSpeed_Mbps',
                                  title=title,
                                  labels={"startTime": "Fecha/Hora", "RawSpeed_Mbps": "Velocidad (Mbps)"})
                    plan_speed = df['plan'].dropna().iloc[0] if not df['plan'].dropna().empty else None
                    if plan_speed:
                        fig.add_hline(y=plan_speed, line_dash="dash", line_color="red")
                        fig.add_annotation(x=df['startTime'].max(), y=plan_speed,
                                           text=f"Plan: {plan_speed:.2f} Mbps",
                                           showarrow=False, font=dict(color="red"), xanchor="left")
                    fig.update_layout(
                        height=280,
                        xaxis=dict(
                            tickformat="%d-%m %H:%M",
                            tickangle=45,
                            tickmode='auto',
                            nticks=20
                        )
                    )
                    st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        df_icmp = consultar_datos("icmp_test", ciudad, olt, ibs, inicio, fin)
        st.markdown("### 📊 Análisis ICMP Test")
        if df_icmp.empty:
            st.warning("No se encontraron datos en icmp_test para los filtros seleccionados.")
        else:
            df_icmp['alias'] = df_icmp['alias'].astype(str)
            df_long = pd.melt(
                df_icmp,
                id_vars=['startTime', 'alias'],
                value_vars=['AverageResponseTime', 'MaximumResponseTime', 'MinimumResponseTime'],
                var_name='Métrica',
                value_name='Tiempo'
            )
            df_long = df_long.sort_values('startTime')

            fig_icmp = px.line(
                df_long,
                x='startTime',
                y='Tiempo',
                color='alias',
                line_dash='Métrica',
                title='Tiempos de respuesta ICMP por alias y métrica',
                labels={'startTime': 'Fecha/Hora', 'Tiempo': 'Tiempo de respuesta (ms)', 'alias': 'Alias', 'Métrica': 'Métrica'}
            )
            fig_icmp.update_layout(height=400)
            st.plotly_chart(fig_icmp, use_container_width=True)

            st.markdown("### 📋 Promedio de tiempos de respuesta por alias")
            tabla_promedios = df_icmp.groupby('alias')[['AverageResponseTime', 'MaximumResponseTime', 'MinimumResponseTime']].mean().reset_index()
            tabla_promedios = tabla_promedios.round(2)
            st.dataframe(tabla_promedios, use_container_width=True)

        c3, c4 = st.columns(2, gap="large")
        for df, label, title, col in [(df_download, "Download", "🗃️ Resultados", c3), (df_upload, "Upload", "🗃️ Resultados Up", c4)]:
            with col:
                st.markdown(f"### {title}")
                if df.empty:
                    st.warning(f"No hay datos para mostrar en {label}_test.")
                else:
                    avg_speed = df["RawSpeed_Mbps"].mean()
                    st.metric(label=f"Velocidad promedio de {label}", value=f"{avg_speed:.2f} Mbps")
                    st.dataframe(df[['startTime', 'finishTime', 'RawSpeed_Mbps', 'plan', 'Evaluación del plan']],
                                 use_container_width=True, height=280)

        # Gráfica para DownloadURL
        st.markdown("---")
        st.markdown("### 📊 DownloadURL")
        if not df_download.empty and 'DownloadURL' in df_download.columns:
            df_download['fecha'] = pd.to_datetime(df_download['startTime']).dt.date
            conteo_download = df_download.groupby(['fecha', 'DownloadURL']).size().reset_index(name='conteo')
            fig_download_url = px.line(
                conteo_download,
                x='fecha',
                y='conteo',
                color='DownloadURL',
                markers=True,
                title='Cantidad diaria de registros por DownloadURL',
                labels={'fecha': 'Fecha', 'conteo': 'Cantidad de registros', 'DownloadURL': 'DownloadURL'}
            )
            fig_download_url.update_layout(
                height=450,
                xaxis_tickangle=45,
                legend_title_text='DownloadURL',
                hovermode='x unified'
            )
            st.plotly_chart(fig_download_url, use_container_width=True)
        else:
            st.warning("No se encontraron datos o columna DownloadURL en Download_test.")

        # Gráfica para UploadURL
        st.markdown("### 📊 UploadURL")
        if not df_upload.empty and 'UploadURL' in df_upload.columns:
            df_upload['fecha'] = pd.to_datetime(df_upload['startTime']).dt.date
            conteo_upload = df_upload.groupby(['fecha', 'UploadURL']).size().reset_index(name='conteo')
            fig_upload_url = px.line(
                conteo_upload,
                x='fecha',
                y='conteo',
                color='UploadURL',
                markers=True,
                title='Cantidad diaria de registros por UploadURL',
                labels={'fecha': 'Fecha', 'conteo': 'Cantidad de registros', 'UploadURL': 'UploadURL'}
            )
            fig_upload_url.update_layout(
                height=450,
                xaxis_tickangle=45,
                legend_title_text='UploadURL',
                hovermode='x unified'
            )
            st.plotly_chart(fig_upload_url, use_container_width=True)
        else:
            st.warning("No se encontraron datos o columna UploadURL en Upload_test.")
