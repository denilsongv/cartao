import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import uuid
import re
import os
from dateutil.relativedelta import relativedelta

# ------------------- CONFIGURAÇÃO DE CAMINHOS -------------------
# ------------------- CONEXÃO COM GOOGLE SHEETS VIA STREAMLIT SECRETS -------------------
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

try:
    service_account_info = dict(st.secrets["gcp_service_account"])

    creds = Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPE
    )

    client = gspread.authorize(creds)

    SPREADSHEET_ID = st.secrets["google_sheets"]["spreadsheet_id"]
    WORKSHEET_NAME = st.secrets["google_sheets"].get("worksheet", "lancamentos")

    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)

except Exception as e:
    st.error(f"Erro ao conectar com o Google Sheets: {e}")
    st.stop()

# ------------------- CONEXÃO COM GOOGLE SHEETS -------------------
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
client = gspread.authorize(creds)
SPREADSHEET_ID = "1oyZ3pLMa0BLGiJW9HafzUpSchY1xnauojLG47Hi2ZwI"
sheet = client.open_by_key(SPREADSHEET_ID).worksheet("lancamentos")

# ------------------- FUNÇÕES AUXILIARES -------------------
def formatar_data_exibicao(data_str):
    try:
        return datetime.strptime(str(data_str).strip(), "%d/%m/%Y").strftime("%d-%m-%Y")
    except:
        return str(data_str).strip()

def converter_data_para_armazenar(data_str):
    data_str = str(data_str).strip()

    if re.match(r"^\d{2}/\d{2}/\d{4}$", data_str):
        try:
            datetime.strptime(data_str, "%d/%m/%Y")
            return data_str
        except:
            pass

    if re.match(r"^\d{2}-\d{2}-\d{4}$", data_str):
        try:
            dt = datetime.strptime(data_str, "%d-%m-%Y")
            return dt.strftime("%d/%m/%Y")
        except:
            pass

    return data_str

def validar_data(data_str):
    if not re.match(r"^\d{2}-\d{2}-\d{4}$", str(data_str).strip()):
        return False
    try:
        datetime.strptime(str(data_str).strip(), "%d-%m-%Y")
        return True
    except:
        return False

def validar_mes_competencia(mes_str):
    if not re.match(r"^\d{2}/\d{4}$", str(mes_str).strip()):
        return False
    try:
        datetime.strptime("01/" + mes_str.strip(), "%d/%m/%Y")
        return True
    except:
        return False

def formatar_moeda_br(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

def normalizar_booleano(v):
    return str(v).strip().lower() in ["true", "1", "sim", "yes"]

def corrige_valor(v):
    """
    Corrige valores vindos da planilha para float, sem explodir para milhar.
    Casos tratados:
    - 1234.56
    - 1234,56
    - 1.234,56
    - 1,234.56
    - R$ 1.234,56
    """
    if pd.isna(v):
        return 0.0

    if isinstance(v, (int, float)):
        return round(float(v), 2)

    v = str(v).strip()

    if not v:
        return 0.0

    # Remove moeda, espaços e caracteres estranhos
    v = v.replace("R$", "").replace(" ", "")
    v = re.sub(r"[^\d,.\-]", "", v)

    # Se tiver vírgula e ponto
    if "," in v and "." in v:
        if v.rfind(",") > v.rfind("."):
            # formato BR: 1.234,56
            v = v.replace(".", "")
            v = v.replace(",", ".")
        else:
            # formato US: 1,234.56
            v = v.replace(",", "")

    # Se tiver só vírgula
    elif "," in v:
        v = v.replace(",", ".")

    # Se tiver só ponto
    elif "." in v:
        partes = v.split(".")
        if len(partes) > 2:
            # ex: 1.234.567.89
            v = "".join(partes[:-1]) + "." + partes[-1]
        elif len(partes) == 2 and len(partes[1]) == 3:
            # ex: 1.234 -> milhar
            v = "".join(partes)

    try:
        return round(float(v), 2)
    except:
        return 0.0

def carregar_dados():
    try:
        dados = sheet.get_all_records()

        colunas = [
            "data", "descricao", "valor", "bandeira",
            "parcelas_total", "parcela_atual",
            "mes_competencia", "id", "conferido"
        ]

        if not dados:
            return pd.DataFrame(columns=colunas)

        df = pd.DataFrame(dados)

        # Garante colunas obrigatórias
        for col in colunas:
            if col not in df.columns:
                if col == "valor":
                    df[col] = 0.0
                elif col in ["parcelas_total", "parcela_atual"]:
                    df[col] = 1
                elif col == "conferido":
                    df[col] = False
                else:
                    df[col] = ""

        # Corrige valor com robustez
        df["valor"] = df["valor"].apply(corrige_valor)
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0).round(2)

        df["parcelas_total"] = pd.to_numeric(
            df["parcelas_total"], errors="coerce"
        ).fillna(1).astype(int)

        df["parcela_atual"] = pd.to_numeric(
            df["parcela_atual"], errors="coerce"
        ).fillna(1).astype(int)

        df["conferido"] = df["conferido"].apply(normalizar_booleano)

        df["data"] = df["data"].astype(str).str.strip()
        df["descricao"] = df["descricao"].astype(str).str.strip()
        df["bandeira"] = df["bandeira"].astype(str).str.strip()
        df["mes_competencia"] = df["mes_competencia"].astype(str).str.strip()
        df["id"] = df["id"].astype(str).str.strip()

        return df[colunas]

    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame(columns=[
            "data", "descricao", "valor", "bandeira",
            "parcelas_total", "parcela_atual",
            "mes_competencia", "id", "conferido"
        ])

