import sys
import streamlit as st
import pandas as pd
import gc
import calendar
import json, os
import io
from utils import mapeamento, get_yoy_data

def get_base_path():
    """Retorna o caminho absoluto da pasta onde o programa (ou .exe) está fisicamente localizado."""
    if getattr(sys, 'frozen', False):
        # Se estiver rodando como .exe compilado
        return os.path.dirname(sys.executable)
    else:
        # Se estiver rodando como script normal no VS Code
        return os.path.dirname(os.path.abspath(__file__))

def to_excel(df):
    """Converte um DataFrame para o formato binário do Excel (XLSX)."""
    output = io.BytesIO()
    # Usamos o mecanismo xlsxwriter para criar o arquivo na memória
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=True, sheet_name='Produtividade_YoY')
        # Aqui você poderia até adicionar formatação específica nas células do Excel se quisesse
        
    return output.getvalue()

def encontrar_arquivo_local(nome_arquivo):
    """Radar: Busca o arquivo na pasta do .exe, no VS Code ou na pasta atual."""
    caminhos_possiveis = [
        os.getcwd(), # 1ª Tentativa: A pasta onde o usuário clicou no .exe
    ]
    if getattr(sys, 'frozen', False):
        caminhos_possiveis.append(os.path.dirname(sys.executable)) # 2ª Tentativa: Diretório real do .exe
    else:
        caminhos_possiveis.append(os.path.dirname(os.path.abspath(__file__))) # 3ª Tentativa: VS Code

    for pasta in caminhos_possiveis:
        caminho_completo = os.path.join(pasta, nome_arquivo)
        if os.path.exists(caminho_completo):
            return caminho_completo
            
    return None # Não achou em lugar nenhum

