import pandas as pd
import streamlit as st

# --- MAPEAMENTO DE COLUNAS ---
    # AJUSTE A ESQUERDA conforme os nomes exatos no seu arquivo CSV
mapeamento = {
        'Dt.lçto.': 'Data_Lancamento', 
        'LINHA P&L': 'P_L',
        'VP': 'VP',
        'LOCALIDADE': 'Localidade',
        'Centro cst': 'Centro_Custo',
        'DenClsCst': 'DenClsCst',        
        'Cl.custo': 'Classe_Custo', 
        'Texto breve material': 'Desc_Material',
        'Valor/moeda objeto': 'Valor',
        'DIRETORIA': 'Diretoria'
}

def clean_data(df):
    """
    Realiza a limpeza e padronização utilizando o mapeamento global.    
    """
    # 1. Limpeza preventiva: remove espaços em branco invisíveis nos nomes das colunas
    df.columns = df.columns.str.strip()
     
    # Renomeia as colunas baseadas no dicionário acima
    df = df.rename(columns=mapeamento)

    # --- DIAGNÓSTICO DE ERRO ---
    # Se o erro 'Data_Lancamento' persistir, este bloco mostrará o culpado
    if 'Data_Lancamento' not in df.columns:
        st.error("🚨 Erro de Mapeamento: Coluna de Data não encontrada!")
        st.write("O Python detetou estas colunas no seu arquivo:", df.columns.tolist())
        st.info("DICA: Verifique se o nome no CSV é exatamente igual ao que está no dicionário 'mapeamento' acima.")
        st.stop()

    # --- 2. TRATAMENTO DE DATAS ---
    df['Data_Lancamento'] = pd.to_datetime(df['Data_Lancamento'], dayfirst=True, errors='coerce')
    # Remove linhas onde a data não pôde ser convertida
    df = df.dropna(subset=['Data_Lancamento'])
    
    # Criação de colunas auxiliares para agrupamento
    df['Ano'] = df['Data_Lancamento'].dt.year
    df['Mes'] = df['Data_Lancamento'].dt.month
    
    # --- 3. TRATAMENTO DE VALORES NUMÉRICOS ---
    # Converte '1.234,56' (String) para 1234.56 (Float)
    if df['Valor'].dtype == object:
        df['Valor'] = (
            df['Valor']
            .astype(str)
            .str.replace('.', '', regex=False)
            .str.replace(',', '.', regex=False)
        )
    df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0)
    
    # --- 4. TAXONOMIA OFICIAL (Concatenação) ---
    # Regra: "Descrição da Conta - Código"
    df['DenClsCst'] = df['DenClsCst'].fillna('Sem Descrição')
    df['Classe_Custo'] = df['Classe_Custo'].fillna('000000')
    
    df['Desc_Conta'] = df['DenClsCst'].astype(str) + " - " + df['Classe_Custo'].astype(str)
    
    return df

def get_yoy_data(df, apenas_completos=True):
    """
    Filtra a base para permitir uma comparação Year-over-Year (YoY) justa.
    """
    if df.empty:
        return pd.DataFrame(), 0, 0
        
    # Identifica os dois anos mais recentes
    anos = sorted(df['Ano'].unique(), reverse=True)
    if len(anos) < 2:
        return pd.DataFrame(), 0, 0
        
    ano_at, ano_ant = anos[0], anos[1]
    
    # Lógica de meses equivalentes
    if apenas_completos:
        # Pega o último mês com dados no ano atual e subtrai 1 (mês fechado)
        mes_max_atual = df[df['Ano'] == ano_at]['Mes'].max()
        mes_limite = mes_max_atual - 1
        
        # Garante que o limite seja pelo menos Janeiro
        if mes_limite <= 0:
            mes_limite = 1
    else:
        # Considera todos os meses disponíveis, incluindo o atual incompleto
        mes_limite = df[df['Ano'] == ano_at]['Mes'].max()
        
    # Filtra para que ambos os anos tenham o mesmo range de meses (comparação maçã com maçã)
    df_filtered = df[df['Mes'] <= mes_limite]
    
    # Retorna apenas os dados dos dois anos de interesse
    df_final = df_filtered[df_filtered['Ano'].isin([ano_at, ano_ant])]
    
    return df_final, ano_at, ano_ant