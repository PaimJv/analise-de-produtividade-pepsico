import streamlit as st
import pandas as pd
import gc # Garbage Collector
import json, os
from utils import mapeamento, get_yoy_data

def carregar_referencia():
    """Carrega o JSON de assinaturas se ele existir."""
    if os.path.exists('referencia_colunas.json'):
        with open('referencia_colunas.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

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

@st.cache_data(show_spinner="Otimizando base de dados...")
def load_and_process_base(files):
    dfs = []
    from utils import mapeamento
    import csv
    
    for f in files:
        try: # --- INÍCIO DO TRY POR ARQUIVO ---
            # 1. LEITURA DE AMOSTRA (100 linhas para o "detetive" ter pistas)
            if f.name.endswith('.csv'):
                encoding_tentativa = 'utf-8-sig' 
                try:
                    df_header = pd.read_csv(f, sep=None, engine='python', encoding=encoding_tentativa, nrows=100)
                except:
                    encoding_tentativa = 'latin-1'
                    f.seek(0)
                    df_header = pd.read_csv(f, sep=None, engine='python', encoding=encoding_tentativa, nrows=100)
                
                f.seek(0)
                try:
                    sample = f.read(8192).decode(encoding_tentativa)
                    dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
                    sep_detectado = dialect.delimiter
                except:
                    sep_detectado = ';' # Fallback padrão SAP
                f.seek(0)
            else:
                df_header = pd.read_excel(f, engine='calamine', nrows=100)
                sep_detectado = None

            # 2. MAPEAMENTO INTELIGENTE (NOME + CONTEÚDO/SINÔNIMOS)
            colunas_reais = df_header.columns.tolist()
            col_map_arquivo = {c.strip().lower(): c for c in colunas_reais}
            map_limpo = {k.strip().lower(): v for k, v in mapeamento.items()}
            
            tradução_final = {}
            colunas_sistema_obrigatorias = ['VP', 'Localidade', 'Centro_Custo', 'P_L', 'Valor', 'Data_Lancamento']
            
            # A) BUSCA POR NOME (Dicionário Utils)
            for k_limpo, v_sistema in map_limpo.items():
                if k_limpo in col_map_arquivo:
                    nome_original = col_map_arquivo[k_limpo]
                    tradução_final[nome_original] = v_sistema
            
            # B) BUSCA POR HEURÍSTICA (JSON de Referência)
            faltantes = [c for c in colunas_sistema_obrigatorias if c not in tradução_final.values()]
            
            if faltantes and os.path.exists('referencia_colunas.json'):
                with open('referencia_colunas.json', 'r', encoding='utf-8') as ref_file:
                    ref_data = json.load(ref_file)
                
                colunas_ignotas = [c for c in colunas_reais if c not in tradução_final.keys()]
                
                for col_arq in colunas_ignotas[:]: # Cópia para permitir remoção
                    nome_col_arq_limpo = col_arq.strip().lower()
                    for nome_sistema_ref, exemplos_ref in ref_data.items():
                        if nome_sistema_ref in faltantes:
                            sinonimos = [str(e).strip().lower() for e in exemplos_ref]
                            if nome_col_arq_limpo in sinonimos:
                                tradução_final[col_arq] = nome_sistema_ref
                                faltantes.remove(nome_sistema_ref)
                                colunas_ignotas.remove(col_arq)
                                break
                
                # --- ONDA 2: BUSCA POR CONTEÚDO (DNA) ---
                # Só entra aqui se o nome da coluna não deu match na Onda 1
                for col_arq in colunas_ignotas:
                    if not faltantes: break
                    
                    amostra_real = [str(x) for x in df_header[col_arq].dropna().unique().tolist()]
                    
                    for nome_sistema_ref, exemplos_ref in ref_data.items():
                        if nome_sistema_ref in faltantes:
                            exemplos_baixos = [str(e).lower() for e in exemplos_ref]
                            
                            # if nome_sistema_ref == "Valor":
                            #     continue
                            
                            match_encontrado = False
                            for dado_arquivo in amostra_real:
                                for ex_json in exemplos_baixos:
                                    if ex_json in dado_arquivo: 
                                        match_encontrado = True
                                        break
                                if match_encontrado: break
                            
                            if match_encontrado:
                                tradução_final[col_arq] = nome_sistema_ref
                                faltantes.remove(nome_sistema_ref)
                                break
                
            # 3. TRAVA DE SEGURANÇA (Evita o KeyError: 'Mes')
            if 'Data_Lancamento' not in tradução_final.values():
                return f"Erro: A coluna de DATA não foi encontrada em {f.name}.", None, None, None

            # 4. LEITURA COMPLETA OTIMIZADA
            f.seek(0)
            colunas_para_ler = list(tradução_final.keys())
            if f.name.endswith('.csv'):
                df_temp = pd.read_csv(f, usecols=colunas_para_ler, sep=sep_detectado, engine='c', encoding=encoding_tentativa, low_memory=False)
            else:
                df_temp = pd.read_excel(f, usecols=colunas_para_ler, engine='calamine')

            df_temp.rename(columns=tradução_final, inplace=True)

            # 5. FEATURE ENGINEERING (Ano, Mes, Desc_Conta)
            if 'Data_Lancamento' in df_temp.columns:
                df_temp['Data_Lancamento'] = pd.to_datetime(df_temp['Data_Lancamento'], dayfirst=True, errors='coerce')
                df_temp = df_temp.dropna(subset=['Data_Lancamento'])
                df_temp['Ano'] = df_temp['Data_Lancamento'].dt.year.astype(int)
                df_temp['Mes'] = df_temp['Data_Lancamento'].dt.month.astype(int)

            den = df_temp['DenClsCst'].fillna("Sem Descrição").astype(str) if 'DenClsCst' in df_temp.columns else "Sem Descrição"
            cod = df_temp['Classe_Custo'].fillna("000000").astype(str) if 'Classe_Custo' in df_temp.columns else "000000"
            df_temp['Desc_Conta'] = den + " - " + cod

            # 6. OTIMIZAÇÃO DE MEMÓRIA E TIPAGEM
            if 'Valor' in df_temp.columns:
                if df_temp['Valor'].dtype == object:
                    df_temp['Valor'] = df_temp['Valor'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df_temp['Valor'] = pd.to_numeric(df_temp['Valor'], errors='coerce').fillna(0).astype('float32')

            for col in ['Desc_Conta', 'Centro_Custo', 'VP', 'Localidade', 'P_L']:
                if col in df_temp.columns:
                    df_temp[col] = df_temp[col].fillna("Não Informado").astype('category')

            dfs.append(df_temp)
            gc.collect()

        except Exception as e: # --- FECHAMENTO DO TRY POR ARQUIVO ---
            return f"Erro no arquivo {f.name}: {str(e)}", None, None, None
    
    if not dfs: return "Nenhum dado processado.", None, None, None
    full_df = pd.concat(dfs, ignore_index=True)
    return get_yoy_data(full_df)

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
    """Relatório onde o Material é puramente informativo e os totais são preservados."""
    if not dims:
        st.warning("Nenhuma dimensão de análise (P&L, VP, etc.) foi encontrada nos arquivos.")
        return
    
    if profundidade >= len(dims):
        return

    meses_nomes = {1:'Jan', 2:'Fev', 3:'Mar', 4:'Abr', 5:'Mai', 6:'Jun',
                   7:'Jul', 8:'Ago', 9:'Set', 10:'Out', 11:'Nov', 12:'Dez'}

    col = dims[profundidade]
    
    # Filtra a base master conforme o nível atual
    df_nivel = df_master.copy()
    if filtro_contexto:
        for c, v in filtro_contexto.items():
            df_nivel = df_nivel.xs(v, level=c, drop_level=False)

    # --- 🟢 NÍVEL FINAL: MATERIAIS (APENAS OBSERVAÇÃO) ---
    if col == 'Desc_Material':
        st.markdown(f"#### 📦 Balanço Detalhado de Objetos")
        
        # Agrupamos por Mês e Material pegando TUDO do contexto atual
        df_mat_mes = df_nivel.groupby(['Mes', 'Desc_Material'])[[ano_ant, ano_at]].sum()
        
        # Filtramos os meses aqui também para o Material não bugar
        meses_disponiveis = sorted(df_mat_mes.index.get_level_values('Mes').unique())
        if selecao_meses:
            meses_disponiveis = [m for m in meses_disponiveis if m in selecao_meses]
        
        for m_num in meses_disponiveis:
            st.write(f"📅 **Referência: {meses_nomes.get(m_num)}**")
            df_exibir = df_mat_mes.xs(m_num, level='Mes').copy()
            df_exibir.index.name = "Objeto"
            df_exibir.columns = pd.MultiIndex.from_tuples([(str(ano_ant), "Valor"), (str(ano_at), "Valor")])
            
            t_at = df_exibir[(str(ano_at), "Valor")].sum()
            t_ant = df_exibir[(str(ano_ant), "Valor")].sum()
            df_total = pd.DataFrame([[format_brl(t_ant), format_brl(t_at)]], columns=df_exibir.columns, index=["Total Contexto"])
            st.table(pd.concat([df_exibir.map(format_brl), df_total]))
        return

    # --- 🔵 NÍVEIS DE GESTÃO (CONTA, LOCALIDADE, CC, ETC) ---
    itens = sorted(df_nivel.index.get_level_values(col).unique().astype(str).tolist())

    # No logic.py, dentro da render_report_ui
    for item in itens:
        df_item = df_nivel.xs(item, level=col, drop_level=False)
        
        # 1. Calculamos o Delta Mensal
        delta_mensal = df_item.groupby(level='Mes', observed=True)['Delta'].sum()
        
        if selecao_meses:
            selecao_ints = [int(m) for m in selecao_meses]
            delta_mensal = delta_mensal[delta_mensal.index.isin(selecao_ints)]
                    
        # 3. Total do período baseado APENAS nos meses filtrados
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
            label = f"{'📌' if profundidade == 0 else '➥'} {item} | Total Período: {format_brl(var_total)}"
            
            # Usamos uma chave simples para o expander (apenas item e profundidade)
            with st.expander(label, key=f"exp_{profundidade}_{item}"):
                st.write("**Variação Mensal YoY (Impacto no Resultado):**")
                
                if not delta_mensal.empty:
                    # O segredo do layout: st.columns recebe o tamanho exato do que sobrou no filtro
                    cols = st.columns(len(delta_mensal))
                    for idx, m_num in enumerate(delta_mensal.index):
                        with cols[idx]:
                            st.caption(meses_nomes.get(int(m_num), f"Mês {m_num}"))
                            st.write(format_brl(delta_mensal[m_num]))
                
                st.divider()
                novo_contexto = (filtro_contexto or {}).copy()
                novo_contexto[col] = item
                
                # RECURSÃO: Passamos o selecao_meses adiante
                render_report_ui(df_master, dims, ano_at, ano_ant, foco_res, profundidade + 1, novo_contexto, selecao_meses=selecao_meses)