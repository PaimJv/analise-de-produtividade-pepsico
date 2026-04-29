from utils import LABELS_MAP
import streamlit as st
import planejamento_logic
from logic import init_state, load_and_process_base, voltar_nivel, apply_color_logic, get_highlights_summary
from sidebar import render_initial_sidebar, render_advanced_filters
from components import render_dynamic_table
import sys
import gc
import pandas as pd
from PIL import Image
import os

# --- 0. COMPATIBILIDADE EXECUTÁVEL ---
if getattr(sys, 'frozen', False):
    bundle_dir = sys._MEIPASS
    sys.path.append(bundle_dir)
    
# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Análise de produtividade PepsiCo",
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
st.title("Análise de produtividade YoY")
st.caption("Observação e destaque de oportunidades de redução de custo na PepsiCo.")

# 🚀 ESPAÇO RESERVADO NO TOPO PARA O BOTÃO DE DOWNLOAD
container_botao_download = st.empty()
st.markdown("---")

uploaded_files, modo_selecionado = render_initial_sidebar()


# Regra de Validação Dinâmica
pode_processar = False
if modo_selecionado == "Arquivos Separados (YoY)" and len(uploaded_files) >= 2:
    pode_processar = True
elif modo_selecionado == "Arquivo Único (Biênio/Histórico)" and len(uploaded_files) == 1:
    pode_processar = True

