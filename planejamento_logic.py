import pandas as pd
import streamlit as st
import re
import os
import json
from utils import LABELS_MAP

def process_all_accounts_format(files):
    """Lê o arquivo matricial, detecta o cabeçalho e mapeia colunas (Dimensões + Financeiras)."""
    dfs = []
    
    # Nomes padronizados (sem espaços para segurança)
    meses_cols = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    agregadores_cols = ['YTD', 'BOY', 'FY']
    
    for f in files:
        if f.name.endswith('.csv'):
            sample_bytes = f.read(10000)
            f.seek(0)
            
            encodings_teste = ['utf-8-sig', 'cp1252', 'latin-1', 'utf-16le']
            enc_final = 'utf-8-sig'
            
            for enc in encodings_teste:
                try:
                    sample_bytes.decode(enc)
                    enc_final = enc
                    break 
                except UnicodeDecodeError:
                    continue
            
            f.seek(0)
            df_bruto = pd.read_csv(f, sep=';', encoding=enc_final, engine='python', header=None)
        else:
            df_bruto = pd.read_excel(f, header=None)
            
        # =========================================================
        # DETETIVE DE CABEÇALHO (SCORE POR PALAVRAS-CHAVE)
        # =========================================================
        # Muito mais seguro que buscar células vazias (ignora sujeira do SAP)
        palavras_chave = ['janeiro', 'centro de custo', 'pacote', 'informação', 'ytd', 'fy', 'conta']
        
        linha_0_str = " ".join([str(x).lower() for x in df_bruto.iloc[0].tolist()])
        linha_1_str = " ".join([str(x).lower() for x in df_bruto.iloc[1].tolist()]) if len(df_bruto) > 1 else ""
        
        score_0 = sum(1 for p in palavras_chave if p in linha_0_str)
        score_1 = sum(1 for p in palavras_chave if p in linha_1_str)
        
        # A linha que tiver mais palavras corporativas será eleita o cabeçalho
        if score_1 > score_0:
            df_bruto.columns = df_bruto.iloc[1].astype(str).str.strip()
            df = df_bruto.iloc[2:].reset_index(drop=True)
        else:
            df_bruto.columns = df_bruto.iloc[0].astype(str).str.strip()
            df = df_bruto.iloc[1:].reset_index(drop=True)
            
        df = df.loc[:, ~df.columns.str.contains('^nan|unnamed', case=False, na=False)]

        # =========================================================
        # 1. MAPEAMENTO INTELIGENTE (JSON + Estático)
        # =========================================================
        map_estatico = {
            'centro de custo': 'Centro_Custo',
            'descrição centro de custo': 'DenClsCst',
            'conta contábil': 'Classe_Custo',
            'descrição conta contábil': 'DenConta',
            'pacote': 'Pacote',
            'informação': 'Tipo_Dado',
            'localidade': 'Localidade',
            'vp': 'VP',
            'linha p&l': 'P_L'
        }
        
        for col_ref in meses_cols + agregadores_cols:
            map_estatico[col_ref.lower()] = col_ref
            
        colunas_reais = df.columns.tolist()
        col_map_arquivo = {str(c).strip().lower(): c for c in colunas_reais}
        
        tradução_final = {}
        colunas_sistema = list(set(map_estatico.values()))
        
        # A) Busca Estática
        for k_limpo, v_sistema in map_estatico.items():
            if k_limpo in col_map_arquivo:
                nome_original = col_map_arquivo[k_limpo]
                tradução_final[nome_original] = v_sistema
                
        # B) Busca JSON
        faltantes = [c for c in colunas_sistema if c not in tradução_final.values()]
        
        if faltantes and os.path.exists('referencia_colunas.json'):
            with open('referencia_colunas.json', 'r', encoding='utf-8') as ref_file:
                ref_data = json.load(ref_file)
            
            colunas_ignotas = [c for c in colunas_reais if c not in tradução_final.keys()]
            for col_arq in colunas_ignotas:
                nome_col_arq_limpo = str(col_arq).strip().lower()
                for nome_sistema_ref, exemplos_ref in ref_data.items():
                    if nome_sistema_ref in faltantes:
                        sinonimos = [str(e).strip().lower() for e in exemplos_ref]
                        if nome_col_arq_limpo in sinonimos:
                            tradução_final[col_arq] = nome_sistema_ref
                            faltantes.remove(nome_sistema_ref)
                            break
                            
        df.rename(columns=tradução_final, inplace=True)

        # =========================================================
        # 2. IDENTIFICAR O CORTE PXXF
        # =========================================================
        mes_corte = 13 
        if 'Tipo_Dado' in df.columns:
            info_str = str(df['Tipo_Dado'].iloc[0])
            match = re.search(r'P(\d{2})F', info_str)
            mes_corte = int(match.group(1)) if match else 13 
        
        # =========================================================
        # 3. LIMPEZA DE VALORES (BLINDADA CONTRA MÁSCARAS)
        # =========================================================
        for col in meses_cols + agregadores_cols:
            if col in df.columns:
                s = df[col].astype(str)
                s = s.str.replace(r'^\s*-\s*$', '0', regex=True) # Transforma " - " em "0"
                s = s.str.replace('.', '', regex=False)          # Remove ponto de milhar
                s = s.str.replace(',', '.', regex=False)          # Troca vírgula por ponto decimal
                df[col] = pd.to_numeric(s, errors='coerce').fillna(0)

        # =========================================================
        # 4. CAPTURA DAS FATIAS DE TEMPO (YTD / BOY / FY)
        # =========================================================
        meses_reais_cols = meses_cols[:mes_corte-1]
        meses_proj_cols = meses_cols[mes_corte-1:]
        
        cols_ytd = [m for m in meses_reais_cols if m in df.columns]
        cols_boy = [m for m in meses_proj_cols if m in df.columns]
        
        # Prioriza a captura dos valores DITOS na planilha. Se a coluna não existir, o código calcula sozinho.
        if 'YTD' in df.columns:
            df['Valor_YTD'] = df['YTD']
        else:
            df['Valor_YTD'] = df[cols_ytd].sum(axis=1)
            
        if 'BOY' in df.columns:
            df['Valor_BOY'] = df['BOY']
        else:
            df['Valor_BOY'] = df[cols_boy].sum(axis=1)
            
        if 'FY' in df.columns:
            df['Valor_FY'] = df['FY']
        else:
            df['Valor_FY'] = df['Valor_YTD'] + df['Valor_BOY']

        # =========================================================
        # 5. BLINDAGEM DE HIERARQUIA
        # =========================================================
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
    """Interface recursiva focada na comparação YTD / BOY / FY (Alta Performance)"""
    if not dims or profundidade >= len(dims):
        return

    col = dims[profundidade]
    
    # Filtra o contexto atual para este nível da recursão
    if filtro_contexto:
        for c, v in filtro_contexto.items():
            df_nivel = df_nivel[df_nivel[c] == v]

    itens = sorted(df_nivel[col].dropna().unique().astype(str).tolist())
    foco_analise = st.session_state.get('radio_foco_ia', 'Análise 360° (Ambos)')
    itens_exibidos = 0

    # =======================================================
    # 🚀 OTIMIZAÇÃO 1: FUNÇÕES NA MEMÓRIA GLOBAL (Fora do laço)
    # =======================================================
    def config_delta(var):
        if round(var, 2) > 0:
            val_str = f"{var:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return f"+ R$ {val_str} (Variação)", "inverse"
        elif round(var, 2) < 0:
            val_str = f"{abs(var):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return f"- R$ {val_str} (Variação)", "inverse"
        else:
            return "0", "off"

    def pintar_variacao(row):
        estilos = []
        is_variacao = 'Variação' in str(row.name)
        for val in row:
            if is_variacao and isinstance(val, (int, float)):
                if val > 0:
                    estilos.append('color: #d32f2f; font-weight: bold;')
                elif val < 0:
                    estilos.append('color: #2e7d32; font-weight: bold;')
                else:
                    estilos.append('')
            else:
                estilos.append('')
        return estilos

    # =======================================================
    # 🚀 OTIMIZAÇÃO 2: DESCOBRIR MÊS DE CORTE UMA SÓ VEZ
    # =======================================================
    meses_cols = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    cols_existentes = [m for m in meses_cols if m in df_nivel.columns]
    
    mes_corte = 13
    import re
    # Em vez de ler cada linha, lê só as categorias únicas (Super rápido)
    tipos_unicos = df_nivel['Tipo_Dado'].dropna().astype(str).unique()
    for tipo in tipos_unicos:
        match = re.search(r'P(\d{2})F', tipo)
        if match:
            mes_corte = int(match.group(1))
            break
            
    meses_fechados = cols_existentes[:mes_corte-1]
    meses_proj = cols_existentes[mes_corte-1:]

    # =======================================================
    # 🚀 OTIMIZAÇÃO 3: MÁSCARAS BOOLEANAS PRÉ-CALCULADAS
    # =======================================================
    mask_pxxf = df_nivel['Tipo_Dado'].astype(str).str.contains(r'P\d{2}F', na=False)
    mask_aop = df_nivel['Tipo_Dado'] == 'AOP26'
    mask_2025 = df_nivel['Tipo_Dado'] == '2025'

    # --- INÍCIO DO LAÇO DE RENDERIZAÇÃO ---
    for item in itens:
        # Fatiamento ultra-rápido por interseção lógica
        mask_item = (df_nivel[col] == item)
        
        df_pxxf = df_nivel[mask_item & mask_pxxf]
        df_aop = df_nivel[mask_item & mask_aop]
        df_2025 = df_nivel[mask_item & mask_2025]
        
        ytd_real = df_pxxf['Valor_YTD'].sum()
        ytd_aop = df_aop['Valor_YTD'].sum()
        ytd_2025 = df_2025['Valor_YTD'].sum()
        
        boy_proj = df_pxxf['Valor_BOY'].sum()
        boy_2025 = df_2025['Valor_BOY'].sum()
        
        fy_total = df_pxxf['Valor_FY'].sum()
        fy_2025 = df_2025['Valor_FY'].sum()
        
        # MOTOR DE FILTRO (FOCO DA ANÁLISE)
        var_2025 = ytd_real - ytd_2025
        
        if foco_analise == "Apenas Savings (Eficiência)" and round(var_2025, 2) > 0:
            continue
        elif foco_analise == "Apenas Desvios (Gastos)" and round(var_2025, 2) <= 0:
            continue
            
        itens_exibidos += 1

        label_dim = LABELS_MAP.get(col, col)
        label_pref = '📌' if profundidade == 0 else '➥'
        label_visual = f"{label_pref} {item} | YTD Real: {format_brl(ytd_real)} | Variação: {format_brl(var_2025)}".replace("$", "\$")

        with st.expander(label_visual):
            # Visão 1
            st.markdown("#### Análise YTD (Meses Fechados)")
            c1, c2, c3 = st.columns(3)
            c1.metric("YTD Real", format_brl(ytd_real))
            c2.metric("Meta (AOP)", format_brl(ytd_aop), *config_delta(ytd_real - ytd_aop))
            c3.metric("Vs Ano Ant. (2025)", format_brl(ytd_2025), *config_delta(var_2025))
            
            # if meses_fechados:
            #     st.write("") 
            #     # 🚀 OTIMIZAÇÃO 4: Montagem da tabela reaproveitando o corte
            #     df_tabela_ytd = pd.DataFrame({
            #         'Real': df_pxxf[meses_fechados].sum(),
            #         'Meta (AOP)': df_aop[meses_fechados].sum(),
            #         'Ano Ant. (2025)': df_2025[meses_fechados].sum()
            #     }).T 
                
            #     df_tabela_ytd.loc['Variação (Real - 2025)'] = df_tabela_ytd.loc['Real'] - df_tabela_ytd.loc['Ano Ant. (2025)']
            #     df_tabela_ytd['Total YTD'] = df_tabela_ytd.sum(axis=1)
                
            #     st.dataframe(
            #         df_tabela_ytd.style
            #         .format(precision=2, decimal=',', thousands='.')
            #         .apply(pintar_variacao, axis=1), 
            #         use_container_width=True
            #     )
            
            st.divider()
            
            # Visão 2
            st.markdown("#### Projeção Resto do Ano (BOY)")
            c4, c5 = st.columns(2)
            c4.metric("BOY Projetado", format_brl(boy_proj))
            c5.metric("BOY Ano Ant. (2025)", format_brl(boy_2025), *config_delta(boy_proj - boy_2025))

            # if meses_proj:
            #     st.write("")
            #     # 🚀 OTIMIZAÇÃO 4: Montagem da tabela reaproveitando o corte
            #     df_tabela_boy = pd.DataFrame({
            #         'Projetado': df_pxxf[meses_proj].sum(),
            #         'Meta (AOP)': df_aop[meses_proj].sum(),
            #         'Ano Ant. (2025)': df_2025[meses_proj].sum()
            #     }).T 
                
            #     df_tabela_boy.loc['Variação (Proj. - 2025)'] = df_tabela_boy.loc['Projetado'] - df_tabela_boy.loc['Ano Ant. (2025)']
            #     df_tabela_boy['Total BOY'] = df_tabela_boy.sum(axis=1)
                
            #     st.dataframe(
            #         df_tabela_boy.style
            #         .format(precision=2, decimal=',', thousands='.')
            #         .apply(pintar_variacao, axis=1), 
            #         use_container_width=True
            #     )

            st.divider()

            # Visão 3
            st.markdown("#### Ano Completo (FY)")
            c6, c7 = st.columns(2)
            c6.metric("FY Estimado (YTD + BOY)", format_brl(fy_total))
            c7.metric("FY Ano Ant. (2025)", format_brl(fy_2025), *config_delta(fy_total - fy_2025))

            # Recursão para o próximo nível
            novo_contexto = (filtro_contexto or {}).copy()
            novo_contexto[col] = item
            render_planejamento_ui(df_nivel, dims, profundidade + 1, novo_contexto)

    # FEEDBACK VISUAL DE TELA VAZIA
    if profundidade == 0 and itens_exibidos == 0:
        st.info(f"Nenhum registro encontrado com o critério: **{foco_analise}**")