def salvar_dados(df):
    try:
        sheet.clear()

        colunas_ordem = [
            "data", "descricao", "valor", "bandeira",
            "parcelas_total", "parcela_atual",
            "mes_competencia", "id", "conferido"
        ]

        if not df.empty:
            df = df.copy().fillna("")

            # Garante tipos corretos antes de salvar
            df["valor"] = df["valor"].apply(corrige_valor).round(2)
            df["parcelas_total"] = pd.to_numeric(df["parcelas_total"], errors="coerce").fillna(1).astype(int)
            df["parcela_atual"] = pd.to_numeric(df["parcela_atual"], errors="coerce").fillna(1).astype(int)
            df["conferido"] = df["conferido"].apply(lambda x: "TRUE" if normalizar_booleano(x) else "FALSE")

            df = df[colunas_ordem]

            dados = [df.columns.tolist()] + df.values.tolist()
            sheet.update(values=dados, range_name="A1")
        else:
            sheet.update([colunas_ordem], "A1")

        return True

    except Exception as e:
        st.error(f"Erro ao salvar dados: {e}")
        return False

def adicionar_lancamentos(lancamentos):
    df = carregar_dados()
    novos = pd.DataFrame(lancamentos)
    novos["valor"] = novos["valor"].apply(corrige_valor).round(2)
    novos["conferido"] = False

    df = pd.concat([df, novos], ignore_index=True)

    if salvar_dados(df):
        st.success("Lançamento(s) adicionado(s)!")
        return True
    return False

def excluir_lancamento_por_id(id_lancamento):
    df = carregar_dados()

    if id_lancamento in df["id"].values:
        df = df[df["id"] != id_lancamento]
        if salvar_dados(df):
            st.success(f"Lançamento(s) com ID {id_lancamento} excluído(s).")
            return True
    else:
        st.warning(f"ID {id_lancamento} não encontrado.")
        return False

# ------------------- LÓGICA DE PARCELAS -------------------
def avancar_mes(mes_ano_str, num_meses):
    mes, ano = map(int, mes_ano_str.split("/"))
    novo_mes = mes + num_meses
    novo_ano = ano + (novo_mes - 1) // 12
    novo_mes = ((novo_mes - 1) % 12) + 1
    return f"{novo_mes:02d}/{novo_ano}"