# Lógica de Hash e Reset (Mantenha o que já temos, mas use pode_processar)
if pode_processar:
    current_files_hash = str([f.name for f in uploaded_files]) + modo_selecionado
    
    if current_files_hash != st.session_state.last_files_hash:
        st.session_state.df_raw = None
        st.session_state.last_files_hash = current_files_hash
        st.session_state.drill_path = []

    # --- 4. PROCESSAMENTO OTIMIZADO ---
    if st.session_state.df_raw is None:
        # 🚀 O ESTADO DE CARREGAMENTO MANUAL (ATIVA A ANIMAÇÃO)
        loading_placeholder = st.empty()
        loading_placeholder.info("⏳ **Processando e otimizando base de dados...** (O navegador pode parecer congelado por alguns segundos, por favor aguarde!)")
        
        import time
        time.sleep(0.3) # O FÔLEGO: Dá tempo ao navegador para desenhar a mensagem acima
        
        modo_planilha = st.session_state.get('modo_planilha', 'Planilha do SAP')
        
        # BIFURCAÇÃO DA LEITURA DE DADOS
        if modo_planilha == "Planilha com todas as contas":
            # ROTA 1: Novo motor de planejamento
            res = planejamento_logic.process_all_accounts_format(uploaded_files)
            if isinstance(res, pd.DataFrame):
                # No novo modo, as dimensões padrão incluem o 'Pacote'
                dims_desejadas = ['Desc_Conta', 'P_L', 'VP', 'Localidade', 'Centro_Custo', 'Desc_Material', 'Pacote']
                dims_validas = ['Desc_Conta', 'P_L', 'VP', 'Localidade', 'Centro_Custo', 'Desc_Material', 'Pacote']
                at, ant, aviso = 2026, 2025, None # Fake values para não quebrar a UI
        else:
            # ROTA 2: Motor original do SAP
            res, at, ant, aviso = load_and_process_base(uploaded_files)
            if isinstance(res, pd.DataFrame):
                from logic import obter_dimensoes_validas
                dims_validas = obter_dimensoes_validas(res, at, ant)

        # SALVAMENTO NA SESSÃO (Igual para ambos)
        if isinstance(res, pd.DataFrame):
            st.session_state.df_raw = res
            st.session_state.ano_at = at
            st.session_state.ano_ant = ant
            st.session_state.dims_com_paridade = dims_validas
            st.session_state.aviso_incompleto = aviso
            gc.collect()
        else:
            loading_placeholder.empty()
            st.error(f"Erro no processamento: {res}")
            st.stop()
            
        # 🚀 FINALIZOU O PROCESSAMENTO: Limpa a mensagem da tela
        loading_placeholder.empty()
    
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

    # --- 🛑 TRAVA DO BOTÃO (AGUARDANDO GERAÇÃO) ---
    if selecao_meses == "AGUARDANDO":
        st.info("Ajuste os parâmetros na barra lateral, clique em **🚀 Gerar / Atualizar Relatório** para iniciar a análise e aguarde.")
        st.stop() # Interrompe a execução da tela principal aqui até o botão ser clicado

    # --- 6. LÓGICA DE FILTRAGEM ---
    df_filtrado = df_raw # 🚀 REMOVIDO O .copy()
    meses_filtro = selecao_meses
    
    # Só aplica o filtro de meses se a coluna existir (Modo SAP)
    if 'Mes' in df_filtrado.columns:
        meses_filtro = selecao_meses if selecao_meses else sorted(df_filtrado['Mes'].unique())
        df_filtrado = df_filtrado[df_filtrado['Mes'].isin(meses_filtro)]
    
    if filtros_dinamicos:
        for col, valores in filtros_dinamicos.items():
            if valores:
                df_filtrado = df_filtrado[df_filtrado[col].astype(str).isin(valores)]
    
    # --- 7. DRILL-DOWN ---
    df_active = df_filtrado # 🚀 REMOVIDO O .copy()
    for col, val in st.session_state.drill_path:
        if col in df_active.columns:
            df_active = df_active[df_active[col].astype(str) == str(val)]

    # ==========================================================
    # BIFURCAÇÃO MESTRE DAS TELAS (SAP vs PLANEJAMENTO)
    # ==========================================================
    modo_planilha = st.session_state.get('modo_planilha', 'Planilha do SAP')

    if modo_planilha == "Planilha com todas as contas":
        
        # ------------------------------------------------------
        # TELA 1: MODO PLANEJAMENTO (NOVO)
        # ------------------------------------------------------
        st.markdown("---")
        st.subheader("Resultados encontrados (Planejamento)")
        
        if not dimensoes_ia:
            st.warning("Selecione as dimensões na barra lateral para o relatório detalhado.")
        else:
            # 🚀 CARREGAMENTO MANUAL DE TELA
            status_plan = st.empty()
            status_plan.info("📊 Gerando visão estruturada em painéis... Por favor, aguarde.")
            
            import time
            time.sleep(0.3) # O FÔLEGO
            
            planejamento_logic.render_planejamento_ui(df_filtrado, dimensoes_ia)
            
            status_plan.empty() # Limpa após carregar

    else:
        
        # ------------------------------------------------------
        # TELA 2: MODO SAP ORIGINAL (INTOCADO)
        # ------------------------------------------------------
        # 🚀 Zera os blocos secundários (caso não existam, o download ignora)
        st.session_state.html_destaques = ""
        st.session_state.html_resumo = ""
        
        if st.session_state.aviso_incompleto:
            a = st.session_state.aviso_incompleto
            st.warning(f"⚠️ **Atenção:** O mês de **{a['mes_nome']}** está incompleto no relatório (registros apenas até o dia **{a['dia']}**).")
                
        # --- 6.1 RESUMO DE DESTAQUES (OPORTUNIDADES) ---
        resumo_opps = get_highlights_summary(df_filtrado, ano_at, ano_ant)
        
        if resumo_opps:
            with st.expander("💡 **Destaques de Produtividade YoY**", expanded=True):
                st.markdown("Principais oportunidades de redução:")
                lista_html_destaques = ""
                
                import re # Garantindo a biblioteca de texto
                
                for item in resumo_opps:
                    st.write(item) # Mantém original na tela do Streamlit
                    
                    # 🚀 TRADUTOR MARKDOWN -> HTML
                    item_html = re.sub(r'\*\*(.*?)\*\*', r'<strong style="color: #60a5fa;">\1</strong>', item)
                    item_html = item_html.replace(r"R\$", "R$")
                    
                    lista_html_destaques += f"<li style='margin-bottom: 8px;'>{item_html}</li>"
                
                # 🚀 CAPTURA PARA DOWNLOAD
                st.session_state.html_destaques = f"""
                <details style='margin-bottom: 15px; border: 1px solid #333; border-radius: 8px; background-color: #1e1e1e;'>
                    <summary style='padding: 16px; font-weight: bold; cursor: pointer; background-color: #252525; border-bottom: 1px solid #333; color: #fff;'>💡 Destaques de Produtividade YoY</summary>
                    <div style='padding: 20px; font-family: sans-serif;'>
                        <p style='color: #aaa; margin-top: 0;'>Principais oportunidades de redução:</p>
                        <ul style='color: #ddd; font-size: 14px;'>{lista_html_destaques}</ul>
                    </div>
                </details>
                """
        else:
            st.info("Nenhuma oportunidade de produtividade acima de R$ 1.000,00 identificada no período selecionado.")

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
            label_atual = LABELS_MAP.get(atual_col, atual_col)

            # Matriz de Variação (Processamento Matemático)
            st.markdown("---")
            st.subheader(f"Resumo Mensal: {label_atual}")
            
            df_pivot = render_dynamic_table(df_active, atual_col, ano_at, ano_ant)
            cols_meses = [c for c in df_pivot.columns if c != 'Total Geral']
            cols_para_estilizar = cols_meses + ['Total Geral']

            # Aplicação das Cores via Pandas Styler
            styler_colorido = df_pivot.style.format(precision=2, decimal=',', thousands='.').map(apply_color_logic, subset=cols_para_estilizar)

            # Exibição na Tela
            st.dataframe(styler_colorido, use_container_width=True)
            
            # 🚀 CAPTURA PARA DOWNLOAD (Gera o código HTML da Tabela com Cores)
            tabela_html_crua = styler_colorido.to_html()
            st.session_state.html_resumo = f"""
            <details style='margin-bottom: 15px; border: 1px solid #333; border-radius: 8px; background-color: #1e1e1e;'>
                <summary style='padding: 16px; font-weight: bold; cursor: pointer; background-color: #252525; border-bottom: 1px solid #333; color: #fff;'>📊 Resumo Mensal: {label_atual}</summary>
                <div style='padding: 15px; overflow-x: auto;'>
                    {tabela_html_crua}
                </div>
            </details>
            """

            st.markdown("---")
            st.subheader("Resultados encontrados")

            if not dimensoes_ia:
                st.warning("Selecione as dimensões na barra lateral para o relatório detalhado.")
            else:
                filtro_id = "-".join(map(str, sorted(meses_filtro)))
                
                # 🚀 CARREGAMENTO MANUAL DE TELA
                status_relatorio = st.empty()
                status_relatorio.info("📊 Montando auditoria detalhada e calculando variações YoY... Aguarde.")
                
                import time
                time.sleep(0.3) # O FÔLEGO
                
                placeholder = st.empty()
                with placeholder.container(): 
                    from logic import render_report_ui, prepare_report_data            
                    df_master, dims_analise = prepare_report_data(df_filtrado, dimensoes_ia, ano_at, ano_ant)
                    render_report_ui(df_master, dims_analise, ano_at, ano_ant, foco_res, selecao_meses=meses_filtro)
                
                status_relatorio.empty() # Limpa após carregar
        
        else:
            # Nível Final (Material)
            st.success("🎯 Detalhe máximo atingido (Análise por Material).")
            if st.button("⬅️ Voltar ao Início", use_container_width=True):
                st.session_state.drill_path = []
                st.rerun()

