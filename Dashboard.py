from google.cloud import bigquery
from google.oauth2 import service_account
import pandas as pd
import plotly.express as px
import streamlit as st

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard TSE", layout="wide")


# --- LEITURA DOS DADOS COM CHAVE DE ACESSO (SECRETS) ---
@st.cache_data
def carregar_dados():
    # Recupera a chave JSON do Service Account configurada nos Secrets do Streamlit
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"]
    )

    # Conecta no BigQuery com as credenciais do seu projeto
   client = bigquery.Client(
        project="estudoinicial-507322",
        credentials=credentials,
        location="US",
    )
    # Consulta otimizada (traz os dados pré-agregados para economizar memória e acelerar a busca)
    query = """
    SELECT 
        CAST(ano AS INT64) AS ano,
        COALESCE(sigla_uf, 'N/A') AS sigla_uf,
        COALESCE(sigla_partido, 'N/A') AS sigla_partido,
        COALESCE(cargo, 'N/A') AS cargo,
        COALESCE(genero, 'N/A') AS genero,
        COUNT(1) AS total_candidatos
    FROM `basedosdados.br_tse_eleicoes.candidatos`
    WHERE ano IS NOT NULL
    GROUP BY ano, sigla_uf, sigla_partido, cargo, genero
    """

    # Executa e converte para DataFrame
    query_job = client.query(query)
    return query_job.to_dataframe()


df = carregar_dados()

# --- FILTROS (SIDEBAR) ---
st.sidebar.header("Filtros")

anos_disponiveis = (
    sorted(df["ano"].dropna().unique(), reverse=True)
    if "ano" in df.columns
    else []
)
partidos_disponiveis = (
    sorted(df["sigla_partido"].dropna().unique())
    if "sigla_partido" in df.columns
    else []
)
ufs_disponiveis = (
    sorted(df["sigla_uf"].dropna().unique()) if "sigla_uf" in df.columns else []
)
cargos_disponiveis = (
    sorted(df["cargo"].dropna().unique()) if "cargo" in df.columns else []
)

ano_selecionado = st.sidebar.selectbox(
    "Selecione o Ano / Eleição:", options=["Todos"] + list(anos_disponiveis)
)
ufs_selecionadas = st.sidebar.multiselect(
    "Selecione a(s) UF(s):", options=ufs_disponiveis
)
partidos_selecionados = st.sidebar.multiselect(
    "Selecione o(s) Partido(s):", options=partidos_disponiveis
)
cargos_selecionados = st.sidebar.multiselect(
    "Selecione o(s) Cargo(s):", options=cargos_disponiveis
)

# --- APLICAÇÃO DOS FILTROS ---
df_filtrado = df.copy()

if ano_selecionado != "Todos" and "ano" in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado["ano"] == ano_selecionado]

if ufs_selecionadas and "sigla_uf" in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado["sigla_uf"].isin(ufs_selecionadas)]

if partidos_selecionados and "sigla_partido" in df_filtrado.columns:
    df_filtrado = df_filtrado[
        df_filtrado["sigla_partido"].isin(partidos_selecionados)
    ]

if cargos_selecionados and "cargo" in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado["cargo"].isin(cargos_selecionados)]

# --- MÉTRICAS ---
total_candidatos = int(df_filtrado["total_candidatos"].sum())
total_partidos = (
    df_filtrado[df_filtrado["sigla_partido"] != "N/A"][
        "sigla_partido"
    ].nunique()
    if not df_filtrado.empty
    else 0
)

col_m1, col_m2 = st.columns(2)
col_m1.metric(
    label=f"Total de Candidatos ({ano_selecionado})",
    value=f"{total_candidatos:,}".replace(",", "."),
)
col_m2.metric(label="Total de Partidos Únicos", value=total_partidos)

st.markdown("---")

# --- PAINEL DE VISUALIZAÇÕES ---
if not df_filtrado.empty:

    # --- TOP 5 UFs (BARRAS) ---
    st.subheader("Top 5 Estados (UF) com Mais Candidatos")

    top5_uf = (
        df_filtrado[df_filtrado["sigla_uf"] != "N/A"]
        .groupby("sigla_uf")["total_candidatos"]
        .sum()
        .reset_index(name="Quantidade")
        .sort_values(by="Quantidade", ascending=False)
        .head(5)
    )

    if not top5_uf.empty:
        fig_uf = px.bar(
            top5_uf,
            x="sigla_uf",
            y="Quantidade",
            text="Quantidade",
            labels={"sigla_uf": "Estado (UF)", "Quantidade": "Candidatos"},
            color="Quantidade",
            color_continuous_scale="Blues",
        )
        fig_uf.update_traces(textposition="outside")
        fig_uf.update_layout(
            showlegend=False,
            height=300,
            margin={"t": 30, "b": 10, "l": 0, "r": 0},
        )

        col_bar1, col_bar2, col_bar3 = st.columns([1, 2, 1])
        with col_bar2:
            st.plotly_chart(fig_uf, use_container_width=True)

    st.markdown("---")

    # --- GRÁFICOS PERCENTUAIS ---
    col_g1, col_g2 = st.columns(2)

    # 1. Percentual por Gênero
    with col_g1:
        st.subheader("Percentual por Gênero")
        df_sexo = (
            df_filtrado.groupby("genero")["total_candidatos"]
            .sum()
            .reset_index(name="Quantidade")
        )

        fig_sexo = px.pie(
            df_sexo,
            names="genero",
            values="Quantidade",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_sexo.update_traces(textinfo="percent+label")
        fig_sexo.update_layout(
            height=320, margin={"t": 20, "b": 20, "l": 0, "r": 0}
        )
        st.plotly_chart(fig_sexo, use_container_width=True)

    # 2. Percentual por Partido (Top 5 + Outros)
    with col_g2:
        st.subheader("Percentual por Partido (Top 5)")
        df_partido = (
            df_filtrado[df_filtrado["sigla_partido"] != "N/A"]
            .groupby("sigla_partido")["total_candidatos"]
            .sum()
            .reset_index(name="Quantidade")
        )
        df_partido = df_partido.sort_values(by="Quantidade", ascending=False)

        top5_partidos = df_partido.head(5)
        outros_qtd = df_partido.iloc[5:]["Quantidade"].sum()

        if outros_qtd > 0:
            outros_df = pd.DataFrame(
                [{"sigla_partido": "Outros", "Quantidade": outros_qtd}]
            )
            df_partido_final = pd.concat(
                [top5_partidos, outros_df], ignore_index=True
            )
        else:
            df_partido_final = top5_partidos

        fig_partido = px.pie(
            df_partido_final,
            names="sigla_partido",
            values="Quantidade",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        fig_partido.update_traces(textinfo="percent+label")
        fig_partido.update_layout(
            height=320, margin={"t": 20, "b": 20, "l": 0, "r": 0}
        )
        st.plotly_chart(fig_partido, use_container_width=True)

else:
    st.warning("Nenhum dado encontrado para os filtros selecionados.")

st.markdown("---")