def gerar_parcelas(data_compra, descricao, valor_total, bandeira, num_parcelas, mes_primeira_parcela):
    parcelas = []
    id_unico = str(uuid.uuid4())

    valor_total = corrige_valor(valor_total)
    valor_parcela = round(valor_total / num_parcelas, 2)

    valores = [valor_parcela] * num_parcelas
    soma = round(sum(valores), 2)
    diferenca = round(valor_total - soma, 2)
    valores[-1] = round(valores[-1] + diferenca, 2)

    for i in range(1, num_parcelas + 1):
        valor = valores[i - 1]
        mes_competencia = avancar_mes(mes_primeira_parcela, i - 1)

        parcela = {
            "data": data_compra,
            "descricao": descricao,
            "valor": valor,
            "bandeira": bandeira,
            "parcelas_total": num_parcelas,
            "parcela_atual": i,
            "mes_competencia": mes_competencia,
            "id": id_unico,
            "conferido": False
        }
        parcelas.append(parcela)

    return parcelas

def gerar_avista(data_compra, descricao, valor, bandeira, mes_competencia):
    return [{
        "data": data_compra,
        "descricao": descricao,
        "valor": corrige_valor(valor),
        "bandeira": bandeira,
        "parcelas_total": 1,
        "parcela_atual": 1,
        "mes_competencia": mes_competencia,
        "id": str(uuid.uuid4()),
        "conferido": False
    }]

# ------------------- INTERFACE STREAMLIT -------------------
st.set_page_config(page_title="Controle de Cartões", layout="wide")
st.title("💳 Controle de Compras no Cartão de Crédito")

# Estados do filtro
if "mes_filtro" not in st.session_state:
    st.session_state["mes_filtro"] = datetime.now().strftime("%m/%Y")

if "bandeira_filtro" not in st.session_state:
    st.session_state["bandeira_filtro"] = "Todas"

# Sidebar
st.sidebar.header("🔍 Filtrar lançamentos")
mes_filtro = st.sidebar.text_input("Mês/Ano (MM/AAAA)", value=st.session_state["mes_filtro"])
bandeira_filtro = st.sidebar.selectbox(
    "Bandeira",
    ["Todas", "Visa", "Elo", "Mastercard", "American Express", "Mercado Pago"],
    index=["Todas", "Visa", "Elo", "Mastercard", "American Express", "Mercado Pago"].index(
        st.session_state["bandeira_filtro"]
    ) if st.session_state["bandeira_filtro"] in ["Todas", "Visa", "Elo", "Mastercard", "American Express", "Mercado Pago"] else 0
)

if st.sidebar.button("Filtrar"):
    st.session_state["mes_filtro"] = mes_filtro.strip()
    st.session_state["bandeira_filtro"] = bandeira_filtro
    st.rerun()

# Carrega dados
df = carregar_dados()

