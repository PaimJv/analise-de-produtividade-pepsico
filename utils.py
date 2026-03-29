import pandas as pd
import streamlit as st
import calendar

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

def get_yoy_data(df):
    if df.empty or 'Ano' not in df.columns:
        return pd.DataFrame(), 0, 0, None
        
    anos = sorted(df['Ano'].unique(), reverse=True)
    if len(anos) < 2:
        return pd.DataFrame(), 0, 0, None
        
    ano_at, ano_ant = anos[0], anos[1]
    
    # 1. IDENTIFICAÇÃO DO PERÍODO DE CORTE
    # Descobrimos qual o último mês com dados no ano ATUAL (ex: Março/2026)
    data_max_atual = df[df['Ano'] == ano_at]['Data_Lancamento'].max()
    mes_max = data_max_atual.month
    dia_max = data_max_atual.day
    
    # 2. ALINHAMENTO (O que faltou antes)
    # Filtramos o DataFrame para que AMBOS os anos (2025 e 2026) 
    # só mostrem meses até o 'mes_max' (ex: Jan a Mar)
    df_filtered = df[df['Mes'] <= mes_max].copy()
    
    # 3. VERIFICAÇÃO DE INTEGRIDADE (Aviso de mês incompleto)
    ultimo_dia_real = calendar.monthrange(ano_at, mes_max)[1]
    
    aviso_incompleto = None
    if dia_max < ultimo_dia_real:
        meses_nomes = {1:'Janeiro', 2:'Fevereiro', 3:'Março', 4:'Abril', 5:'Maio', 6:'Junho',
                       7:'Julho', 8:'Agosto', 9:'Setembro', 10:'Outubro', 11:'Novembro', 12:'Dezembro'}
        aviso_incompleto = {
            'mes_nome': meses_nomes.get(mes_max),
            'dia': dia_max
        }

    # Retorna apenas os dados dos dois anos dentro do range de meses alinhado
    df_final = df_filtered[df_filtered['Ano'].isin([ano_at, ano_ant])]
    
    return df_final, ano_at, ano_ant, aviso_incompleto