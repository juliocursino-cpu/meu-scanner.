import streamlit as st
import pandas as pd
import requests
import io
import re
import unicodedata
import numpy as np
from scipy import stats

st.set_page_config(layout="wide", page_title="Scanner & Correct")

# =====================================================
# TOKEN FIXO
# =====================================================
TOKEN = "d128d3a3e828ca5fd800f73170dc215dfc589a1c"


# =====================================================
# FUNÇÕES
# =====================================================
def normalize_key(text):
    if not text or pd.isna(text):
        return ""

    val = str(text).upper().strip()
    val = unicodedata.normalize("NFD", val).encode("ascii", "ignore").decode("utf-8")
    val = re.sub(
        r"\b(FC|CF|SD|CD|SC|RC|SAD|CE|AFC|FK|AC|CR|CLUB|CLUBE|FUTEBOL|DE|DO|DA)\b",
        "",
        val,
    )
    val = re.sub(r"[^A-Z0-9]", "", val)
    return val.strip()


def safe_float(value):
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except:
        return 0.0


def pct_implicita(odd):
    odd = safe_float(odd)

    if odd > 0:
        return round((1 / odd) * 100)

    return 0


def calcular_pct(hist_casa, hist_fora, mercado, odd):
    total = len(hist_casa) + len(hist_fora)

    if total == 0:
        return pct_implicita(odd)

    hits = 0

    if mercado == "Over 0.5 HT":
        hits = len(hist_casa[hist_casa["TOTAL_GOLS_HT"] >= 1]) + len(
            hist_fora[hist_fora["TOTAL_GOLS_HT"] >= 1]
        )

    elif mercado == "Over 1.5 FT":
        hits = len(hist_casa[hist_casa["TOTAL_GOLS_FT"] >= 2]) + len(
            hist_fora[hist_fora["TOTAL_GOLS_FT"] >= 2]
        )

    elif mercado == "Over 2.5 FT":
        hits = len(hist_casa[hist_casa["TOTAL_GOLS_FT"] >= 3]) + len(
            hist_fora[hist_fora["TOTAL_GOLS_FT"] >= 3]
        )

    elif mercado == "BTTS":
        hits = len(
            hist_casa[
                (hist_casa["Goals_H_FT"] > 0)
                & (hist_casa["Goals_A_FT"] > 0)
            ]
        ) + len(
            hist_fora[
                (hist_fora["Goals_H_FT"] > 0)
                & (hist_fora["Goals_A_FT"] > 0)
            ]
        )

    return round((hits / total) * 100)


def carregar_jogos(data_f):
    url_jogos = f"https://api.futpythontrader.com/api/dados/jogos-do-dia/betfair/{data_f}/"
    url_base = "https://api.futpythontrader.com/api/dados/betfair/download/"

    headers = {
        "Authorization": f"Token {TOKEN}"
    }

    resp_j = requests.get(url_jogos, headers=headers)
    resp_b = requests.get(url_base, headers=headers)

    if resp_j.status_code != 200:
        raise Exception(f"Erro jogos do dia: {resp_j.status_code}")

    if resp_b.status_code != 200:
        raise Exception(f"Erro base histórica: {resp_b.status_code}")

    lista_jogos = resp_j.json().get("dados", [])

    df_h = pd.read_csv(io.BytesIO(resp_b.content))

    for col in ["Goals_H_FT", "Goals_A_FT", "Goals_H_HT", "Goals_A_HT"]:
        if col in df_h.columns:
            df_h[col] = pd.to_numeric(df_h[col], errors="coerce").fillna(0)
        else:
            df_h[col] = 0

    df_h["TOTAL_GOLS_FT"] = df_h["Goals_H_FT"] + df_h["Goals_A_FT"]
    df_h["TOTAL_GOLS_HT"] = df_h["Goals_H_HT"] + df_h["Goals_A_HT"]

    df_h["NORM_CASA"] = df_h["Home"].apply(normalize_key)
    df_h["NORM_FORA"] = df_h["Away"].apply(normalize_key)

    dados_finais = []

    for jogo in lista_jogos:
        home = jogo.get("Home", "")
        away = jogo.get("Away", "")

        h_key = normalize_key(home)
        a_key = normalize_key(away)

        hist_casa = df_h[df_h["NORM_CASA"] == h_key].tail(10)
        hist_fora = df_h[df_h["NORM_FORA"] == a_key].tail(10)

        linha = {
            "Hora": str(jogo.get("Time", "00:00"))[:5],
            "Liga": jogo.get("League", "N/A"),
            "Casa": home,
            "Fora": away,
        }

        mercados = {
            "Back Casa": ("Odd_H_Back", None),
            "Draw": ("Odd_D_Back", None),
            "Back Fora": ("Odd_A_Back", None),
            "Over 0.5 HT": ("Odd_Over05_HT_Back", "Over 0.5 HT"),
            "Over 1.5 FT": ("Odd_Over15_FT_Back", "Over 1.5 FT"),
            "Over 2.5 FT": ("Odd_Over25_FT_Back", "Over 2.5 FT"),
            "BTTS": ("Odd_BTTS_Yes_Back", "BTTS"),
            "0x1": ("Odd_CS_0x1_Lay", None),
            "1x0": ("Odd_CS_1x0_Lay", None),
            "Gol. Casa": ("Odd_CS_Goleada_H_Lay", None),
            "Gol. Fora": ("Odd_CS_Goleada_A_Lay", None),
        }

        for nome_coluna, dados in mercados.items():
            api_key, mercado = dados

            odd = safe_float(jogo.get(api_key, 0))

            if mercado:
                pct = calcular_pct(hist_casa, hist_fora, mercado, odd)
            else:
                pct = pct_implicita(odd)

            linha[nome_coluna] = f"{odd:.2f} - {pct}%"
            linha[f"{nome_coluna}_ODD"] = odd
            linha[f"{nome_coluna}_PCT"] = pct

        linha["Jogos"] = len(hist_casa) + len(hist_fora)

        dados_finais.append(linha)

    df_final = pd.DataFrame(dados_finais)

    return df_final


