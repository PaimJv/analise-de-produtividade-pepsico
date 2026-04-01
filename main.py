import streamlit as st
from logic import init_state, load_and_process_base, voltar_nivel, apply_color_logic, get_highlights_summary
from sidebar import render_initial_sidebar, render_advanced_filters
from components import render_dynamic_table
import sys
import gc
import pandas as pd

# --- 0. COMPATIBILIDADE EXECUTÁVEL ---
if getattr(sys, 'frozen', False):
    bundle_dir = sys._MEIPASS
    sys.path.append(bundle_dir)

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Auditoria Estratégica Facilities",
    page_icon="https://raw.githubusercontent.com/PaimJv/analise-financeira-pepsico/db28a88acbdc6ae9a227d018546b1479e9eb94b0/logo-projeto-custos.ico",
    layout="wide"
)

# Inicializa o estado da sessão (drill_path e dados)
init_state()

# --- 2. GESTÃO DE ESTADO DE DADOS (OTIMIZAÇÃO CLOUD) ---
# Inicializamos chaves para armazenar os dados processados na RAM da sessão
if 'df_raw' not in st.session_state:
    st.session_state.df_raw = None
if 'ano_at' not in st.session_state:
    st.session_state.ano_at = None
if 'ano_ant' not in st.session_state:
    st.session_state.ano_ant = None
if 'last_files_hash' not in st.session_state:
    st.session_state.last_files_hash = None
if 'dims_com_paridade' not in st.session_state:
    st.session_state.dims_com_paridade = []

# --- 3. INTERFACE INICIAL ---
st.title("📊 Auditoria de Produtividade YoY")
st.caption("Análise de Variação de Custos com Auditoria Exaustiva por IA")
st.markdown("---")

# Renderiza a sidebar inicial
uploaded_files = render_initial_sidebar()

# Proteção contra None: Se não houver arquivos, o hash é uma string vazia
if uploaded_files:
    # Caso o Streamlit retorne um único objeto em vez de lista (segurança extra)
    if isinstance(uploaded_files, list):
        current_files_hash = str([f.name for f in uploaded_files]) + str(len(uploaded_files))
    else:
        current_files_hash = uploaded_files.name
else:
    current_files_hash = ""

# Lógica para detectar se os arquivos mudaram (para resetar o cache da sessão)
# current_files_hash = str([f.name for f in uploaded_files]) + str(len(uploaded_files))

if uploaded_files and current_files_hash != st.session_state.last_files_hash:
    st.session_state.df_raw = None # Força reprocessamento
    st.session_state.last_files_hash = current_files_hash
    st.session_state.drill_path = [] # Reseta navegação ao trocar arquivos