else:
    st.info("Para começar, carregue o(s) arquivo(s) com dois anos diferentes na barra lateral e aguarde o carregamento.")
    
# 🚀 PREENCHE A CAIXA VAZIA NO TOPO COM O BOTÃO DE DOWNLOAD
if 'ultimo_html_gerado' in st.session_state and st.session_state.ultimo_html_gerado:
    try:
        from logic import compilar_html_para_download
        
        # 1. Lista as colunas que queremos mostrar (excluíndo materiais propositalmente)
        colunas_metadados = ['Desc_Conta', 'P_L', 'VP', 'Localidade', 'Centro_Custo', 'Pacote']
        
        # 2. Faz um raio-X no df_filtrado para descobrir exatamente o que está no relatório
        itens_disponiveis = {}
        for col in colunas_metadados:
            if col in df_filtrado.columns:
                valores = sorted([str(x) for x in df_filtrado[col].dropna().unique() if str(x).strip() != ""])
                if valores:
                    itens_disponiveis[col] = valores
        
        # 3. Empacota tudo (Buscando também os Destaques e a Tabela Resumo)
        html_dest = st.session_state.get('html_destaques', '')
        html_resu = st.session_state.get('html_resumo', '')
        
        html_para_baixar = compilar_html_para_download(
            st.session_state.ultimo_html_gerado,
            titulo=f"Produtividade YoY - {modo_selecionado}",
            foco=foco_res,
            itens_disponiveis=itens_disponiveis,
            meses=selecao_meses,
            html_destaques=html_dest,
            html_resumo=html_resu
        )
        
        container_botao_download.download_button(
            label="📥 Baixar Relatório Atual (HTML Offline)",
            data=html_para_baixar,
            file_name=f"pepsico_produtividade_yoy.html",
            mime="text/html",
            use_container_width=True
        )
    except Exception as e:
        pass # Segurança caso haja erro na compilação

import gc
gc.collect()