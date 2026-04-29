import sys
import streamlit as st
import pandas as pd
import gc
import calendar
import json, os
import io
from utils import mapeamento, get_yoy_data

def compilar_html_para_download(html_conteudo, titulo="Relatório de Produtividade", foco="Análise 360° (Ambos)", itens_disponiveis=None, meses=None):
    """Envolve o conteúdo do relatório em um documento HTML com blocos minimizáveis e link funcional."""
    
    mapa_nomes = {
        'Desc_Conta': 'Conta(s) contábil(is)',
        'P_L': 'Linha(s) de P&L',
        'VP': 'VP(s)',
        'Localidade': 'Localidade(s)',
        'Centro_Custo': 'Centro(s) de Custo',
        'Pacote': 'Pacote(s)'
    }
    
    # 1. Tratamento das variáveis de contexto
    meses_str = ", ".join([str(m) for m in sorted(meses)]) if meses and meses != "AGUARDANDO" else "Nenhum selecionado"
    
    html_itens_detalhados = ""
    if itens_disponiveis:
        for col, valores in itens_disponiveis.items():
            if valores: 
                nome_amigavel = mapa_nomes.get(col, col)
                valores_str = ", ".join([str(v) for v in valores])
                qtd = len(valores)
                
                html_itens_detalhados += f"""
                <details class="item-detail-box">
                    <summary>▸ <strong>{nome_amigavel}</strong> <span style="opacity: 0.6; font-size: 11px; margin-left: 5px;">({qtd} itens)</span></summary>
                    <div class="item-content">{valores_str}</div>
                </details>
                """

    if not html_itens_detalhados:
        html_itens_detalhados = "<div style='color: #aaa; font-size: 13px; padding-top: 10px;'>Visão completa da base (sem dimensões detalhadas aplicadas).</div>"

    # 2. Montagem do HTML Final (Note as chaves duplas no CSS para evitar erros de renderização)
    html_completo = f"""
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <title>{titulo}</title>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; padding: 40px; background-color: #121212; color: #e0e0e0; line-height: 1.6; }}
            h1 {{ color: #ffffff; margin-bottom: 5px; font-weight: bold; }}
            .brand-sub {{ color: #888; font-size: 14px; margin-top: 0; margin-bottom: 30px; }}
            .metadata-box {{ background-color: #1e1e1e; padding: 20px; border-radius: 12px; border: 1px solid #333; margin-bottom: 30px; }}
            .metadata-box .summary-line {{ display: flex; gap: 40px; margin-bottom: 15px; font-size: 15px; }}
            .metadata-box strong {{ color: #60a5fa; margin-right: 8px; }}
            .filters-grid {{ display: flex; flex-direction: column; gap: 8px; padding-top: 15px; border-top: 1px solid #333; }}
            .item-detail-box {{ margin-bottom: 0 !important; border: 1px solid #2a2a2a !important; border-radius: 6px !important; background-color: #1a1a1a !important; }}
            .item-detail-box summary {{ padding: 10px 15px !important; font-size: 13px !important; cursor: pointer; color: #aaa !important; }}
            .item-detail-box[open] summary {{ color: #60a5fa !important; }}
            .item-content {{ padding: 12px 15px; font-size: 12px; color: #ccc; background-color: #141414; }}
            details {{ margin-bottom: 15px; border: 1px solid #333; border-radius: 8px; background-color: #1e1e1e; overflow: hidden; }}
            summary {{ padding: 16px; font-weight: bold; cursor: pointer; background-color: #252525; color: #fff; }}
            div[style*='display: flex'] {{ display: flex; gap: 12px; flex-wrap: wrap; margin-top: 10px; }}
            div[style*='border-radius: 5px'], div[style*='border-radius: 6px'] {{ background-color: #2a2a25 !important; border: 1px solid #444 !important; color: #fff !important; padding: 12px !important; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px; }}
            th {{ background-color: #252525; padding: 12px; text-align: left; color: #888; border-bottom: 2px solid #333; }}
            td {{ padding: 12px; border-bottom: 1px solid #252525; }}
        </style>
    </head>
    <body>
        <h1>{titulo}</h1>
        <p class="brand-sub">
            Extraído do <a href="https://paimjv.github.io/analise-de-produtividade-pepsico/" target="_blank" style="color: #60a5fa; text-decoration: none; font-weight: bold;">Dashboard de Produtividade PepsiCo</a> • Exportação Estática
        </p>
        
        <div class="metadata-box">
            <div class="summary-line">
                <div><strong>Foco da Análise:</strong> {foco}</div>
                <div><strong>Meses Analisados:</strong> {meses_str}</div>
            </div>
            
            <div class="filters-grid">
                {html_itens_detalhados}
            </div>
        </div>

        <hr style="border: 0; border-top: 1px solid #333; margin-bottom: 40px;">
        
        <div class="report-container">
            {html_conteudo}
        </div>
    </body>
    </html>
    """
    return html_completo

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

