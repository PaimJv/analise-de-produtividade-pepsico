import pandas as pd
import streamlit as st
import re
from utils import LABELS_MAP

def process_all_accounts_format(files):
    """Lê o arquivo matricial, detecta o mês de corte (PXXF) e derrete os meses em linhas."""
    dfs = []
    meses_cols = [' Janeiro ', 'Fevereiro ', ' Março ', ' Abril ', ' Maio ', ' Junho ', 
                  ' Julho ', ' Agosto ', ' Setembro ', ' Outubro ', ' Novembro ', ' Dezembro ']
    
    for f in files:
        if f.name.endswith('.csv'):
            # --- DETECÇÃO CEGA DE ENCODING ---
            sample_bytes = f.read(10000)
            f.seek(0)
            
            # Lista de encodings comuns (utf-16le ignora a exigência de BOM do SAP)
            encodings_teste = ['utf-8-sig', 'cp1252', 'latin-1', 'utf-16le']
            enc_final = 'utf-8-sig' # Padrão inicial
            
            for enc in encodings_teste:
                try:
                    sample_bytes.decode(enc)
                    enc_final = enc
                    break # Achou o correto, para de testar
                except UnicodeDecodeError:
                    continue
            
            f.seek(0)
            # engine='python' garante mais estabilidade com encodings exóticos
            df = pd.read_csv(f, sep=';', encoding=enc_final, engine='python')
        else:
            # Excel é resolvido nativamente pelo pandas
            df = pd.read_excel(f)
            
        # 1. Identificar o corte PXXF para separar Real (YTD) de Projeção (BOY)
        info_str = df['Informação'].iloc[0]
        match = re.search(r'P(\d{2})F', str(info_str))
        mes_corte = int(match.group(1)) if match else 13 
        
        # 2. Limpeza de valores e conversão de "-" para 0
        for mes in meses_cols:
            if mes in df.columns:
                df[mes] = df[mes].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df[mes] = pd.to_numeric(df[mes].replace(r'^\s*-\s*$', '0', regex=True), errors='coerce').fillna(0)

        # 3. Cálculo das fatias de tempo
        meses_reais_cols = meses_cols[:mes_corte-1]
        meses_proj_cols = meses_cols[mes_corte-1:]
        
        # BLINDAGEM: Filtramos para manter APENAS os meses que vieram no arquivo atual
        cols_ytd = [m for m in meses_reais_cols if m in df.columns]
        cols_boy = [m for m in meses_proj_cols if m in df.columns]
        
        df['Valor_YTD'] = df[cols_ytd].sum(axis=1)
        df['Valor_BOY'] = df[cols_boy].sum(axis=1)
        df['Valor_FY'] = df['Valor_YTD'] + df['Valor_BOY']

        # 4. Padronização das colunas para os filtros funcionarem
        mapeamento = {
            'Centro de Custo': 'Centro_Custo',
            'Descrição Centro de Custo': 'DenClsCst',
            'Conta Contábil': 'Classe_Custo',
            'Descrição Conta Contábil': 'DenConta',
            'Pacote': 'Pacote',
            'Informação': 'Tipo_Dado',
            'Localidade': 'Localidade',
            'VP': 'VP',
            'Linha P&L': 'P_L'
        }
        df.rename(columns=mapeamento, inplace=True)
        
        # Criação de Desc_Conta e Desc_Material (Blindagem de hierarquia)
        if 'DenConta' in df.columns and 'Classe_Custo' in df.columns:
            df['Desc_Conta'] = df['DenConta'].astype(str) + " - " + df['Classe_Custo'].astype(str)
        else:
            df['Desc_Conta'] = "Não Especificado"
            
        if 'Desc_Material' not in df.columns:
            df['Desc_Material'] = "Sem detalhamento de material"
            
        dfs.append(df)  
        
    return pd.concat(dfs, ignore_index=True)

def format_brl(val):
    """Formatação monetária."""
    prefix = "R$ "
    if val < 0:
        val_abs = abs(val)
        return f"{prefix}-{val_abs:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{prefix}{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def render_planejamento_ui(df_nivel, dims, profundidade=0, filtro_contexto=None):
    """Interface recursiva focada na comparação YTD / BOY / FY"""
    if not dims or profundidade >= len(dims):
        return

    col = dims[profundidade]
    
    # Filtra o contexto atual
    if filtro_contexto:
        for c, v in filtro_contexto.items():
            df_nivel = df_nivel[df_nivel[c] == v]

    itens = sorted(df_nivel[col].dropna().unique().astype(str).tolist())

    for item in itens:
        df_item = df_nivel[df_nivel[col] == item]
        
        # Separação dos dados pelos identificadores
        ytd_real = df_item[df_item['Tipo_Dado'].str.contains(r'P\d{2}F', na=False)]['Valor_YTD'].sum()
        ytd_aop = df_item[df_item['Tipo_Dado'] == 'AOP26']['Valor_YTD'].sum()
        ytd_2025 = df_item[df_item['Tipo_Dado'] == '2025']['Valor_YTD'].sum()
        
        boy_proj = df_item[df_item['Tipo_Dado'].str.contains(r'P\d{2}F', na=False)]['Valor_BOY'].sum()
        fy_total = df_item[df_item['Tipo_Dado'].str.contains(r'P\d{2}F', na=False)]['Valor_FY'].sum()

        label_dim = LABELS_MAP.get(col, col)
        label_pref = '📌' if profundidade == 0 else '➥'
        label_visual = f"{label_pref} {label_dim}: {item} | YTD Real: {format_brl(ytd_real)}"

        with st.expander(label_visual):
            # Visão 1: Análise de Produtividade YTD
            st.markdown("### 📊 Análise YTD (Meses Fechados)")
            c1, c2, c3 = st.columns(3)
            c1.metric("YTD Real", format_brl(ytd_real))
            c2.metric("Meta (AOP)", format_brl(ytd_aop), f"{format_brl(ytd_aop - ytd_real)} (Saldo)", delta_color="normal")
            c3.metric("Vs Ano Ant. (2025)", format_brl(ytd_2025), f"{format_brl(ytd_real - ytd_2025)} (Variação)", delta_color="inverse")
            
            st.divider()
            
            # Visão 2: Projeção e Ano Completo
            st.markdown("### 🔮 Projeção (BOY) e Ano Completo (FY)")
            c4, c5 = st.columns(2)
            c4.metric("Projeção (BOY)", format_brl(boy_proj))
            c5.metric("Estimativa Ano (FY)", format_brl(fy_total))

            # Recursão para o próximo nível
            novo_contexto = (filtro_contexto or {}).copy()
            novo_contexto[col] = item
            render_planejamento_ui(df_nivel, dims, profundidade + 1, novo_contexto)