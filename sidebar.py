import streamlit as st
import pandas as pd
from logic import reset_navigation
from utils import LABELS_MAP

def render_initial_sidebar():
    """
    Renderiza os controlos básicos na barra lateral antes do processamento.
    Configura o modo de comparação e o carregamento de ficheiros.
    """
    st.sidebar.title("Seleção de conteúdos")
    
    modo_envio = st.sidebar.radio(
        "Modo de Envio:",
        ["Arquivos Separados (YoY)", "Arquivo Único (Biênio/Histórico)"],
        index=0,
        key="modo_envio"
    )
    
    st.sidebar.markdown("---")
    
    if modo_envio == "Arquivos Separados (YoY)":
        uploaded_files = st.sidebar.file_uploader(
            "Selecione os 2 arquivos (Anos Diferentes):", 
            accept_multiple_files=True, 
            type=['csv', 'xlsx']
        )
    else:
        # Modo Arquivo Único: desativamos o multiple_files para evitar confusão
        uploaded_file = st.sidebar.file_uploader(
            "Selecione o arquivo único:", 
            accept_multiple_files=False, 
            type=['csv', 'xlsx']
        )
        uploaded_files = [uploaded_file] if uploaded_file else []

    return uploaded_files, modo_envio

def render_advanced_filters(df_raw, dimensoes_validas, ano_at, ano_ant):
    st.sidebar.markdown("---")
    
    if 'Mes' in df_raw.columns:
        meses_lista = sorted(df_raw['Mes'].unique())
        
        mes_max_data = df_raw[df_raw['Ano'] == ano_at]['Mes'].max()
        
        meses_completos = [m for m in meses_lista if m < mes_max_data]
        
        if not meses_completos:
            meses_completos = meses_lista
        
    else:
        st.sidebar.error("❌ Coluna 'Mes' não encontrada.")
        meses_lista = []
        meses_completos = []
    
    meses_br = {1:'Jan', 2:'Fev', 3:'Mar', 4:'Abr', 5:'Mai', 6:'Jun',
                7:'Jul', 8:'Ago', 9:'Set', 10:'Out', 11:'Nov', 12:'Dez'}
    
    # # 1. Filtro de Meses
    # meses_lista = sorted(df_raw['Mes'].unique())
    # meses_br = {1:'Jan', 2:'Fev', 3:'Mar', 4:'Abr', 5:'Mai', 6:'Jun',
    #             7:'Jul', 8:'Ago', 9:'Set', 10:'Out', 11:'Nov', 12:'Dez'}
    
    selecao_meses = st.sidebar.multiselect(
        "2. Período (Meses):", 
        options=meses_lista, 
        default=meses_completos,
        format_func=lambda x: meses_br.get(x, x),
        key="ms_meses",
        on_change=reset_navigation
    )

    # 2. Dimensões para a IA
    # opcoes_hierarquia = ['Desc_Conta', 'P_L', 'VP', 'Localidade', 'Centro_Custo', 'Desc_Material']
    opcoes_hierarquia = dimensoes_validas
    dimensoes_ia = st.sidebar.multiselect(
        "3. Colunas a serem analisadas:",
        options=dimensoes_validas,
        default=dimensoes_validas,
        format_func=lambda x: LABELS_MAP.get(x, x),
        key="ms_dimensoes",
        on_change=reset_navigation
    )

    # 3. Foco da Análise
    foco_resultado = st.sidebar.radio(
        "4. Foco da Análise:",
        ["Apenas Savings (Eficiência)", "Apenas Desvios (Gastos)", "Análise 360° (Ambos)"],
        key="radio_foco_ia",
        on_change=reset_navigation
    )

    filtros_selecionados = {}
    
    if dimensoes_ia:
        st.sidebar.markdown("---")
        st.sidebar.subheader("Filtrar resultados:")
        
        for dim in dimensoes_ia:
            # 1. Base filtrada apenas pelos meses (ponto de partida)
            df_temp = df_raw[df_raw['Mes'].isin(selecao_meses)] if selecao_meses else df_raw.copy()
            
            # 2. Aplica as seleções das OUTRAS dimensões para o filtro "conversar"
            for outra_dim in dimensoes_ia:
                if outra_dim != dim:
                    selecionados_na_outra = st.session_state.get(f"dyn_filter_{outra_dim}", [])
                    if selecionados_na_outra:
                        # Filtramos o df_temp convertendo a coluna para string para evitar erros
                        df_temp = df_temp[df_temp[outra_dim].astype(str).isin(selecionados_na_outra)]
            
            # 3. Extração de opções com blindagem contra tipos mistos (TypeError)
            # Convertemos para string antes do unique() e sorted()
            
            # raw_unique = df_temp[dim].dropna().unique().tolist()
            raw_unique = df_temp[dim].unique()
            
            label_amigavel = LABELS_MAP.get(dim, dim)
            opcoes_disponiveis = sorted([str(x) for x in raw_unique])
            
            # 4. Mantemos o que já estava selecionado no estado para não sumir da lista
            
            opcoes_disponiveis = sorted([
                str(x) if pd.notna(x) and str(x).lower() != 'nan' else "Não Especificado" 
                for x in raw_unique
            ])
            
            # opcoes_disponiveis = sorted(df_temp[dim].astype(str).unique().tolist())
            
            # 3. Gestão de estado (seu código original)
            # selecionados_atuais = [str(x) for x in st.session_state.get(f"dyn_filter_{dim}", [])]
            
            estado_atual = st.session_state.get(f"dyn_filter_{dim}", [])
            if not isinstance(estado_atual, list):
                estado_atual = []
            
            selecionados_atuais = [str(x) for x in estado_atual]
            opcoes_finais = sorted(list(set(opcoes_disponiveis) | set(selecionados_atuais)))

            # 5. Renderização do Multiselect (Barra de busca nativa)
            escolha = st.sidebar.multiselect(
                f"Filtrar {label_amigavel}:",
                options=opcoes_finais,
                key=f"dyn_filter_{dim}",
                help=f"Selecione os filtros para especificar os resultados.",
                on_change=reset_navigation
            )
            filtros_selecionados[dim] = escolha

    st.sidebar.markdown("---")

    return selecao_meses, dimensoes_ia, foco_resultado, filtros_selecionados