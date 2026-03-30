import streamlit as st
import pandas as pd
import gc # Garbage Collector
from utils import mapeamento, get_yoy_data

def init_state():
    """Inicializa as variáveis de estado da sessão de forma única."""
    if 'drill_path' not in st.session_state:
        st.session_state.drill_path = []
    if 'aviso_incompleto' not in st.session_state:
        st.session_state.aviso_incompleto = None

@st.cache_data(show_spinner="Otimizando base de dados...")
def load_and_process_base(files):
    dfs = []
    from utils import mapeamento
    import csv
    
    for f in files:
        try:
            # 1. IDENTIFICAÇÃO DE ENCODING (utf-8-sig mata o erro do ï»¿)
            if f.name.endswith('.csv'):
                encoding_tentativa = 'utf-8-sig' 
                try:
                    df_header = pd.read_csv(f, sep=None, engine='python', encoding=encoding_tentativa, nrows=2)
                except:
                    encoding_tentativa = 'latin-1'
                    f.seek(0)
                    df_header = pd.read_csv(f, sep=None, engine='python', encoding=encoding_tentativa, nrows=2)

            else:
                # LEITURA OTIMIZADA EXCEL (Calamine)
                df_header = pd.read_excel(f, engine='calamine', nrows=2)
                # f.seek(0)
                # df_temp = pd.read_excel(f, engine='calamine')

            # 2. MAPEAMENTO FLEXÍVEL
            colunas_reais = df_header.columns.tolist()
            col_map_arquivo = {c.strip().lower(): c for c in colunas_reais}
            map_limpo = {k.strip().lower(): v for k, v in mapeamento.items()}
            
            tradução_final = {}
            colunas_para_ler = []
            
            for k_limpo, v_sistema in map_limpo.items():
                if k_limpo in col_map_arquivo:
                    nome_original = col_map_arquivo[k_limpo]
                    tradução_final[nome_original] = v_sistema
                    colunas_para_ler.append(nome_original)
            
            # 3. LEITURA COMPLETA OTIMIZADA
            if f.name.endswith('.csv'):
                f.seek(0)
                # Melhoria no Sniffer: tentamos detectar, se falhar, usamos o padrão ';' (comum no SAP)
                try:
                    sample = f.read(4096).decode(encoding_tentativa)
                    dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
                    sep_detectado = dialect.delimiter
                except:
                    sep_detectado = ';' 
                
                f.seek(0)
                df_temp = pd.read_csv(
                    f, 
                    usecols=colunas_para_ler, 
                    sep=sep_detectado, 
                    engine='c', 
                    encoding=encoding_tentativa, 
                    low_memory=False
                )
            else:
                f.seek(0)
                df_temp = pd.read_excel(f, usecols=colunas_para_ler, engine='calamine')

            # Renomeia as colunas para o padrão do sistema
            df_temp.rename(columns=tradução_final, inplace=True)

            # 4. CRIAÇÃO DE ANO E MES (Essencial para o YoY)
            if 'Data_Lancamento' in df_temp.columns:
                df_temp['Data_Lancamento'] = pd.to_datetime(df_temp['Data_Lancamento'], dayfirst=True, errors='coerce')
                df_temp = df_temp.dropna(subset=['Data_Lancamento'])
                df_temp['Ano'] = df_temp['Data_Lancamento'].dt.year.astype(int)
                df_temp['Mes'] = df_temp['Data_Lancamento'].dt.month.astype(int)

            # --- 5. CRIAÇÃO DA DESC_CONTA (O que estava faltando!) ---
            # Unimos a Denominação ao Código da Classe de Custo
            # Usamos fillna para evitar que o "NaN" quebre a concatenação de strings
            den = df_temp['DenClsCst'].fillna("Sem Descrição").astype(str) if 'DenClsCst' in df_temp.columns else "Sem Descrição"
            cod = df_temp['Classe_Custo'].fillna("000000").astype(str) if 'Classe_Custo' in df_temp.columns else "000000"
            df_temp['Desc_Conta'] = den + " - " + cod

            # 6. OTIMIZAÇÃO DE MEMÓRIA
            if 'Valor' in df_temp.columns:
                if df_temp['Valor'].dtype == object:
                    df_temp['Valor'] = df_temp['Valor'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df_temp['Valor'] = pd.to_numeric(df_temp['Valor'], errors='coerce').fillna(0).astype('float32')

            cat_cols = ['Desc_Conta', 'Centro_Custo', 'VP', 'Localidade', 'P_L']
            for col in cat_cols:
                if col in df_temp.columns:
                    df_temp[col] = df_temp[col].fillna("Não Informado").astype('category')

            dfs.append(df_temp)
            gc.collect()

        except Exception as e:
            return f"Erro no arquivo {f.name}: {str(e)}", None, None, None

    if not dfs: return "Nenhum dado processado.", None, None, None
    
    full_df = pd.concat(dfs, ignore_index=True)
    
    from utils import get_yoy_data
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
    
    # FORÇAMOS o Mês a ser um inteiro puro para matar a memória do tipo 'category'
    if 'Mes' in df_clean.columns:
        df_clean['Mes'] = df_clean['Mes'].astype(int)
    
    todas_cols = ['Desc_Conta', 'P_L', 'VP', 'Localidade', 'Centro_Custo', 'Desc_Material']
    
    # AJUSTE AQUI: Convertemos para string ANTES de preencher o vazio
    for c in todas_cols:
        if c in df_clean.columns:
            # Ao converter para str, os NaNs viram a string 'nan'
            df_clean[c] = df_clean[c].astype(str).replace(['nan', 'None', '<NA>'], "Não Informado")
    
    # O restante da função permanece igual
    agrupado = (
        df_clean.groupby(dims + ['Mes', 'Ano'], observed=True)['Valor']
        .sum()
        .unstack(level='Ano')
        .fillna(0)
    )
    
    for a in [ano_at, ano_ant]:
        if a not in agrupado.columns: agrupado[a] = 0
    
    agrupado['Delta'] = agrupado[ano_at] - agrupado[ano_ant]
    return agrupado

def render_report_ui(df_master, dims, ano_at, ano_ant, foco_res, profundidade=0, filtro_contexto=None, selecao_meses=None):
    """Relatório onde o Material é puramente informativo e os totais são preservados."""
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