if len(uploaded_files) >= 2:
    
    # --- 4. PROCESSAMENTO OTIMIZADO ---
    if st.session_state.df_raw is None:
        with st.spinner("🚀 Otimizando base de dados..."):
            res, at, ant, aviso = load_and_process_base(uploaded_files)
            
            if isinstance(res, pd.DataFrame):
                # 1. Detectamos as dimensões válidas
                from logic import obter_dimensoes_validas
                dims_validas = obter_dimensoes_validas(res, at, ant)
                
                # 2. Salvamos TUDO na sessão
                st.session_state.df_raw = res
                st.session_state.ano_at = at
                st.session_state.ano_ant = ant
                st.session_state.dims_com_paridade = dims_validas # SALVANDO AQUI
                st.session_state.aviso_incompleto = aviso
                gc.collect()
            else:
                st.error(f"Erro no processamento: {res}")
                st.stop()

    # Atalhos (Garante que as variáveis existam para a sidebar)
    df_raw = st.session_state.df_raw
    ano_at = st.session_state.ano_at
    ano_ant = st.session_state.ano_ant
    dims_com_paridade = st.session_state.dims_com_paridade

    # --- 5. FILTROS AVANÇADOS ---
    # Agora passando os 4 argumentos necessários
    selecao_meses, dimensoes_ia, foco_res, filtros_dinamicos = render_advanced_filters(
        df_raw, 
        dims_com_paridade, 
        ano_at, 
        ano_ant
    )

    # --- 6. LÓGICA DE FILTRAGEM ---
    meses_filtro = selecao_meses if selecao_meses else sorted(df_raw['Mes'].unique())
    df_filtrado = df_raw[df_raw['Mes'].isin(meses_filtro)]
    
    if filtros_dinamicos:
        for col, valores in filtros_dinamicos.items():
            if valores:
                df_filtrado = df_filtrado[df_filtrado[col].astype(str).isin(valores)]
                
    # --- 6.1 RESUMO DE DESTAQUES (OPORTUNIDADES) ---
    resumo_opps = get_highlights_summary(df_filtrado, ano_at, ano_ant)
    
    if resumo_opps:
        with st.expander("💡 **Destaques de Produtividade YoY**", expanded=True):
            st.markdown("Principais oportunidades de redução:")
            for item in resumo_opps:
                st.write(item)
    else:
        st.info("Nenhuma oportunidade de produtividade acima de R$ 1.000,00 identificada no período selecionado.")
    
    # --- 7. DRILL-DOWN ---
    df_active = df_filtrado.copy()
    for col, val in st.session_state.drill_path:
        if col in df_active.columns:
            df_active = df_active[df_active[col].astype(str) == str(val)]

    if st.session_state.aviso_incompleto:
            a = st.session_state.aviso_incompleto
            st.warning(f"⚠️ **Atenção:** O mês de **{a['mes_nome']}** está incompleto no relatório (registros apenas até o dia **{a['dia']}**).")

    path_txt = " > ".join([str(v) for c, v in st.session_state.drill_path]) if st.session_state.drill_path else "Corporativo"
    # st.info(f"📍 **Localização:** `Início > {path_txt}`")

    # --- 8. HIERARQUIA DE NAVEGAÇÃO ---
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

        # Cabeçalho e Botão Voltar
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

        # Exibição da Tabela
        event = st.dataframe(
            df_pivot.style.format(precision=2, decimal=',', thousands='.')
            .map(apply_color_logic, subset=cols_meses),
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            key=f"tab_drill_{nivel}"
        )

        # Lógica de Clique (Drill-down)
        if event and "selection" in event and event["selection"]["rows"]:
            idx = event["selection"]["rows"][0]
            val_selecionado = df_pivot.index[idx]
            if val_selecionado != "Total Geral":
                st.session_state.drill_path.append((atual_col, val_selecionado))
                st.rerun()

        st.markdown("---")
        st.subheader("📑 Auditoria Hierárquica de Variações")

        if not dimensoes_ia:
            st.warning("Selecione as dimensões na barra lateral para o relatório detalhado.")
        else:
            from logic import render_report_ui, prepare_report_data            
            
            # Criamos uma string única da seleção atual (ex: "1-2" para Jan e Fev)
            filtro_id = "-".join(map(str, sorted(meses_filtro)))
            
            # O st.empty() garante que o espaço possa ser limpo
            placeholder = st.empty()
            
            with placeholder.container(): # <--- ADICIONE ESTA LINHA
                with st.spinner("Gerando auditoria detalhada..."):
                    df_master, dims_analise = prepare_report_data(df_filtrado, dimensoes_ia, ano_at, ano_ant)
                    render_report_ui(df_master, dims_analise, ano_at, ano_ant, foco_res, selecao_meses=meses_filtro)
        
    else:
        # Nível Final (Material)
        st.success("🎯 Detalhe máximo atingido (Análise por Material).")
        if st.button("⬅️ Voltar ao Início", use_container_width=True):
            st.session_state.drill_path = []
            st.rerun()
else:
    st.info("👋 Para começar, carregue os arquivos de dois anos diferentes na barra lateral.")