@st.cache_data(show_spinner=False)
def carregar_bases_apoio():
    """Carrega as bases blindadas, dispara o Alarme se sumirem e economiza memória."""
    caminho_contas = encontrar_arquivo_local("dim_contas.csv.gz")
    caminho_cc = encontrar_arquivo_local("dim_centros_custo.csv.gz")
    
    # 🚨 ALARME DE ARQUIVO INEXISTENTE
    if not caminho_contas or not caminho_cc:
        st.error("🚨 ARQUIVOS AUXILIARES NÃO ENCONTRADOS! Verifique se os arquivos 'dim_contas.csv.gz' e 'dim_centros_custo.csv.gz' estão no GitHub e nomeados corretamente no index.html.")
        return None, None
        
    try:
        df_contas, df_cc = None, None
        import io
        
        # 🚀 MÁGICA DA MEMÓRIA: Lemos APENAS as colunas que vamos usar no merge!
        cols_contas = ['Conta', 'Desc Conta', 'Pacote', 'P&L']
        cols_cc = ['CC', 'Descricao CC', 'VP', 'Diretoria', 'Local', 'Localidade', 'Empresa', 'Responsável']
        
        if caminho_contas:
            with open(caminho_contas, "rb") as f:
                # Fatiamos em blocos e filtramos as colunas para não explodir a memória C
                chunks_contas = pd.read_csv(io.BytesIO(f.read()), sep=';', encoding='utf-8-sig', compression='gzip', 
                                            usecols=cols_contas, dtype={'Conta': str}, chunksize=15000)
                df_contas = pd.concat(chunks_contas, ignore_index=True)
                
        if caminho_cc:
            with open(caminho_cc, "rb") as f:
                chunks_cc = pd.read_csv(io.BytesIO(f.read()), sep=';', encoding='utf-8-sig', compression='gzip', 
                                        usecols=cols_cc, dtype={'CC': str}, chunksize=15000)
                df_cc = pd.concat(chunks_cc, ignore_index=True)
                
        return df_contas, df_cc
    except Exception as e:
        st.warning(f"⚠️ Erro ao abrir as bases de apoio: {e}")
        return None, None

def load_and_process_base(files):
    import time
    import streamlit as st
    
    # 🚀 A "Função Casca": Chama o spinner nativo, força a tela a atualizar (sleep) e chama o seu código
    with st.spinner("⏳ Lendo arquivos, otimizando base e cruzando chaves SAP..."):
        time.sleep(0.5) 
        return _load_and_process_base_internal(files)