# Filtra
if not df.empty:
    df_filtrado = df[df["mes_competencia"] == st.session_state["mes_filtro"]]

    if st.session_state["bandeira_filtro"] != "Todas":
        df_filtrado = df_filtrado[df_filtrado["bandeira"] == st.session_state["bandeira_filtro"]]

    total_fatura = df_filtrado["valor"].sum()

    st.metric(
        label=f"💰 Total da fatura ({st.session_state['bandeira_filtro']} - {st.session_state['mes_filtro']})",
        value=formatar_moeda_br(total_fatura)
    )

    if not df_filtrado.empty:
        df_edit = df_filtrado.copy()

        df_edit["data_exibicao"] = df_edit["data"].apply(formatar_data_exibicao)
        df_edit["parcela"] = df_edit.apply(
            lambda row: "única" if row["parcelas_total"] == 1 else f"{row['parcela_atual']}/{row['parcelas_total']}",
            axis=1
        )

        df_edit = df_edit[[
            "data_exibicao", "descricao", "valor", "bandeira",
            "parcela", "mes_competencia", "conferido", "id"
        ]]

        df_edit = df_edit.rename(columns={"data_exibicao": "data"})

        st.subheader("📋 Lançamentos do período")
        edited_df = st.data_editor(
            df_edit,
            use_container_width=True,
            column_config={
                "conferido": st.column_config.CheckboxColumn("Conferido"),
                "id": st.column_config.TextColumn("ID", disabled=True),
                "data": st.column_config.TextColumn("Data (dd-mm-aaaa)"),
                "descricao": st.column_config.TextColumn("Descrição"),
                "valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f", step=0.01),
                "bandeira": st.column_config.TextColumn("Bandeira"),
                "parcela": st.column_config.TextColumn("Parcela", disabled=True),
                "mes_competencia": st.column_config.TextColumn("Mês Competência (MM/AAAA)")
            },
            key="editor"
        )

        if st.button("💾 Salvar alterações"):
            df_full = carregar_dados().copy()
            erros = []

            for _, row_edit in edited_df.iterrows():
                id_edit = str(row_edit["id"]).strip()
                mask = df_full["id"] == id_edit

                if mask.any():
                    data_edit = str(row_edit["data"]).strip()
                    mes_edit = str(row_edit["mes_competencia"]).strip()
                    valor_edit = corrige_valor(row_edit["valor"])

                    if not validar_data(data_edit):
                        erros.append(f"Data inválida no ID {id_edit}: {data_edit}")
                        continue

                    if not validar_mes_competencia(mes_edit):
                        erros.append(f"Mês de competência inválido no ID {id_edit}: {mes_edit}")
                        continue

                    data_armazenar = converter_data_para_armazenar(data_edit)

                    df_full.loc[mask, "data"] = data_armazenar
                    df_full.loc[mask, "descricao"] = str(row_edit["descricao"]).strip()
                    df_full.loc[mask, "bandeira"] = str(row_edit["bandeira"]).strip()
                    df_full.loc[mask, "mes_competencia"] = mes_edit
                    df_full.loc[mask, "valor"] = valor_edit
                    df_full.loc[mask, "conferido"] = bool(row_edit["conferido"])

            if erros:
                for erro in erros:
                    st.error(erro)
            else:
                if salvar_dados(df_full):
                    st.success("Alterações salvas com sucesso!")
                    st.rerun()

        st.subheader("🗑️ Excluir lançamento")
        col1, col2 = st.columns([3, 1])

        with col1:
            id_para_excluir = st.text_input("ID da parcela ou compra (copie da tabela)")

        with col2:
            st.write("")
            if st.button("Excluir este ID", type="primary"):
                if id_para_excluir:
                    excluir_lancamento_por_id(id_para_excluir.strip())
                    st.rerun()
                else:
                    st.warning("Digite um ID.")
    else:
        st.info("Nenhum lançamento para o filtro selecionado.")
else:
    st.info("Nenhum lançamento ainda. Adicione abaixo.")

# ---------- FORMULÁRIO DE NOVO LANÇAMENTO ----------
st.header("➕ Adicionar novo gasto")

sugestoes_descricoes = [
    "gasolina", "supermercado", "lanche", "mercado livre", "shopee",
    "sacolão", "pizza", "academia", "padaria", "uber", "óleo carro", "óleo moto", "Outro"
]

if "form_data_compra" not in st.session_state:
    st.session_state["form_data_compra"] = datetime.now().strftime("%d-%m-%Y")
if "form_descricao" not in st.session_state:
    st.session_state["form_descricao"] = sugestoes_descricoes[0]
if "form_descricao_outro" not in st.session_state:
    st.session_state["form_descricao_outro"] = ""
if "form_valor" not in st.session_state:
    st.session_state["form_valor"] = 0.01
if "form_bandeira" not in st.session_state:
    st.session_state["form_bandeira"] = "Visa"
if "form_parcelas" not in st.session_state:
    st.session_state["form_parcelas"] = 1
if "form_mes_primeira" not in st.session_state:
    st.session_state["form_mes_primeira"] = (datetime.now() + relativedelta(months=1)).strftime("%m/%Y")

def limpar_formulario():
    st.session_state["form_data_compra"] = datetime.now().strftime("%d-%m-%Y")
    st.session_state["form_descricao"] = sugestoes_descricoes[0]
    st.session_state["form_descricao_outro"] = ""
    st.session_state["form_valor"] = 0.01
    st.session_state["form_bandeira"] = "Visa"
    st.session_state["form_parcelas"] = 1
    st.session_state["form_mes_primeira"] = (datetime.now() + relativedelta(months=1)).strftime("%m/%Y")

