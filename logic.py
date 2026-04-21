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
    import io

    for f in files:
        try: 
            # 🚀 ESCUDO DE MEMÓRIA
            file_buffer = io.BytesIO(f.read())
            
            if f.name.endswith('.csv'):
                sample_bytes = file_buffer.read(10000)
                file_buffer.seek(0)
                
                try:
                    sample_bytes.decode('utf-8-sig')
                    encoding_tentativa = 'utf-8-sig'
                except UnicodeDecodeError:
                    encoding_tentativa = 'cp1252'
                
                try:
                    sample_text = sample_bytes.decode(encoding_tentativa, errors='ignore')
                    dialect = csv.Sniffer().sniff(sample_text, delimiters=',;\t|')
                    sep_detectado = dialect.delimiter
                except:
                    sep_detectado = ';' 

                file_buffer.seek(0)
                df_header = pd.read_csv(file_buffer, sep=sep_detectado, engine='python', encoding=encoding_tentativa, nrows=100)
            else:
                df_header = pd.read_excel(file_buffer, engine='openpyxl', nrows=100)
                sep_detectado = None
                encoding_tentativa = None
            
            # =========================================================
            # 2. MAPEAMENTO INTELIGENTE (O bloco que havia sumido)
            # =========================================================
            colunas_reais = df_header.columns.tolist()
            col_map_arquivo = {str(c).strip().lower(): c for c in colunas_reais}
            map_limpo = {str(k).strip().lower(): v for k, v in mapeamento.items()}
            
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
            
            # B) O "TESTE DE DNA" COM OS PARQUETS
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

            # C) FALLBACK PARA O JSON
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
                cols_lidas = [str(c) for c in colunas_reais[:15]] 
                
                msg_erro = (
                    f"❌ **A coluna de DATA não foi encontrada no arquivo:** `{f.name}`.\n\n"
                    f"🔍 **Raio-X do que o .exe enxergou na sua planilha:**\n"
                    f"`{cols_lidas}`\n\n"
                    f"📂 **JSON procurado em:** `{caminho_usado}`"
                )
                return msg_erro, None, None, None

            # =========================================================
            # 4. LEITURA COMPLETA OTIMIZADA
            # =========================================================
            file_buffer.seek(0)
            colunas_para_ler = list(tradução_final.keys())
            if f.name.endswith('.csv'):
                df_temp = pd.read_csv(file_buffer, usecols=colunas_para_ler, sep=sep_detectado, engine='c', encoding=encoding_tentativa, low_memory=False)
            else:
                df_temp = pd.read_excel(file_buffer, usecols=colunas_para_ler, engine='openpyxl')

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
                
            if 'Classe_Custo' in df_temp.columns:
                df_temp['Classe_Custo'] = df_temp['Classe_Custo'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            if 'Centro_Custo' in df_temp.columns:
                df_temp['Centro_Custo'] = df_temp['Centro_Custo'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

            dfs.append(df_temp)
            gc.collect()

        except Exception as e: 
            return f"Erro no arquivo {f.name}: {str(e)}", None, None, None
    
    if not dfs: return "Nenhum dado processado.", None, None, None
    
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
        df_contas['Conta'] = df_contas['Conta'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        df_cc['CC'] = df_cc['CC'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        
        if 'Classe_Custo' in df.columns:
            df['Classe_Custo'] = df['Classe_Custo'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        else:
            df['Classe_Custo'] = "000000"
            
        if 'Centro_Custo' in df.columns:
            df['Centro_Custo'] = df['Centro_Custo'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        else:
            df['Centro_Custo'] = "CC_INDEFINIDO"
        
        df_contas = df_contas.groupby('Conta', as_index=False).first()
        df_cc = df_cc.groupby('CC', as_index=False).first()
        
        df = df.merge(df_contas[['Conta', 'Desc Conta', 'Pacote', 'P&L']], 
                      left_on='Classe_Custo', right_on='Conta', how='left', validate='m:1')
        del df_contas 
        gc.collect()  
        
        df = df.merge(df_cc[['CC', 'Descricao CC', 'VP', 'Diretoria', 'Local', 'Localidade', 'Empresa', 'Responsável']], 
                      left_on='Centro_Custo', right_on='CC', how='left', validate='m:1')
        del df_cc 
        gc.collect() 
        
        df['Desc_Conta'] = df['Desc Conta'].astype(object).fillna("Sem Descrição") + " - " + df['Classe_Custo'].astype(object).fillna("000000")
        df['P_L'] = df['Responsável'].astype(object).fillna("Não Informado") 
        df['VP'] = df['VP'].astype(object).fillna("Não Informado")
        df['Localidade'] = df['Localidade'].astype(object).fillna("Não Informado")
        df['Pacote'] = df['Pacote'].astype(object).fillna("Não Informado")
        df['Diretoria'] = df['Diretoria'].astype(object).fillna("Não Informado")
        df['Centro_Custo'] = df['Descricao CC'].astype(object).fillna("Sem Descrição") + " (" + df['Centro_Custo'].astype(object).fillna("000") + ")"
        
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