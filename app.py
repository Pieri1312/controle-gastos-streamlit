import pandas as pd
import streamlit as st
from datetime import datetime
import plotly.express as px
import os

# Arquivos
ARQUIVO_GASTOS = "gastos.csv"
ARQUIVO_RENDA = "renda.csv"
CATEGORIAS = ["Alimentacao", "Transporte", "Lazer", "Moradia", "Saude", "Educacao", "Contas", "Outros", "Viagem", "Compras"]

CORES = {
    "Alimentacao": "#FF6347",
    "Transporte": "#4682B4",
    "Lazer": "#32CD32",
    "Moradia": "#DAA520",
    "Saude": "#8A2BE2",
    "Educacao": "#FFD700",
    "Contas": "#6A5ACD",
    "Outros": "#808080",
    "Viagem": "#00CED1",
    "Compras": "#FF1493"
}

st.set_page_config(page_title="💸 Controle de Gastos", layout="wide", page_icon="💰")
st.title("💸 Controle Pessoal de Gastos")

# --- Funcoes ---
def carregar_gastos():
    if not os.path.exists(ARQUIVO_GASTOS):
        return pd.DataFrame(columns=["Data", "Valor", "Categoria", "Descricao"])
    df = pd.read_csv(ARQUIVO_GASTOS)
    df["Data"] = pd.to_datetime(df["Data"], errors='coerce')
    return df.dropna(subset=["Data"])

def salvar_gastos(df):
    df.to_csv(ARQUIVO_GASTOS, index=False)

def carregar_renda():
    if not os.path.exists(ARQUIVO_RENDA):
        return 0.0
    return pd.read_csv(ARQUIVO_RENDA)["Renda"].iloc[0]

def salvar_renda(valor):
    pd.DataFrame({"Renda": [valor]}).to_csv(ARQUIVO_RENDA, index=False)

# --- Sidebar ---
st.sidebar.header("💰 Inserir Renda Mensal")
renda_input = st.sidebar.number_input("Renda (R$)", min_value=0.0, value=carregar_renda(), step=10.0, format="%.2f")
if st.sidebar.button("Salvar Renda"):
    salvar_renda(renda_input)
    st.sidebar.success("Renda salva com sucesso!")

st.sidebar.markdown("---")
st.sidebar.header("➕ Adicionar Gasto")
with st.sidebar.form("form_gasto", clear_on_submit=True):
    data = st.date_input("Data", datetime.today())
    valor = st.number_input("Valor (R$)", min_value=0.01, format="%.2f")
    categoria = st.selectbox("Categoria", CATEGORIAS)
    descricao = st.text_input("Descricao")
    submit = st.form_submit_button("Registrar Gasto")

    if submit:
        novo = pd.DataFrame([[data, valor, categoria, descricao]], columns=["Data", "Valor", "Categoria"])
        df_gastos = carregar_gastos()
        df_gastos = pd.concat([df_gastos, novo], ignore_index=True)
        salvar_gastos(df_gastos)
        st.success("Gasto registrado com sucesso!")
        st.experimental_rerun()

# --- Dados ---
df = carregar_gastos()
renda = carregar_renda()

if df.empty:
    st.warning("Nenhum gasto registrado ainda. Use o menu lateral para adicionar.")
    st.stop()

# --- Filtros ---
meses = df["Data"].dt.to_period("M").astype(str).sort_values(ascending=False).unique()
mes_selecionado = st.selectbox("📅 Mês:", meses)
df_mes = df[df["Data"].dt.to_period("M").astype(str) == mes_selecionado]

# --- Metricas ---
st.markdown("### 📈 Visão Geral do Mês")
col1, col2, col3 = st.columns(3)
col1.metric("Renda do Mês", f"R$ {renda:,.2f}")
total = df_mes["Valor"].sum()
col2.metric("Total Gasto", f"R$ {total:,.2f}")
col3.metric("Saldo Restante", f"R$ {renda - total:,.2f}", delta=f"{((renda - total)/renda*100) if renda else 0:.1f}%")

# --- Gráfico de Categorias ---
cat_data = df_mes.groupby("Categoria")["Valor"].sum().reset_index()
fig = px.bar(cat_data, x="Valor", y="Categoria", orientation='h', color="Categoria",
             color_discrete_map=CORES, title="Gastos por Categoria")
st.plotly_chart(fig, use_container_width=True)

# --- Tabela e Exclusao ---
st.subheader("🧾 Detalhamento dos Gastos")
def deletar_gasto(idx):
    df = carregar_gastos()
    df = df.drop(index=idx).reset_index(drop=True)
    salvar_gastos(df)
    st.success("Gasto excluído com sucesso!")
    st.experimental_rerun()

for i, row in df_mes.iterrows():
    with st.expander(f"{row['Data'].date()} - R$ {row['Valor']:.2f} - {row['Categoria']}"):
        if st.button("Excluir", key=f"del_{i}"):
            deletar_gasto(row.name)

st.caption("Desenvolvido por Pieri 💻")
