import streamlit as st
import pandas as pd
from logic import reset_navigation
from utils import LABELS_MAP
 
def render_initial_sidebar():
    """
    Renderiza os controlos básicos na barra lateral antes do processamento.
    Configura o modo de comparação e o carregamento de ficheiros.
    """
    st.sidebar.title("Configurações")
    
    modo_planilha = st.sidebar.radio(
        "Selecione o formato da base:",
        ["Planilha do SAP (Transacional)", "Planilha com todas as contas"],
        help="Altera o motor de cálculo para ler arquivos de projeção (PXXF/AOP)."
    )
    st.session_state.modo_planilha = modo_planilha
    
    st.sidebar.divider()
    
    st.sidebar.title("Seleção de conteúdos")
    
    if modo_planilha == "Planilha com todas as contas":
        modo_envio = "Arquivo Único (Biênio/Histórico)"
        st.sidebar.info("📌 Modo de arquivo único ativado por padrão para o Planejamento.")
    else:
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
    
    # Resgata o modo selecionado na tela anterior
    modo_planilha = st.session_state.get('modo_planilha', 'Planilha do SAP')
    
    # --- 1. TRATAMENTO: Ocultar Material no modo Planejamento ---
    if modo_planilha == "Planilha com todas as contas":
        dimensoes_validas = [d for d in dimensoes_validas if d != 'Desc_Material']
    
    # --- 2. TRATAMENTO: Ocultar Filtro de Mês e Erro no modo Planejamento ---
    if modo_planilha == "Planilha com todas as contas":
        selecao_meses = [] # Ignora filtros de meses sem quebrar a tela
    else:
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
        
        selecao_meses = st.sidebar.multiselect(
            "2. Período (Meses):", 
            options=meses_lista, 
            default=meses_completos,
            format_func=lambda x: meses_br.get(x, x),
            key="ms_meses",
            # on_change=reset_navigation
        )

    # 2. Dimensões para a IA
    opcoes_hierarquia = dimensoes_validas
    dimensoes_ia = st.sidebar.multiselect(
        "3. Colunas a serem analisadas:",
        options=dimensoes_validas,
        default=dimensoes_validas,
        format_func=lambda x: LABELS_MAP.get(x, x),
        key="ms_dimensoes",
        # on_change=reset_navigation
    )

    # 3. Foco da Análise
    foco_resultado = st.sidebar.radio(
        "4. Foco da Análise:",
        ["Apenas Savings (Eficiência)", "Apenas Desvios (Gastos)", "Análise 360° (Ambos)"],
        key="radio_foco_ia",
        # on_change=reset_navigation
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
            valores_brutos = df_temp[dim].unique().tolist()
            
            label_amigavel = LABELS_MAP.get(dim, dim)
            # opcoes_disponiveis = sorted(df_temp[dim].astype(str).unique().tolist())
            opcoes_disponiveis = sorted([
                str(x) if pd.notna(x) and str(x).lower() != 'nan' else "Não Especificado" 
                for x in valores_brutos
            ])
            
            # 4. Mantemos o que já estava selecionado no estado para não sumir da lista
            # selecionados_atuais = [str(x) for x in st.session_state.get(f"dyn_filter_{dim}", [])]
            # opcoes_finais = sorted(list(set(opcoes_disponiveis) | set(selecionados_atuais)))
            
            opcoes_disponiveis = sorted(df_temp[dim].astype(str).unique().tolist())
            
            # 3. Gestão de estado (seu código original)
            selecionados_atuais = [str(x) for x in st.session_state.get(f"dyn_filter_{dim}", [])]
            opcoes_finais = sorted(list(set(opcoes_disponiveis) | set(selecionados_atuais)))

            # 5. Renderização do Multiselect (Barra de busca nativa)
            escolha = st.sidebar.multiselect(
                f"Filtrar {label_amigavel}:",
                options=opcoes_finais,
                key=f"dyn_filter_{dim}",
                help=f"Selecione os filtros para especificar os resultados.",
                # on_change=reset_navigation
            )
            filtros_selecionados[dim] = escolha

    st.sidebar.markdown("---")

    st.sidebar.markdown("---")

    # BOTÃO PARA GERAR/ATUALIZAR O RELATÓRIO
    if st.sidebar.button("🚀 Gerar / Atualizar Relatório", type="primary", use_container_width=True):
        st.session_state.relatorio_liberado = True
        # Tira uma "foto" dos filtros no exato momento do clique
        st.session_state.filtros_snapshot = {
            'selecao_meses': selecao_meses,
            'dimensoes_ia': dimensoes_ia,
            'foco_resultado': foco_resultado,
            'filtros_selecionados': filtros_selecionados
        }
        reset_navigation() # Reseta a tela (drill-down) só ao gerar um novo relatório

    # Se o relatório já foi gerado antes, retorna a "foto" salva (ignorando o que está sendo mexido ao vivo na sidebar)
    if st.session_state.get('relatorio_liberado', False) and 'filtros_snapshot' in st.session_state:
        snap = st.session_state.filtros_snapshot
        return snap['selecao_meses'], snap['dimensoes_ia'], snap['foco_resultado'], snap['filtros_selecionados']
    
    # Se o usuário acabou de subir o arquivo e ainda não clicou no botão:
    return "AGUARDANDO", [], None, {}