def carregar_referencia():
    """Carrega o JSON usando o radar."""
    caminho_json = encontrar_arquivo_local('referencia_colunas.json')
    if caminho_json:
        try:
            with open(caminho_json, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Erro ao ler JSON: {e}")
    return {}

# Agora o conteúdo já fica salvo na memória para o aplicativo inteiro usar
REFERENCIA_CONTEUDO = carregar_referencia()

def init_state():
    """Inicializa as variáveis de estado da sessão de forma única."""
    if 'drill_path' not in st.session_state:
        st.session_state.drill_path = []
    if 'aviso_incompleto' not in st.session_state:
        st.session_state.aviso_incompleto = None

def obter_dimensoes_validas(df, ano_at, ano_ant):
    """Retorna apenas as colunas que possuem dados em ambos os anos."""
    possiveis = ['Desc_Conta', 'P_L', 'VP', 'Localidade', 'Centro_Custo', 'Desc_Material']
    validas = []
    
    for col in possiveis:
        if col in df.columns:
            # Teste de existência em ambos os anos
            tem_no_at = df[df['Ano'] == ano_at][col].notna().any()
            tem_no_ant = df[df['Ano'] == ano_ant][col].notna().any()
            
            if tem_no_at and tem_no_ant:
                validas.append(col)
    return validas

def get_highlights_summary(df, ano_at, ano_ant):
    """
    Identifica as top 10 oportunidades de produtividade (economias >= 1000).
    """
    if df.empty:
        return []

    # 1. Agrupamos por Conta e Centro de Custo para calcular o Delta total no período
    grouped = df.groupby(['Desc_Conta', 'Centro_Custo', 'Ano'], observed=True)['Valor'].sum().unstack('Ano').fillna(0)
    
    # Garantia de paridade de colunas
    for a in [ano_at, ano_ant]:
        if a not in grouped.columns:
            grouped[a] = 0
            
    grouped['Delta'] = grouped[ano_at] - grouped[ano_ant]
    
    # 2. Filtramos apenas produtividade real (Redução de custo <= -1000)
    opps = grouped[grouped['Delta'] <= -1000].copy()
    
    if opps.empty:
        return []

    # 3. Ranking das Top 10 Contas com maior economia acumulada
    contas_ranking = opps.groupby('Desc_Conta', observed=True)['Delta'].sum().sort_values()
    top_contas = contas_ranking.head(5)
    
    summary = []
    for conta in top_contas.index:
        # Buscamos os Centros de Custo que mais contribuíram para essa conta específica
        ccs_da_conta = opps.loc[conta].sort_values('Delta').head(3) # Limitamos a 3 para manter o texto limpo
        
        cc_items = []
        for cc, row in ccs_da_conta.iterrows():
            valor_formatado = format_brl(row['Delta']).replace("$", r"\$")
            cc_items.append(f"{cc} ({valor_formatado})")
        
        if not cc_items: continue
            
        # Formatação gramatical (vírgula e "e")
        if len(cc_items) > 1:
            texto_ccs = ", ".join(cc_items[:-1]) + " e " + cc_items[-1]
        else:
            texto_ccs = cc_items[0]
            
        summary.append(f"- A conta **{conta}** com os centros de custo {texto_ccs}")
        
    return summary

# @st.cache_data(show_spinner=False)
def carregar_bases_apoio():
    """Carrega os arquivos Parquet garantindo que o .exe não se perca."""
    caminho_contas = encontrar_arquivo_local("dim_contas.parquet")
    caminho_cc = encontrar_arquivo_local("dim_centros_custo.parquet")
    
    try:
        df_contas = pd.read_parquet(caminho_contas) if caminho_contas else None
        df_cc = pd.read_parquet(caminho_cc) if caminho_cc else None
        return df_contas, df_cc
    except Exception as e:
        st.warning(f"⚠️ Erro ao carregar Parquets. Verifique os arquivos: {e}")
        return None, None

@st.cache_data(show_spinner="Otimizando base de dados...")
def load_and_process_base(files):
    dfs = []
    from utils import mapeamento
    import csv
    
    for f in files:
        try: # --- INÍCIO DO TRY POR ARQUIVO ---
            # 1. LEITURA DE AMOSTRA (100 linhas para o "detetive" ter pistas)
            if f.name.endswith('.csv'):
                # 1.1 DETECÇÃO DE ENCODING
                sample_bytes = f.read(10000)
                f.seek(0)
                
                try:
                    sample_bytes.decode('utf-8-sig')
                    encoding_tentativa = 'utf-8-sig'
                except UnicodeDecodeError:
                    encoding_tentativa = 'cp1252'
                
                # 1.2 DETECÇÃO DE SEPARADOR (O que estava faltando antes)
                try:
                    sample_text = sample_bytes.decode(encoding_tentativa, errors='ignore')
                    dialect = csv.Sniffer().sniff(sample_text, delimiters=',;\t|')
                    sep_detectado = dialect.delimiter
                except:
                    sep_detectado = ';' # Fallback padrão SAP

                # 1.3 LEITURA DO CABEÇALHO (Agora com sep e encoding definidos)
                f.seek(0)
                df_header = pd.read_csv(
                    f, 
                    sep=sep_detectado, 
                    engine='python', 
                    encoding=encoding_tentativa, 
                    nrows=100
                )
                f.seek(0)
                
            else:
                # Tratamento para Excel (xlsx, xls)
                df_header = pd.read_excel(f, engine='calamine', nrows=100)
                sep_detectado = None
                encoding_tentativa = None

            # 2. MAPEAMENTO INTELIGENTE (NOME + CONTEÚDO/SINÔNIMOS)
            colunas_reais = df_header.columns.tolist()
            col_map_arquivo = {str(c).strip().lower(): c for c in colunas_reais}
            map_limpo = {str(k).strip().lower(): v for k, v in mapeamento.items()}
            
            # 🚀 VACINA DE SEGURANÇA (Hardcoded)
            map_limpo['data de lançamento'] = 'Data_Lancamento'
            map_limpo['dt.lçto'] = 'Data_Lancamento'
            map_limpo['data de lancamento'] = 'Data_Lancamento'
            
            tradução_final = {}
            colunas_sistema_obrigatorias = ['Classe_Custo', 'Centro_Custo', 'Valor', 'Data_Lancamento']
            
            # A) BUSCA POR NOME
            for k_limpo, v_sistema in map_limpo.items():
                if k_limpo in col_map_arquivo:
                    nome_original = col_map_arquivo[k_limpo]
                    tradução_final[nome_original] = v_sistema
            
            # 🚀 B) O "TESTE DE DNA" COM OS PARQUETS (A SUA IDEIA!)
            faltantes = [c for c in colunas_sistema_obrigatorias if c not in tradução_final.values()]
            colunas_ignotas = [c for c in colunas_reais if c not in tradução_final.keys()]
            
            # Carregamos os Parquets rapidamente para usar como lista oficial
            df_contas_ref, df_cc_ref = carregar_bases_apoio()
            set_contas = set(df_contas_ref['Conta'].dropna().astype(str).str.replace(r'\.0$', '', regex=True).str.strip()) if df_contas_ref is not None else set()
            set_cc = set(df_cc_ref['CC'].dropna().astype(str).str.replace(r'\.0$', '', regex=True).str.strip()) if df_cc_ref is not None else set()
            
            for col_arq in colunas_ignotas[:]:
                if not faltantes: break
                
                # Extrai 100 valores da coluna misteriosa do arquivo
                amostra = set(df_header[col_arq].dropna().astype(str).str.replace(r'\.0$', '', regex=True).str.strip().tolist())
                
                # Bateu com a base de Contas?
                if 'Classe_Custo' in faltantes and amostra.intersection(set_contas):
                    tradução_final[col_arq] = 'Classe_Custo'
                    faltantes.remove('Classe_Custo')
                    colunas_ignotas.remove(col_arq)
                    continue
                    
                # Bateu com a base de CC?
                if 'Centro_Custo' in faltantes and amostra.intersection(set_cc):
                    tradução_final[col_arq] = 'Centro_Custo'
                    faltantes.remove('Centro_Custo')
                    colunas_ignotas.remove(col_arq)
                    continue

            # C) FALLBACK PARA O JSON (Apenas para achar o Valor e a Data)
            if faltantes and REFERENCIA_CONTEUDO:
                ref_data = REFERENCIA_CONTEUDO
                for col_arq in colunas_ignotas[:]: 
                    nome_col_arq_limpo = str(col_arq).strip().lower()
                    for nome_sistema_ref, exemplos_ref in ref_data.items():
                        if nome_sistema_ref in faltantes:
                            sinonimos = [str(e).strip().lower() for e in exemplos_ref]
                            if nome_col_arq_limpo in sinonimos:
                                tradução_final[col_arq] = nome_sistema_ref
                                faltantes.remove(nome_sistema_ref)
                                colunas_ignotas.remove(col_arq)
                                break
                                
            # 3. TRAVA DE SEGURANÇA COM ERRO "RAIO-X"
            if 'Data_Lancamento' not in tradução_final.values():
                caminho_usado = encontrar_arquivo_local('referencia_colunas.json')
                cols_lidas = [str(c) for c in colunas_reais[:15]] # Pega as 15 primeiras colunas para diagnóstico
                
                msg_erro = (
                    f"❌ **A coluna de DATA não foi encontrada no arquivo:** `{f.name}`.\n\n"
                    f"🔍 **Raio-X do que o .exe enxergou na sua planilha:**\n"
                    f"`{cols_lidas}`\n\n"
                    f"📂 **JSON procurado em:** `{caminho_usado}`"
                )
                return msg_erro, None, None, None

            # 4. LEITURA COMPLETA OTIMIZADA
            f.seek(0)
            colunas_para_ler = list(tradução_final.keys())
            if f.name.endswith('.csv'):
                df_temp = pd.read_csv(f, usecols=colunas_para_ler, sep=sep_detectado, engine='c', encoding=encoding_tentativa, low_memory=False)
            else:
                df_temp = pd.read_excel(f, usecols=colunas_para_ler, engine='calamine')

            df_temp.rename(columns=tradução_final, inplace=True)

            # 5. LIMPEZA INICIAL
            if 'Data_Lancamento' in df_temp.columns:
                df_temp['Data_Lancamento'] = pd.to_datetime(df_temp['Data_Lancamento'], dayfirst=True, errors='coerce')
                df_temp = df_temp.dropna(subset=['Data_Lancamento'])
                df_temp['Ano'] = df_temp['Data_Lancamento'].dt.year.astype(int)
                df_temp['Mes'] = df_temp['Data_Lancamento'].dt.month.astype(int)

            if 'Valor' in df_temp.columns:
                if df_temp['Valor'].dtype == object:
                    df_temp['Valor'] = df_temp['Valor'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df_temp['Valor'] = pd.to_numeric(df_temp['Valor'], errors='coerce').fillna(0).astype('float32')
                
            # Padroniza as chaves para que o "PROCV" encaixe perfeitamente
            if 'Classe_Custo' in df_temp.columns:
                df_temp['Classe_Custo'] = df_temp['Classe_Custo'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            if 'Centro_Custo' in df_temp.columns:
                df_temp['Centro_Custo'] = df_temp['Centro_Custo'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

            dfs.append(df_temp)
            gc.collect()

        except Exception as e: # --- FECHAMENTO DO TRY POR ARQUIVO ---
            return f"Erro no arquivo {f.name}: {str(e)}", None, None, None
    
    if not dfs: return "Nenhum dado processado.", None, None, None
    
    # Junta os arquivos transacionais mensais
    df = pd.concat(dfs, ignore_index=True)
    
    del dfs # 🚀 Esvazia a lista temporária da memória
    gc.collect() # 🚀 Limpa a RAM imediatamente

    # 🚀 PREPARAÇÃO DO ESQUEMA ESTRELA (Isola apenas Fatos e Chaves)
    colunas_fatos = ['Classe_Custo', 'Centro_Custo', 'Desc_Material', 'Data_Lancamento', 'Valor', 'Ano', 'Mes']
    colunas_presentes = [c for c in colunas_fatos if c in df.columns]
    df = df[colunas_presentes]

    # =========================================================
    # 🚀 O PROCV (MERGE) COM O STAR SCHEMA DOS PARQUETS
    # =========================================================
    df_contas, df_cc = carregar_bases_apoio()
    
    if df_contas is not None and df_cc is not None:
        # 1. Limpeza extrema de caracteres invisíveis nas chaves
        df_contas['Conta'] = df_contas['Conta'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        df_cc['CC'] = df_cc['CC'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        
        # 🛡️ PROTEÇÃO CONTRA KEYERROR
        if 'Classe_Custo' in df.columns:
            df['Classe_Custo'] = df['Classe_Custo'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        else:
            df['Classe_Custo'] = "000000"
            
        if 'Centro_Custo' in df.columns:
            df['Centro_Custo'] = df['Centro_Custo'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        else:
            df['Centro_Custo'] = "CC_INDEFINIDO"
        
        # 🛡️ TRAVA ABSOLUTA CONTRA MULTIPLICAÇÃO DE VALORES
        df_contas = df_contas.groupby('Conta', as_index=False).first()
        df_cc = df_cc.groupby('CC', as_index=False).first()
        
        # CRUZAMENTO 1 (CONTAS)
        df = df.merge(df_contas[['Conta', 'Desc Conta', 'Pacote', 'P&L']], 
                      left_on='Classe_Custo', right_on='Conta', how='left', validate='m:1')
        
        del df_contas # 🚀 Destrói a base de apoio de contas após o cruzamento
        gc.collect()  # 🚀 Limpa a RAM
        
        # CRUZAMENTO 2 (CENTROS DE CUSTO)
        df = df.merge(df_cc[['CC', 'Descricao CC', 'VP', 'Diretoria', 'Local', 'Localidade', 'Empresa', 'Responsável']], 
                      left_on='Centro_Custo', right_on='CC', how='left', validate='m:1')
        
        del df_cc # 🚀 Destrói a base de apoio de CC após o cruzamento
        gc.collect() # 🚀 Limpa a RAM
        
        # =========================================================
        # RECONSTRUÇÃO DOS NOMES PARA A INTERFACE UI
        # =========================================================
        df['Desc_Conta'] = df['Desc Conta'].astype(object).fillna("Sem Descrição") + " - " + df['Classe_Custo'].astype(object).fillna("000000")
        df['P_L'] = df['Responsável'].astype(object).fillna("Não Informado") 
        df['VP'] = df['VP'].astype(object).fillna("Não Informado")
        df['Localidade'] = df['Localidade'].astype(object).fillna("Não Informado")
        df['Pacote'] = df['Pacote'].astype(object).fillna("Não Informado")
        df['Diretoria'] = df['Diretoria'].astype(object).fillna("Não Informado")
        
        df['Centro_Custo'] = df['Descricao CC'].astype(object).fillna("Sem Descrição") + " (" + df['Centro_Custo'].astype(object).fillna("000") + ")"
        
        # 🚀 LIXEIRA VIP CONTRA O OUT OF MEMORY (NUVEM):
        # Apaga todas as colunas do Parquet e do SAP que já não são úteis para a interface.
        # Isto liberta centenas de Megabytes de RAM instantaneamente!
        colunas_lixo = ['Classe_Custo', 'Conta', 'Desc Conta', 'CC', 'Descricao CC', 'Empresa', 'Local', 'Responsável']
        col_existentes = [c for c in colunas_lixo if c in df.columns]
        df.drop(columns=col_existentes, inplace=True)
        gc.collect() # Força o servidor a limpar a RAM
        
    else:
        # Fallback
        df['Desc_Conta'] = df.get('Classe_Custo', '0000')
        df['P_L'] = df.get('P_L', "Não Informado")
        df['VP'] = df.get('VP', "Não Informado")
        df['Localidade'] = df.get('Localidade', "Não Informado")

    # Tratamento de segurança para o Material (Caso algum arquivo SAP venha sem ele)
    if 'Desc_Material' not in df.columns:
        df['Desc_Material'] = "Não Informado"
    df['Desc_Material'] = df['Desc_Material'].astype(object).fillna("Não Informado")

    # =========================================================
    # 🚀 COMPRESSÃO FINAL DE MEMÓRIA (Categorias)
    # =========================================================
    # Adicionamos 'Desc_Material' na compressão para economizar RAM
    colunas_texto = ['Desc_Conta', 'P_L', 'VP', 'Localidade', 'Centro_Custo', 'Pacote', 'Diretoria', 'Desc_Material']
    for col in colunas_texto:
        if col in df.columns:
            df[col] = df[col].astype('category')

    return get_yoy_data(df)

# Manter as funções voltar_nivel, apply_color_logic, etc., sem alterações.

def voltar_nivel():
    """
    Remove o último nível da hierarquia de navegação (Breadcrumb).
    """
    if st.session_state.drill_path:
        st.session_state.drill_path.pop()

def apply_color_logic(val):
    """
    Lógica de Estilização Condicional (CSS) para o DataFrame.
    Regra de Facilities/Controladoria:
    - Valor Negativo (< 0): Redução de custo em relação ao ano anterior (Verde/Sucesso).
    - Valor Positivo (> 0): Aumento de custo em relação ao ano anterior (Vermelho/Atenção).
    """
    if isinstance(val, (int, float)):
        if val < 0:
            return 'background-color: #D4EDDA; color: #155724'  # Verde (Success)
        elif val > 0:
            return 'background-color: #F8D7DA; color: #721C24'  # Vermelho (Danger)
    return ''

def reset_navigation():
    """
    Limpa completamente o caminho de navegação, voltando ao topo da hierarquia.
    """
    st.session_state.drill_path = []
    

def format_brl(val):
    """Formata valores para o padrão R$ 1.000,00 e R$ -1.000,00"""
    prefix = "R$ "
    if val < 0:
        val_abs = abs(val)
        return f"{prefix}-{val_abs:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{prefix}{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def get_trend_text(df_item):
    """Analisa a tendência sem asteriscos."""
    mensal = df_item.groupby('Mes')['Valor'].sum().sort_index()
    if len(mensal) < 2:
        return ""
    ultimos = mensal.tail(2).values
    if ultimos[-1] < ultimos[0]:
        reducao_pct = ((ultimos[0] - ultimos[-1]) / ultimos[0]) * 100 if ultimos[0] != 0 else 0
        return f" 📉 Tendência: Redução de {reducao_pct:.1f}% no último mês."
    return " 📈 Tendência: Elevação ou Estabilidade."

def prepare_report_data(df, dims, ano_at, ano_ant):
    """Pre-calcula os dados garantindo que nenhum valor seja descartado (Lossless)."""
    df_clean = df.copy()
    dims_com_paridade = []
    dims_existentes = [d for d in dims if d in df_clean.columns]
    
    for d in dims:
        if d in df_clean.columns:
            # Verifica se o ano ATUAL tem algum dado que não seja nulo para esta coluna
            existe_no_atual = df_clean[df_clean['Ano'] == ano_at][d].notna().any()
            # Verifica se o ano ANTERIOR tem algum dado que não seja nulo para esta coluna
            existe_no_anterior = df_clean[df_clean['Ano'] == ano_ant][d].notna().any()
            
            # A coluna só entra no relatório se "viver" nos dois anos
            if existe_no_atual and existe_no_anterior:
                dims_com_paridade.append(d)
    
    # FORÇAMOS o Mês a ser um inteiro puro para matar a memória do tipo 'category'
    if 'Mes' in df_clean.columns:
        df_clean['Mes'] = df_clean['Mes'].astype(int)
    
    # todas_cols = ['Desc_Conta', 'P_L', 'VP', 'Localidade', 'Centro_Custo', 'Desc_Material']
    
    # AJUSTE AQUI: Convertemos para string ANTES de preencher o vazio
    # for c in todas_cols:
    for c in dims_com_paridade + ['Desc_Material']:
        if c in df_clean.columns:
            # Ao converter para str, os NaNs viram a string 'nan'
            df_clean[c] = df_clean[c].astype(str).replace(['nan', 'None', '<NA>'], "Não Informado")
    
    # for c in dims_existentes + ['Desc_Material']:
    #     if c in df_clean.columns:
    #         df_clean[c] = df_clean[c].astype(str).replace(['nan', 'None', '<NA>'], "Não Informado")
    
    # O restante da função permanece igual
    agrupado = (
        df_clean.groupby(dims_com_paridade + ['Mes', 'Ano'], observed=True)['Valor']
        .sum()
        .unstack(level='Ano')
        .fillna(0)
    )
    
    for a in [ano_at, ano_ant]:
        if a not in agrupado.columns: agrupado[a] = 0
    
    agrupado['Delta'] = agrupado[ano_at] - agrupado[ano_ant]
    return agrupado, dims_com_paridade

def render_report_ui(df_master, dims, ano_at, ano_ant, foco_res, profundidade=0, filtro_contexto=None, selecao_meses=None):
    """Relatório ultrarrápido em HTML puro com animação de carregamento (Modo SAP)."""
    if not dims:
        st.warning("Nenhuma dimensão de análise (P&L, VP, etc.) foi encontrada nos arquivos.")
        return

    # 1. Cria os espaços reservados para a Animação na tela
    aviso_texto = st.empty()
    barra_progresso = st.progress(0)

    with st.spinner("Construindo painéis gerenciais na memória do navegador..."):
        # 2. Chama o motor recursivo blindado em HTML
        html_final = _gerar_html_sap_recursivo(
            df_master, dims, ano_at, ano_ant, foco_res, 0, {}, selecao_meses, aviso_texto, barra_progresso
        )

    # 3. Limpa a barra de progresso da tela quando o trabalho terminar
    aviso_texto.empty()
    barra_progresso.empty()

    if html_final.strip() == "":
        st.info("Nenhum registro atende aos critérios de foco selecionados.")
    else:
        st.success("✅ Relatório detalhado renderizado com sucesso!")
        st.markdown(f"<div style='padding-bottom: 50px;'>{html_final}</div>", unsafe_allow_html=True)


def _gerar_html_sap_recursivo(df_nivel, dims, ano_at, ano_ant, foco_res, profundidade, filtro_contexto, selecao_meses, text_ui, progress_ui):
    """Motor de geração de HTML puro para o SAP, evitando gargalos do Streamlit Markdown."""
    if profundidade >= len(dims):
        return ""

    meses_nomes = {1:'Jan', 2:'Fev', 3:'Mar', 4:'Abr', 5:'Mai', 6:'Jun',
                   7:'Jul', 8:'Ago', 9:'Set', 10:'Out', 11:'Nov', 12:'Dez'}

    col = dims[profundidade]
    html_completo = ""

    # Filtra a base
    if filtro_contexto:
        for c, v in filtro_contexto.items():
            df_nivel = df_nivel.xs(v, level=c, drop_level=False)

    # =========================================================
    # 🟢 NÍVEL FINAL: MATERIAIS (Tabelas HTML leves)
    # =========================================================
    if col == 'Desc_Material':
        html_mat = "<div style='margin-bottom: 10px; font-size: 16px; font-weight: bold; color: #333; border-bottom: 2px solid #eee; padding-bottom: 5px;'>📦 Balanço Detalhado por Material</div>"

        df_mat_mes = df_nivel.groupby(['Mes', 'Desc_Material'])[[ano_ant, ano_at]].sum()
        meses_disponiveis = sorted(df_mat_mes.index.get_level_values('Mes').unique())

        if selecao_meses:
            meses_disponiveis = [m for m in meses_disponiveis if m in selecao_meses]

        for m_num in meses_disponiveis:
            nome_mes = meses_nomes.get(m_num, f"Mês {m_num}")
            html_mat += f"<div style='margin-top: 15px; font-weight: bold; color: #444;'>📅 Referência: {nome_mes}</div>"
            html_mat += f"<table style='width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 13px; margin-top: 5px; border: 1px solid #ddd;'>"
            html_mat += f"<tr style='background-color: #f8f9fa;'><th style='padding: 8px; text-align: left; border-bottom: 1px solid #ddd;'>Objeto</th><th style='padding: 8px; text-align: right; border-bottom: 1px solid #ddd;'>{ano_ant}</th><th style='padding: 8px; text-align: right; border-bottom: 1px solid #ddd;'>{ano_at}</th></tr>"

            df_exibir = df_mat_mes.xs(m_num, level='Mes')
            t_ant_total = 0
            t_at_total = 0

            for mat, row in df_exibir.iterrows():
                v_ant = row[ano_ant]
                v_at = row[ano_at]
                t_ant_total += v_ant
                t_at_total += v_at
                html_mat += f"<tr><td style='padding: 8px; border-bottom: 1px solid #eee;'>{mat}</td><td style='padding: 8px; text-align: right; border-bottom: 1px solid #eee;'>{format_brl(v_ant)}</td><td style='padding: 8px; text-align: right; border-bottom: 1px solid #eee;'>{format_brl(v_at)}</td></tr>"

            html_mat += f"<tr style='font-weight: bold; background-color: #f1f3f5;'><td style='padding: 8px;'>Total Contexto</td><td style='padding: 8px; text-align: right;'>{format_brl(t_ant_total)}</td><td style='padding: 8px; text-align: right;'>{format_brl(t_at_total)}</td></tr>"
            html_mat += "</table>"

        return html_mat

    # =========================================================
    # 🔵 NÍVEIS DE GESTÃO (Contas, Localidades, etc.)
    # =========================================================
    itens = sorted(df_nivel.index.get_level_values(col).unique().astype(str).tolist())
    total_itens = len(itens)

    for idx, item in enumerate(itens):
        
        # 🔄 MOTOR DE ANIMAÇÃO (Atualiza apenas na Dimensão Mestre)
        if profundidade == 0 and text_ui is not None and progress_ui is not None:
            porcentagem = int(((idx + 1) / total_itens) * 100)
            text_ui.info(f"⏳ Processando bloco SAP: **{item}** ({idx + 1}/{total_itens})")
            progress_ui.progress(porcentagem)

        df_item = df_nivel.xs(item, level=col, drop_level=False)
        delta_mensal = df_item.groupby(level='Mes', observed=True)['Delta'].sum()

        if selecao_meses:
            selecao_ints = [int(m) for m in selecao_meses]
            delta_mensal = delta_mensal[delta_mensal.index.isin(selecao_ints)]

        var_total = delta_mensal.sum()

        def meets_foco(val):
            if abs(val) < 1000: return False
            if "Savings" in foco_res: return val < 0
            if "Desvios" in foco_res: return val > 0
            return True

        sub_impacto = False
        if profundidade < len(dims) - 1 and dims[profundidade+1] != 'Desc_Material':
            sub_impacto = df_item['Delta'].groupby(level=dims[profundidade+1]).sum().apply(meets_foco).any()

        if meets_foco(var_total) or sub_impacto:
            cor_var = '#d32f2f' if var_total > 0 else '#2e7d32' if var_total < 0 else '#666'
            sinal_var = '+' if var_total > 0 else ''
            label_pref = '📌' if profundidade == 0 else '➥'

            # Construção dos Cards Mensais em HTML
            html_meses = ""
            for m_num in delta_mensal.index:
                val_mes = delta_mensal[m_num]
                cor_mes = '#d32f2f' if val_mes > 0 else '#2e7d32' if val_mes < 0 else '#666'
                sin_mes = '+' if val_mes > 0 else ''
                nome_m = meses_nomes.get(int(m_num), f"Mês {m_num}")
                html_meses += f"<div style='background-color: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 6px; padding: 10px; min-width: 110px; text-align: center; flex: 1;'><div style='font-size: 12px; color: #666; margin-bottom: 4px;'>{nome_m}</div><div style='font-size: 14px; font-weight: bold; color: {cor_mes};'>{sin_mes}{format_brl(val_mes)}</div></div>"

            # Recursão antecipada para os filhos
            novo_contexto = (filtro_contexto or {}).copy()
            novo_contexto[col] = item
            html_filhos = _gerar_html_sap_recursivo(df_nivel, dims, ano_at, ano_ant, foco_res, profundidade + 1, novo_contexto, selecao_meses, None, None)

            # Montagem do Painel (Sem espaços no começo da linha para evitar Markdown Code Block)
            html_item = (
                f"<details style='margin-bottom: 10px; border: 1px solid #d1d5db; border-radius: 8px; background-color: #ffffff; overflow: hidden; box-shadow: 0 1px 2px rgba(0,0,0,0.05);'>"
                f"<summary style='padding: 14px; font-weight: bold; cursor: pointer; background-color: #fcfcfc; border-bottom: 1px solid #eee; font-family: sans-serif; font-size: 15px;'>"
                f"{label_pref} {item} <span style='font-weight: normal; color: #555; margin-left: 10px;'>| Total Período: <span style='color: {cor_var}; font-weight: bold;'>{sinal_var}{format_brl(var_total)}</span></span>"
                f"</summary>"
                f"<div style='padding: 20px; font-family: sans-serif;'>"
                f"<div style='font-weight: bold; margin-bottom: 12px; font-size: 14px; color: #444;'>Variação Mensal YoY (Impacto no Resultado):</div>"
                f"<div style='display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px;'>"
                f"{html_meses}"
                f"</div>"
                f"<div style='border-left: 3px solid #e5e7eb; padding-left: 15px;'>"
                f"{html_filhos}"
                f"</div>"
                f"</div>"
                f"</details>"
            )
            html_completo += html_item

    return html_completo
