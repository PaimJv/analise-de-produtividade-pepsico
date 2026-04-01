import streamlit as st
from logic import reset_navigation

def render_initial_sidebar():
    """
    Renderiza os controlos básicos na barra lateral antes do processamento.
    Configura o modo de comparação e o carregamento de ficheiros.
    """
    st.sidebar.title("🔍 Parâmetros da Auditoria")
    st.sidebar.markdown("---")
    
    uploaded_files = st.sidebar.file_uploader(
        "Carregue os arquivos (CSV ou Excel)", 
        type=['csv', 'xlsx', 'xls'], 
        accept_multiple_files=True
    )
    
    return uploaded_files

def render_advanced_filters(df_raw, dimensoes_validas, ano_at, ano_ant):
    st.sidebar.markdown("---")
    
    # 1. Filtro de Meses
    meses_lista = sorted(df_raw['Mes'].unique())
    meses_br = {1:'Jan', 2:'Fev', 3:'Mar', 4:'Abr', 5:'Mai', 6:'Jun',
                7:'Jul', 8:'Ago', 9:'Set', 10:'Out', 11:'Nov', 12:'Dez'}
    
    selecao_meses = st.sidebar.multiselect(
        "2. Período (Meses):", 
        options=meses_lista, 
        default=meses_lista,
        format_func=lambda x: meses_br.get(x, x),
        key="ms_meses",
        on_change=reset_navigation
    )

    # 2. Dimensões para a IA
    # opcoes_hierarquia = ['Desc_Conta', 'P_L', 'VP', 'Localidade', 'Centro_Custo', 'Desc_Material']
    opcoes_hierarquia = dimensoes_validas
    dimensoes_ia = st.sidebar.multiselect(
        "3. Dimensões para a IA:",
        options=opcoes_hierarquia,
        default=[
            # 'Desc_Conta', 'Localidade'
            ],
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
        st.sidebar.subheader("🎯 Filtros Inteligentes")
        
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
            opcoes_disponiveis = sorted(df_temp[dim].astype(str).unique().tolist())
            
            # 4. Mantemos o que já estava selecionado no estado para não sumir da lista
            selecionados_atuais = [str(x) for x in st.session_state.get(f"dyn_filter_{dim}", [])]
            opcoes_finais = sorted(list(set(opcoes_disponiveis) | set(selecionados_atuais)))

            # 5. Renderização do Multiselect (Barra de busca nativa)
            escolha = st.sidebar.multiselect(
                f"Filtrar {dim}:",
                options=opcoes_finais,
                key=f"dyn_filter_{dim}",
                help=f"Lista em ordem alfabética. Opções limitadas pelas outras seleções.",
                on_change=reset_navigation
            )
            filtros_selecionados[dim] = escolha

    st.sidebar.markdown("---")

    return selecao_meses, dimensoes_ia, foco_resultado, filtros_selecionados