# =====================================================
# ABAS
# =====================================================
aba1, aba2 = st.tabs(["🚀 Scanner", "⚽ Correct"])


# =====================================================
# ABA 1 - SCANNER
# =====================================================
with aba1:
    st.title("🚀 Scanner de Jogos")

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        data_f = st.date_input("Data")

    with c2:
        max_0x1 = st.slider("Lay 0x1 — máximo %", 0, 100, 100)

    with c3:
        max_1x0 = st.slider("Lay 1x0 — máximo %", 0, 100, 100)

    with c4:
        min_o05 = st.slider("Over 0.5 HT — mínimo %", 0, 100, 0)

    with c5:
        min_o15 = st.slider("Over 1.5 FT — mínimo %", 0, 100, 0)

    if st.button("🚀 Buscar Jogos"):
        if not TOKEN or TOKEN == "COLE_SEU_TOKEN_AQUI":
            st.error("Token não configurado. Cole seu token na variável TOKEN.")
        else:
            with st.spinner("Buscando e filtrando jogos..."):
                try:
                    df_carregado = carregar_jogos(data_f)

                    if df_carregado.empty:
                        st.warning("Nenhum jogo encontrado para essa data.")
                    else:
                        st.session_state.df_scanner = df_carregado
                        st.success("Jogos carregados com sucesso!")

                except Exception as e:
                    st.error(f"Erro: {e}")

    if "df_scanner" in st.session_state:
        df_base = st.session_state.df_scanner.copy()

        if not df_base.empty:
            ligas = ["Todas"] + sorted(df_base["Liga"].dropna().unique().tolist())

            liga_sel = st.selectbox(
                "Filtrar por Liga",
                ligas,
                index=0
            )

            df_filtrado = df_base.copy()

            if liga_sel != "Todas":
                df_filtrado = df_filtrado[df_filtrado["Liga"] == liga_sel]

            df_filtrado = df_filtrado[
                (df_filtrado["0x1_PCT"] <= max_0x1)
                & (df_filtrado["1x0_PCT"] <= max_1x0)
                & (df_filtrado["Over 0.5 HT_PCT"] >= min_o05)
                & (df_filtrado["Over 1.5 FT_PCT"] >= min_o15)
            ]

            colunas_visiveis = [
                "Hora",
                "Liga",
                "Casa",
                "Fora",
                "Back Casa",
                "Draw",
                "Back Fora",
                "Over 0.5 HT",
                "Over 1.5 FT",
                "Over 2.5 FT",
                "BTTS",
                "0x1",
                "1x0",
                "Gol. Casa",
                "Gol. Fora",
                "Jogos",
            ]

            st.dataframe(
                df_filtrado[colunas_visiveis],
                use_container_width=True,
                hide_index=True,
            )

            st.caption(f"Total de jogos exibidos: {len(df_filtrado)}")

        else:
            st.info("Nenhum jogo carregado.")

    else:
        st.info("Clique em Buscar Jogos para carregar a tabela.")


