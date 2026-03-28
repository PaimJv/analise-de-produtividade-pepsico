import streamlit as st
from logic import init_state, load_and_process_base, voltar_nivel, apply_color_logic
from sidebar import render_initial_sidebar, render_advanced_filters
from ia_engine import get_ai_insights
from components import plot_drilldown_chart, render_dynamic_table
import os, sys

# Adiciona a pasta temporária do executável ao PATH do Python para os imports funcionarem
if getattr(sys, 'frozen', False):
    bundle_dir = sys._MEIPASS
    sys.path.append(bundle_dir)

# # No lugar de: api_key = st.secrets["GROQ_API_KEY"]
# api_key = os.environ.get("GROQ_API_KEY")

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Auditoria Estratégica Facilities",
    page_icon="🕵️‍♂️",
    layout="wide"
)

# Inicializa o estado da sessão (drill_path)
init_state()

# Recupera a chave de API dos secrets
api_key = st.secrets.get("GROQ_API_KEY", None)

# --- 2. INTERFACE INICIAL ---
st.title("📊 Auditoria de Produtividade YoY")
st.caption("Análise de Variação de Custos com Auditoria Exaustiva por IA")
st.markdown("---")

# Renderiza a primeira parte da sidebar (Modo e Upload)
apenas_completos, uploaded_files = render_initial_sidebar()

if len(uploaded_files) >= 2:
    # --- 3. PROCESSAMENTO DE DADOS ---
    # df_raw já vem com a coluna 'Desc_Conta' formatada ("Descrição - Código")
    df_raw, ano_at, ano_ant = load_and_process_base(uploaded_files, apenas_completos)
    
    if isinstance(df_raw, str):
        st.error(f"Erro no processamento: {df_raw}")
        st.stop()

    # --- 4. FILTROS AVANÇADOS (SIDEBAR ETAPA 2) ---
    # Só renderiza após o df_raw estar pronto
    selecao_meses, dimensoes_ia, foco_res, filtros_dinamicos = render_advanced_filters(df_raw)

    # --- 5. LÓGICA DE FILTRAGEM E DRILL-DOWN ---
    # A. Filtro de Meses
    meses_filtro = selecao_meses if selecao_meses else sorted(df_raw['Mes'].unique())
    df_filtrado = df_raw[df_raw['Mes'].isin(meses_filtro)]
    
    # B. Filtros Inteligentes (Cross-filtering da Sidebar)
    # Aqui é onde a mágica acontece: se você filtrar uma Localidade, 
    # o df_filtrado diminui e tudo que vem abaixo dele (Gráfico/Tabela) obedece.
    if filtros_dinamicos:
        for col, valores in filtros_dinamicos.items():
            if valores:
                # Garantimos que a comparação seja feita como string para evitar erros de tipo
                df_filtrado = df_filtrado[df_filtrado[col].astype(str).isin(valores)]
    
    # C. Lógica de Drill-down (Navegação por clique)
    # df_active é o que os gráficos e tabelas realmente usam
    df_active = df_filtrado.copy()
    for col, val in st.session_state.drill_path:
        if col in df_active.columns:
            df_active = df_active[df_active[col].astype(str) == str(val)]

    # Breadcrumbs (Navegação Visual)
    path_txt = " > ".join([str(v) for c, v in st.session_state.drill_path]) if st.session_state.drill_path else "Corporativo"
    st.info(f"📍 **Localização:** `Início > {path_txt}`")

    # --- 6. HIERARQUIA DE NAVEGAÇÃO ---
    hierarquia = ['Desc_Conta', 'P_L', 'VP', 'Localidade', 'Centro_Custo', 'Desc_Material']
    labels = {
        'Desc_Conta': 'Conta (Classe de Custo)', 
        'P_L': 'P&L', 
        'VP': 'VP', 
        'Localidade': 'Localidade', 
        'Centro_Custo': 'Centro de Custo', 
        'Desc_Material': 'Material'
    }
    
    nivel = len(st.session_state.drill_path)

    if nivel < len(hierarquia):
        atual_col = hierarquia[nivel]
        label_atual = labels.get(atual_col, atual_col)

        # Gráfico de Impacto
        # st.plotly_chart(plot_drilldown_chart(df_active, atual_col, ano_at, ano_ant), use_container_width=True)
        
        # Cabeçalho da Tabela e Botão Voltar
        st.markdown("---")
        c1, c2 = st.columns([4, 1])
        with c1:
            st.subheader(f"📂 Visão Mensal: {label_atual}")
        with c2:
            if nivel > 0:
                st.write("##")
                if st.button("⬅️ Voltar Nível", use_container_width=True, key="btn_back_main"):
                    voltar_nivel()
                    st.rerun()

        # Matriz de Variação
        df_pivot = render_dynamic_table(df_active, atual_col, ano_at, ano_ant)
        cols_meses = [c for c in df_pivot.columns if c != 'Total Geral']

        # Exibição da Tabela com Seleção de Linha
        event = st.dataframe(
            df_pivot.style.format(precision=2, decimal=',', thousands='.')
            .map(apply_color_logic, subset=cols_meses),
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            key=f"tab_drill_{nivel}"
        )

        st.markdown("---")
        st.subheader("📑 Auditoria Hierárquica de Variações")

        if not dimensoes_ia:
            st.warning("Selecione as dimensões na barra lateral.")
        else:
            from logic import render_report_ui, prepare_report_data            
            # 1. Pré-calculamos tudo (Rápido, fora da recursão)
            with st.spinner("Processando indicadores..."):
                df_master = prepare_report_data(df_filtrado, dimensoes_ia, ano_at, ano_ant)
            
            # 2. Renderizamos a UI (Instantâneo, apenas consulta a df_master)
            render_report_ui(df_master, dimensoes_ia,ano_at, ano_ant, foco_res)

    else:
        # Nível Final (Material)
        st.success("🎯 Detalhe máximo atingido (Análise por Material).")
        if st.button("⬅️ Voltar ao Início", use_container_width=True):
            st.session_state.drill_path = []
            st.rerun()
else:
    st.info("👋 Para começar, carregue os arquivos CSV de dois anos diferentes na barra lateral.")