def _load_and_process_base_internal(files):
    dfs = []
    from utils import mapeamento
    import csv
    import io
    
    for f in files:
        try: 
            # 🚀 ESCUDO DE MEMÓRIA
            file_buffer = io.BytesIO(f.getvalue())
            
            if f.name.endswith('.csv'):
                sample_bytes = file_buffer.read(10000)
                file_buffer.seek(0)
                
                encodings_teste = ['utf-8-sig', 'cp1252', 'latin-1', 'utf-16le']
                encoding_tentativa = 'utf-8-sig'
                
                for enc in encodings_teste:
                    try:
                        sample_bytes.decode(enc)
                        encoding_tentativa = enc
                        break 
                    except UnicodeDecodeError:
                        continue
                
                sep_detectado = ';' 
                file_buffer.seek(0)
                df_header = pd.read_csv(file_buffer, sep=sep_detectado, engine='c', encoding=encoding_tentativa, nrows=100)
            else:
                df_header = pd.read_excel(file_buffer, engine='openpyxl', nrows=100)
                sep_detectado = None
                encoding_tentativa = None
            
            colunas_reais = df_header.columns.tolist()
            col_map_arquivo = {str(c).strip().lower(): c for c in colunas_reais}
            map_limpo = {str(k).strip().lower(): v for k, v in mapeamento.items()}
            
            map_limpo['data de lançamento'] = 'Data_Lancamento'
            map_limpo['dt.lçto'] = 'Data_Lancamento'
            map_limpo['data de lancamento'] = 'Data_Lancamento'
            
            tradução_final = {}
            colunas_sistema_obrigatorias = ['Classe_Custo', 'Centro_Custo', 'Valor', 'Data_Lancamento']
            
            for k_limpo, v_sistema in map_limpo.items():
                if k_limpo in col_map_arquivo:
                    nome_original = col_map_arquivo[k_limpo]
                    tradução_final[nome_original] = v_sistema
            
            faltantes = [c for c in colunas_sistema_obrigatorias if c not in tradução_final.values()]
            colunas_ignotas = [c for c in colunas_reais if c not in tradução_final.keys()]
            
            df_contas_ref, df_cc_ref = carregar_bases_apoio()
            set_contas = set(df_contas_ref['Conta'].dropna().astype(str).str.replace(r'\.0$', '', regex=True).str.strip()) if df_contas_ref is not None else set()
            set_cc = set(df_cc_ref['CC'].dropna().astype(str).str.replace(r'\.0$', '', regex=True).str.strip()) if df_cc_ref is not None else set()
            
            for col_arq in colunas_ignotas[:]:
                if not faltantes: break
                
                amostra = set(df_header[col_arq].dropna().astype(str).str.replace(r'\.0$', '', regex=True).str.strip().tolist())
                
                if 'Classe_Custo' in faltantes and amostra.intersection(set_contas):
                    tradução_final[col_arq] = 'Classe_Custo'
                    faltantes.remove('Classe_Custo')
                    colunas_ignotas.remove(col_arq)
                    continue
                    
                if 'Centro_Custo' in faltantes and amostra.intersection(set_cc):
                    tradução_final[col_arq] = 'Centro_Custo'
                    faltantes.remove('Centro_Custo')
                    colunas_ignotas.remove(col_arq)
                    continue

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
                                
            if 'Data_Lancamento' not in tradução_final.values():
                msg_erro = f"❌ **A coluna de DATA não foi encontrada no arquivo:** `{f.name}`."
                return msg_erro, None, None, None

            file_buffer.seek(0)
            colunas_para_ler = list(tradução_final.keys())
            
            if f.name.endswith('.csv'):
                lista_pedacos = []
                chunks = pd.read_csv(
                    file_buffer, 
                    usecols=colunas_para_ler, 
                    sep=sep_detectado, 
                    engine='c', 
                    encoding=encoding_tentativa, 
                    chunksize=15000
                )
                for pedaco in chunks:
                    lista_pedacos.append(pedaco)
                    
                df_temp = pd.concat(lista_pedacos, ignore_index=True)
                del lista_pedacos, chunks 
            else:
                df_temp = pd.read_excel(file_buffer, usecols=colunas_para_ler, engine='openpyxl')

            df_temp.rename(columns=tradução_final, inplace=True)

            if 'Data_Lancamento' in df_temp.columns:
                df_temp['Data_Lancamento'] = pd.to_datetime(df_temp['Data_Lancamento'], dayfirst=True, errors='coerce')
                df_temp = df_temp.dropna(subset=['Data_Lancamento'])
                df_temp['Ano'] = df_temp['Data_Lancamento'].dt.year.astype(int)
                df_temp['Mes'] = df_temp['Data_Lancamento'].dt.month.astype(int)

            if 'Valor' in df_temp.columns:
                if df_temp['Valor'].dtype == object:
                    df_temp['Valor'] = df_temp['Valor'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df_temp['Valor'] = pd.to_numeric(df_temp['Valor'], errors='coerce').fillna(0).astype('float32')
                
            if 'Classe_Custo' in df_temp.columns:
                df_temp['Classe_Custo'] = df_temp['Classe_Custo'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            if 'Centro_Custo' in df_temp.columns:
                df_temp['Centro_Custo'] = df_temp['Centro_Custo'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

            dfs.append(df_temp)
            gc.collect()

        except Exception as e: 
            return f"Erro no arquivo {f.name}: {str(e)}", None, None, None
    
    if not dfs: 
        return "Nenhum dado processado.", None, None, None
    
    df = pd.concat(dfs, ignore_index=True)
    del dfs
    gc.collect()

    if 'Desc_Material' not in df.columns:
        df['Desc_Material'] = "Não Informado"
    df['Desc_Material'] = df['Desc_Material'].astype(str).fillna("Não Informado")

    df = df.groupby(
        ['Classe_Custo', 'Centro_Custo', 'Desc_Material', 'Ano', 'Mes'], 
        dropna=False, 
        as_index=False
    ).agg({
        'Valor': 'sum',
        'Data_Lancamento': 'max' 
    })
    gc.collect()

    df_contas, df_cc = carregar_bases_apoio()

    if df_contas is not None and df_cc is not None:
        df_contas['Conta'] = df_contas['Conta'].astype(str).str.split('.').str[0].str.strip().str.lstrip('0').str.upper()
        df_cc['CC'] = df_cc['CC'].astype(str).str.split('.').str[0].str.strip().str.lstrip('0').str.upper()
        
        if 'Classe_Custo' in df.columns:
            df['Classe_Custo'] = df['Classe_Custo'].astype(str).str.split('.').str[0].str.strip().str.lstrip('0').str.upper()
        else:
            df['Classe_Custo'] = "000000"
            
        if 'Centro_Custo' in df.columns:
            df['Centro_Custo'] = df['Centro_Custo'].astype(str).str.split('.').str[0].str.strip().str.lstrip('0').str.upper()
        else:
            df['Centro_Custo'] = "CC_INDEFINIDO"
        
        df_contas = df_contas.drop_duplicates(subset=['Conta'])
        df_cc = df_cc.drop_duplicates(subset=['CC'])
        
        df = df.merge(df_contas[['Conta', 'Desc Conta', 'Pacote', 'P&L']], 
                      left_on='Classe_Custo', right_on='Conta', how='left')
        del df_contas 
        gc.collect()  
        
        df = df.merge(df_cc[['CC', 'Descricao CC', 'VP', 'Diretoria', 'Local', 'Localidade', 'Empresa', 'Responsável']], 
                      left_on='Centro_Custo', right_on='CC', how='left')
        del df_cc 
        gc.collect() 
        
        df['Desc_Conta'] = df['Desc Conta'].fillna("Cod") + " - " + df['Classe_Custo'].fillna("000000")
        df['P_L'] = df['Responsável'].fillna("Não Encontrado") 
        df['VP'] = df['VP'].fillna("Não Encontrado")
        df['Localidade'] = df['Localidade'].fillna("Não Encontrado")
        df['Pacote'] = df['Pacote'].fillna("Não Encontrado")
        df['Diretoria'] = df['Diretoria'].fillna("Não Encontrado")
        df['Centro_Custo'] = df['Descricao CC'].fillna("CC") + " (" + df['Centro_Custo'].fillna("000") + ")"
        
        colunas_lixo = ['Classe_Custo', 'Conta', 'Desc Conta', 'CC', 'Descricao CC', 'Empresa', 'Local', 'Responsável']
        col_existentes = [c for c in colunas_lixo if c in df.columns]
        df.drop(columns=col_existentes, inplace=True)
        gc.collect() 
        
    else:
        df['Desc_Conta'] = df.get('Classe_Custo', '0000')
        df['P_L'] = df.get('P_L', "Não Informado")
        df['VP'] = df.get('VP', "Não Informado")
        df['Localidade'] = df.get('Localidade', "Não Informado")

    if 'Desc_Material' not in df.columns:
        df['Desc_Material'] = "Não Informado"
    df['Desc_Material'] = df['Desc_Material'].astype(object).fillna("Não Informado")

    colunas_texto = ['Desc_Conta', 'P_L', 'VP', 'Localidade', 'Centro_Custo', 'Pacote', 'Diretoria', 'Desc_Material']
    for col in colunas_texto:
        if col in df.columns:
            df[col] = df[col].astype('category')

    return get_yoy_data(df)

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
        
        st.session_state.ultimo_html_gerado = html_final

    # 3. Limpa a barra de progresso da tela quando o trabalho terminar
    aviso_texto.empty()
    barra_progresso.empty()

    if html_final.strip() == "":
        st.info("Nenhum registro atende aos critérios de foco selecionados.")
    else:
        st.success("✅ Relatório detalhado renderizado com sucesso!")
        st.markdown(f"<div style='padding-bottom: 50px;'>{html_final}</div>", unsafe_allow_html=True)

def compilar_html_para_download(html_conteudo, titulo="Relatório de Produtividade", foco="Análise 360° (Ambos)", itens_disponiveis=None, meses=None):
    """Gera um arquivo HTML completo com CSS blindado e link de âncora funcional."""
    
    mapa_nomes = {
        'Desc_Conta': 'Conta(s) contábil(is)',
        'P_L': 'Linha(s) de P&L',
        'VP': 'VP(s)',
        'Localidade': 'Localidade(s)',
        'Centro_Custo': 'Centro(s) de Custo',
        'Pacote': 'Pacote(s)'
    }
    
    # 1. Preparação das variáveis de contexto
    meses_str = ", ".join([str(m) for m in sorted(meses)]) if meses and meses != "AGUARDANDO" else "Nenhum selecionado"
    
    html_itens_detalhados = ""
    if itens_disponiveis:
        for col, valores in itens_disponiveis.items():
            if valores: 
                nome_amigavel = mapa_nomes.get(col, col)
                valores_str = ", ".join([str(v) for v in valores])
                qtd = len(valores)
                
                html_itens_detalhados += f"""
                <details class="item-detail-box">
                    <summary>▸ <strong>{nome_amigavel}</strong> <span style="opacity: 0.6; font-size: 11px; margin-left: 5px;">({qtd} itens)</span></summary>
                    <div class="item-content">{valores_str}</div>
                </details>
                """

    if not html_itens_detalhados:
        html_itens_detalhados = "<div style='color: #aaa; font-size: 13px; padding-top: 10px;'>Visão completa da base.</div>"

    # 2. Montagem do HTML (Note o uso de {{ }} no CSS para escapar as chaves do Python)
    html_completo = f"""
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <title>{titulo}</title>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; padding: 40px; background-color: #121212; color: #e0e0e0; line-height: 1.6; }}
            h1 {{ color: #ffffff; margin-bottom: 5px; font-weight: bold; }}
            .brand-sub {{ color: #888; font-size: 14px; margin-top: 0; margin-bottom: 30px; }}
            .metadata-box {{ background-color: #1e1e1e; padding: 20px; border-radius: 12px; border: 1px solid #333; margin-bottom: 30px; }}
            .metadata-box .summary-line {{ display: flex; gap: 40px; margin-bottom: 15px; font-size: 15px; }}
            .metadata-box strong {{ color: #60a5fa; margin-right: 8px; }}
            .filters-grid {{ display: flex; flex-direction: column; gap: 8px; padding-top: 15px; border-top: 1px solid #333; }}
            .item-detail-box {{ margin-bottom: 0 !important; border: 1px solid #2a2a2a !important; border-radius: 6px !important; background-color: #1a1a1a !important; }}
            .item-detail-box summary {{ padding: 10px 15px !important; font-size: 13px !important; cursor: pointer; color: #aaa !important; }}
            .item-detail-box[open] summary {{ border-bottom: 1px solid #2a2a2a !important; color: #60a5fa !important; }}
            .item-content {{ padding: 12px 15px; font-size: 12px; color: #ccc; line-height: 1.6; background-color: #141414; border-radius: 0 0 6px 6px; }}
            details {{ margin-bottom: 15px; border: 1px solid #333; border-radius: 8px; background-color: #1e1e1e; overflow: hidden; }}
            summary {{ padding: 16px; font-weight: bold; cursor: pointer; background-color: #252525; border-bottom: 1px solid #333; color: #fff; }}
            div[style*='display: flex'] {{ display: flex; gap: 12px; flex-wrap: wrap; margin-top: 10px; }}
            div[style*='border-radius: 5px'], div[style*='border-radius: 6px'] {{ background-color: #2a2a25 !important; border: 1px solid #444 !important; color: #fff !important; padding: 12px !important; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px; }}
            th {{ background-color: #252525; padding: 12px; text-align: left; color: #888; border-bottom: 2px solid #333; }}
            td {{ padding: 12px; border-bottom: 1px solid #252525; }}
            .loader-mini {{ display: none; }}
        </style>
    </head>
    <body>
        <h1>{titulo}</h1>
        <p class="brand-sub">
            Extraído do <a href="https://paimjv.github.io/analise-de-produtividade-pepsico/" target="_blank" style="color: #60a5fa; text-decoration: none; font-weight: bold;">Dashboard de Produtividade PepsiCo</a> • Exportação Estática
        </p>
        
        <div class="metadata-box">
            <div class="summary-line">
                <div><strong>Foco da Análise:</strong> {foco}</div>
                <div><strong>Meses Analisados:</strong> {meses_str}</div>
            </div>
            
            <div class="filters-grid">
                {html_itens_detalhados}
            </div>
        </div>

        <hr style="border: 0; border-top: 1px solid #333; margin-bottom: 40px;">
        
        <div class="report-container">
            {html_conteudo}
        </div>
    </body>
    </html>
    """
    return html_completo

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
        html_mat = "<div style='margin-bottom: 10px; font-size: 16px; font-weight: bold; color: var(--text-color); border-bottom: 2px solid rgba(128,128,128,0.2); padding-bottom: 5px;'>📦 Balanço Detalhado por Material</div>"

        df_mat_mes = df_nivel.groupby(['Mes', 'Desc_Material'])[[ano_ant, ano_at]].sum()
        meses_disponiveis = sorted(df_mat_mes.index.get_level_values('Mes').unique())

        if selecao_meses:
            meses_disponiveis = [m for m in meses_disponiveis if m in selecao_meses]

        for m_num in meses_disponiveis:
            nome_mes = meses_nomes.get(m_num, f"Mês {m_num}")
            html_mat += f"<div style='margin-top: 15px; font-weight: bold; color: var(--text-color);'>📅 Referência: {nome_mes}</div>"
            html_mat += f"<table style='width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 13px; margin-top: 5px; border: 1px solid rgba(128,128,128,0.2);'>"
            html_mat += f"<tr style='background-color: var(--secondary-background-color);'><th style='padding: 8px; text-align: left; border-bottom: 1px solid rgba(128,128,128,0.2);'>Objeto</th><th style='padding: 8px; text-align: right; border-bottom: 1px solid rgba(128,128,128,0.2);'>{ano_ant}</th><th style='padding: 8px; text-align: right; border-bottom: 1px solid rgba(128,128,128,0.2);'>{ano_at}</th></tr>"

            df_exibir = df_mat_mes.xs(m_num, level='Mes')
            t_ant_total = 0
            t_at_total = 0

            for mat, row in df_exibir.iterrows():
                v_ant = row[ano_ant]
                v_at = row[ano_at]
                t_ant_total += v_ant
                t_at_total += v_at
                html_mat += f"<tr><td style='padding: 8px; border-bottom: 1px solid rgba(128,128,128,0.1);'>{mat}</td><td style='padding: 8px; text-align: right; border-bottom: 1px solid rgba(128,128,128,0.1);'>{format_brl(v_ant)}</td><td style='padding: 8px; text-align: right; border-bottom: 1px solid rgba(128,128,128,0.1);'>{format_brl(v_at)}</td></tr>"

            html_mat += f"<tr style='font-weight: bold; background-color: var(--secondary-background-color);'><td style='padding: 8px;'>Total Contexto</td><td style='padding: 8px; text-align: right;'>{format_brl(t_ant_total)}</td><td style='padding: 8px; text-align: right;'>{format_brl(t_at_total)}</td></tr>"
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
            # 🚀 Cores dinâmicas e mais vibrantes para ler bem tanto no claro quanto escuro
            cor_var = '#ff4b4b' if var_total > 0 else '#09ab3b' if var_total < 0 else 'var(--text-color)'
            sinal_var = '+' if var_total > 0 else ''
            label_pref = '📌' if profundidade == 0 else '➥'

            # Construção dos Cards Mensais em HTML
            html_meses = ""
            for m_num in delta_mensal.index:
                val_mes = delta_mensal[m_num]
                cor_mes = '#ff4b4b' if val_mes > 0 else '#09ab3b' if val_mes < 0 else 'var(--text-color)'
                sin_mes = '+' if val_mes > 0 else ''
                nome_m = meses_nomes.get(int(m_num), f"Mês {m_num}")
                html_meses += f"<div style='background-color: var(--secondary-background-color); border: 1px solid rgba(128,128,128,0.2); border-radius: 6px; padding: 10px; min-width: 110px; text-align: center; flex: 1;'><div style='font-size: 12px; color: var(--text-color); opacity: 0.8; margin-bottom: 4px;'>{nome_m}</div><div style='font-size: 14px; font-weight: bold; color: {cor_mes};'>{sin_mes}{format_brl(val_mes)}</div></div>"

            # Recursão antecipada para os filhos
            novo_contexto = (filtro_contexto or {}).copy()
            novo_contexto[col] = item
            html_filhos = _gerar_html_sap_recursivo(df_nivel, dims, ano_at, ano_ant, foco_res, profundidade + 1, novo_contexto, selecao_meses, None, None)

            # Montagem do Painel (Agora 100% responsivo ao tema do usuário)
            html_item = (
                f"<details style='margin-bottom: 10px; border: 1px solid rgba(128,128,128,0.2); border-radius: 8px; background-color: transparent; overflow: hidden; box-shadow: 0 1px 2px rgba(0,0,0,0.05);'>"
                f"<summary style='padding: 14px; font-weight: bold; cursor: pointer; background-color: var(--secondary-background-color); border-bottom: 1px solid rgba(128,128,128,0.2); font-family: sans-serif; font-size: 15px; color: var(--text-color);'>"
                f"{label_pref} {item} <span style='font-weight: normal; opacity: 0.8; margin-left: 10px;'>| Total Período: <span style='color: {cor_var}; font-weight: bold;'>{sinal_var}{format_brl(var_total)}</span></span>"
                f"</summary>"
                f"<div style='padding: 20px; font-family: sans-serif; color: var(--text-color);'>"
                f"<div style='font-weight: bold; margin-bottom: 12px; font-size: 14px; opacity: 0.9;'>Variação Mensal YoY (Impacto no Resultado):</div>"
                f"<div style='display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px;'>"
                f"{html_meses}"
                f"</div>"
                f"<div style='border-left: 3px solid rgba(128,128,128,0.2); padding-left: 15px;'>"
                f"{html_filhos}"
                f"</div>"
                f"</div>"
                f"</details>"
            )
            html_completo += html_item

    return html_completo