with st.form("novo_lancamento", clear_on_submit=False):
    col1, col2 = st.columns(2)

    with col1:
        data_compra_str = st.text_input(
            "Data da compra (dd-mm-aaaa)",
            value=st.session_state["form_data_compra"],
            key="data_compra_input"
        )

        descricao_opcao = st.selectbox(
            "Descrição",
            sugestoes_descricoes,
            index=sugestoes_descricoes.index(st.session_state["form_descricao"]),
            key="descricao_select"
        )

        descricao_outro = ""
        if descricao_opcao == "Outro":
            descricao_outro = st.text_input(
                "Digite a descrição",
                value=st.session_state["form_descricao_outro"],
                key="descricao_outro_input"
            )

        descricao_final = descricao_outro.strip() if descricao_opcao == "Outro" else descricao_opcao

        valor_total = st.number_input(
            "Valor total (R$)",
            min_value=0.01,
            step=0.01,
            format="%.2f",
            value=float(st.session_state["form_valor"]),
            key="valor_input"
        )

        bandeira = st.selectbox(
            "Bandeira",
            ["Visa", "Elo", "Mastercard", "American Express", "Mercado Pago"],
            index=["Visa", "Elo", "Mastercard", "American Express", "Mercado Pago"].index(
                st.session_state["form_bandeira"]
            ),
            key="bandeira_select"
        )

    with col2:
        parcelas = st.number_input(
            "Número de parcelas",
            min_value=1,
            max_value=24,
            value=int(st.session_state["form_parcelas"]),
            step=1,
            key="parcelas_input"
        )

        mes_primeira = st.text_input(
            "Mês da primeira parcela (MM/AAAA)",
            value=st.session_state["form_mes_primeira"],
            key="mes_primeira_input"
        )

    col_buttons = st.columns(2)

    with col_buttons[0]:
        submitted = st.form_submit_button("Lançar compra", use_container_width=True)

    with col_buttons[1]:
        limpar = st.form_submit_button("Limpar campos", use_container_width=True)

    st.session_state["form_data_compra"] = data_compra_str
    st.session_state["form_descricao"] = descricao_opcao
    st.session_state["form_descricao_outro"] = descricao_outro if descricao_opcao == "Outro" else ""
    st.session_state["form_valor"] = valor_total
    st.session_state["form_bandeira"] = bandeira
    st.session_state["form_parcelas"] = parcelas
    st.session_state["form_mes_primeira"] = mes_primeira

if submitted:
    erro = False

    if not descricao_final:
        st.error("Descrição obrigatória.")
        erro = True
    elif corrige_valor(valor_total) <= 0:
        st.error("Valor deve ser maior que zero.")
        erro = True
    elif not validar_mes_competencia(mes_primeira):
        st.error("Mês da primeira parcela inválido. Use MM/AAAA.")
        erro = True
    elif not validar_data(data_compra_str):
        st.error("Data inválida. Use o formato dd-mm-aaaa (ex: 15-04-2026).")
        erro = True

    if not erro:
        data_armazenar = converter_data_para_armazenar(data_compra_str)

        if parcelas == 1:
            lancamentos = gerar_avista(
                data_armazenar,
                descricao_final,
                valor_total,
                bandeira,
                mes_primeira
            )
        else:
            lancamentos = gerar_parcelas(
                data_armazenar,
                descricao_final,
                valor_total,
                bandeira,
                parcelas,
                mes_primeira
            )

        if adicionar_lancamentos(lancamentos):
            limpar_formulario()
            st.rerun()

if limpar:
    limpar_formulario()
    st.rerun()

# Sidebar com vencimentos
st.sidebar.markdown("---")
st.sidebar.subheader("📅 Vencimentos")
vencimentos = {
    "Elo": "10",
    "American Express": "16",
    "Visa": "25",
    "Mercado Pago": "17"
}

for cartao, dia in vencimentos.items():
    st.sidebar.text(f"{cartao}: dia {dia}")