# =====================================================
# ABA 2 - CORRECT
# =====================================================
with aba2:
    st.title("⚽ Analisador Correct Manual")
    st.write("Insira os dados resumidos da partida para calcular as probabilidades reais de mercado.")

    total_jogos = st.number_input(
        "Quantidade de jogos analisados no histórico:",
        min_value=1,
        value=6,
        step=1,
        key="correct_total_jogos"
    )

    st.write("---")
    st.subheader("📊 Tabela de Gols por Período")

    c1, c2, c3, c4, c5 = st.columns([1, 1, 1.2, 1, 1])

    with c1:
        st.markdown("<b style='color:#4CAF50;'>🏠 Marcados Casa</b>", unsafe_allow_html=True)
    with c2:
        st.markdown("<b style='color:#F44336;'>🏠 Sofridos Casa</b>", unsafe_allow_html=True)
    with c3:
        st.markdown("<p style='text-align:center;'><b>⏱️ Período</b></p>", unsafe_allow_html=True)
    with c4:
        st.markdown("<b style='color:#4CAF50;'>🚀 Marcados Fora</b>", unsafe_allow_html=True)
    with c5:
        st.markdown("<b style='color:#F44336;'>🚀 Sofridos Fora</b>", unsafe_allow_html=True)

    periodos = [
        ("0-15'", 0, 1, 1, 1),
        ("16-30'", 1, 2, 2, 2),
        ("31-HT", 2, 1, 2, 1),
        ("46-60'", 2, 1, 0, 0),
        ("61-75'", 1, 3, 4, 0),
        ("76-FT", 2, 2, 1, 5),
    ]

    marcados_casa = []
    sofridos_casa = []
    marcados_fora = []
    sofridos_fora = []

    for i, (periodo, mc_padrao, sc_padrao, mf_padrao, sf_padrao) in enumerate(periodos):
        col1, col2, col3, col4, col5 = st.columns([1, 1, 1.2, 1, 1])

        with col1:
            mc = st.number_input(
                f"MC {periodo}",
                min_value=0,
                value=mc_padrao,
                key=f"mc_{i}",
                label_visibility="collapsed"
            )

        with col2:
            sc = st.number_input(
                f"SC {periodo}",
                min_value=0,
                value=sc_padrao,
                key=f"sc_{i}",
                label_visibility="collapsed"
            )

        with col3:
            st.markdown(
                f"<p style='text-align:center; background-color:#262730;color:white; padding:6px; border-radius:6px;'><b>{periodo}</b></p>",
                unsafe_allow_html=True
            )

        with col4:
            mf = st.number_input(
                f"MF {periodo}",
                min_value=0,
                value=mf_padrao,
                key=f"mf_{i}",
                label_visibility="collapsed"
            )

        with col5:
            sf = st.number_input(
                f"SF {periodo}",
                min_value=0,
                value=sf_padrao,
                key=f"sf_{i}",
                label_visibility="collapsed"
            )

        marcados_casa.append(mc)
        sofridos_casa.append(sc)
        marcados_fora.append(mf)
        sofridos_fora.append(sf)

    st.write("---")

    if st.button("⚡ ANALISAR PARTIDA MANUAL", use_container_width=True):
        total_m_casa = sum(marcados_casa)
        total_s_casa = sum(sofridos_casa)
        total_m_fora = sum(marcados_fora)
        total_s_fora = sum(sofridos_fora)

        gols_por_periodo = np.array([
            marcados_casa[i] + sofridos_casa[i] + marcados_fora[i] + sofridos_fora[i]
            for i in range(6)
        ])

        total_gols_geral = np.sum(gols_por_periodo)

        if total_gols_geral > 0:
            pct_periodos = gols_por_periodo / total_gols_geral
        else:
            pct_periodos = np.array([1 / 6] * 6)

        lambda_casa = max(
            0.1,
            ((total_m_casa / total_jogos) + (total_s_fora / total_jogos)) / 2
        )

        lambda_fora = max(
            0.1,
            ((total_m_fora / total_jogos) + (total_s_casa / total_jogos)) / 2
        )

        matriz_placares = np.zeros((10, 10))

        for i in range(10):
            for j in range(10):
                matriz_placares[i, j] = (
                    stats.poisson.pmf(i, lambda_casa)
                    * stats.poisson.pmf(j, lambda_fora)
                )

        peso_ate_65 = np.sum(pct_periodos[0:4]) + (pct_periodos[4] * 0.33)

        p_vitoria_casa = np.sum(np.tril(matriz_placares, -1))
        p_vitoria_fora = np.sum(np.triu(matriz_placares, 1))
        p_empate = np.sum(np.diag(matriz_placares))

        p_0x1_ft = matriz_placares[0, 1]
        p_1x0_ft = matriz_placares[1, 0]

        p_goleada_casa = np.sum(matriz_placares[4:, :])
        p_goleada_fora = np.sum(matriz_placares[:, 4:])

        p_over_15 = 1 - (
            matriz_placares[0, 0]
            + matriz_placares[0, 1]
            + matriz_placares[1, 0]
        )

        p_over_ht = 1 - (
            stats.poisson.pmf(0, lambda_casa * 0.45)
            * stats.poisson.pmf(0, lambda_fora * 0.45)
        )

        def fmt_odd(p):
            if p <= 0:
                return "100.00"
            odd = 1 / p
            return f"{odd:.2f}" if odd <= 100 else "100.00"

        resultados = [
            {
                "Mercado": "Back Casa",
                "Probabilidade": f"{p_vitoria_casa * 100:.1f}%",
                "Odd Justa": fmt_odd(p_vitoria_casa),
            },
            {
                "Mercado": "Back Fora",
                "Probabilidade": f"{p_vitoria_fora * 100:.1f}%",
                "Odd Justa": fmt_odd(p_vitoria_fora),
            },
            {
                "Mercado": "Lay Draw",
                "Probabilidade": f"{p_empate * 100:.1f}%",
                "Odd Justa": fmt_odd(p_empate),
            },
            {
                "Mercado": "Over HT",
                "Probabilidade": f"{p_over_ht * 100:.1f}%",
                "Odd Justa": fmt_odd(p_over_ht),
            },
            {
                "Mercado": "Over 1.5 FT",
                "Probabilidade": f"{p_over_15 * 100:.1f}%",
                "Odd Justa": fmt_odd(p_over_15),
            },
            {
                "Mercado": "Lay 1x0 FT",
                "Probabilidade": f"{p_1x0_ft * 100:.1f}%",
                "Odd Justa": fmt_odd(p_1x0_ft),
            },
            {
                "Mercado": "Lay 0x1 FT",
                "Probabilidade": f"{p_0x1_ft * 100:.1f}%",
                "Odd Justa": fmt_odd(p_0x1_ft),
            },
            {
                "Mercado": "Lay 1x0 até 65m",
                "Probabilidade": f"{(p_1x0_ft * peso_ate_65) * 100:.1f}%",
                "Odd Justa": fmt_odd(p_1x0_ft * peso_ate_65),
            },
            {
                "Mercado": "Lay 0x1 até 65m",
                "Probabilidade": f"{(p_0x1_ft * peso_ate_65) * 100:.1f}%",
                "Odd Justa": fmt_odd(p_0x1_ft * peso_ate_65),
            },
            {
                "Mercado": "Lay Goleada Casa",
                "Probabilidade": f"{p_goleada_casa * 100:.1f}%",
                "Odd Justa": fmt_odd(p_goleada_casa),
            },
            {
                "Mercado": "Lay Goleada Fora",
                "Probabilidade": f"{p_goleada_fora * 100:.1f}%",
                "Odd Justa": fmt_odd(p_goleada_fora),
            },
        ]

        df_resultados = pd.DataFrame(resultados)

        st.subheader("📌 Resultado da Análise")
        st.dataframe(df_resultados, use_container_width=True, hide_index=True)

        st.write("---")

        c_a, c_b, c_c = st.columns(3)

        with c_a:
            st.metric("Lambda Casa", f"{lambda_casa:.2f}")

        with c_b:
            st.metric("Lambda Fora", f"{lambda_fora:.2f}")

        with c_c:
            st.metric("Peso até 65m", f"{peso_ate_65 * 100:.1f}%")