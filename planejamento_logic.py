import pandas as pd
import streamlit as st
import re
import os
import json
from utils import LABELS_MAP

def process_all_accounts_format(files):
    """Lê o arquivo matricial, detecta o cabeçalho e mapeia colunas (Dimensões + Financeiras)."""
    dfs = []
    import io
    
    meses_cols = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    agregadores_cols = ['YTD', 'BOY', 'FY']
    
    for f in files:
        # 🚀 ESCUDO DE MEMÓRIA PARA O MODO PLANEJAMENTO TAMBÉM
        file_buffer = io.BytesIO(f.read())
        
        if f.name.endswith('.csv'):
            sample_bytes = file_buffer.read(10000)
            file_buffer.seek(0)
            
            encodings_teste = ['utf-8-sig', 'cp1252', 'latin-1', 'utf-16le']
            enc_final = 'utf-8-sig'
            
            for enc in encodings_teste:
                try:
                    sample_bytes.decode(enc)
                    enc_final = enc
                    break 
                except UnicodeDecodeError:
                    continue
            
            file_buffer.seek(0)
            df_bruto = pd.read_csv(file_buffer, sep=';', encoding=enc_final, engine='python', header=None)
        else:
            df_bruto = pd.read_excel(file_buffer, engine='openpyxl', header=None)
            
        # =========================================================
        # DETETIVE DE CABEÇALHO (SCORE POR PALAVRAS-CHAVE)
        # =========================================================
        palavras_chave = ['janeiro', 'centro de custo', 'pacote', 'informação', 'ytd', 'fy', 'conta']
        
        linha_0_str = " ".join([str(x).lower() for x in df_bruto.iloc[0].tolist()])
        linha_1_str = " ".join([str(x).lower() for x in df_bruto.iloc[1].tolist()]) if len(df_bruto) > 1 else ""
        
        score_0 = sum(1 for p in palavras_chave if p in linha_0_str)
        score_1 = sum(1 for p in palavras_chave if p in linha_1_str)
        
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
        
        for k_limpo, v_sistema in map_estatico.items():
            if k_limpo in col_map_arquivo:
                nome_original = col_map_arquivo[k_limpo]
                tradução_final[nome_original] = v_sistema
                
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
                s = s.str.replace(r'^\s*-\s*$', '0', regex=True)
                s = s.str.replace('.', '', regex=False)
                s = s.str.replace(',', '.', regex=False)
                df[col] = pd.to_numeric(s, errors='coerce').fillna(0)

        # =========================================================
        # 4. CAPTURA DAS FATIAS DE TEMPO (YTD / BOY / FY)
        # =========================================================
        meses_reais_cols = meses_cols[:mes_corte-1]
        meses_proj_cols = meses_cols[mes_corte-1:]
        
        cols_ytd = [m for m in meses_reais_cols if m in df.columns]
        cols_boy = [m for m in meses_proj_cols if m in df.columns]
        
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
        # 5. BLINDAGEM DE HIERARQUIA E REMOÇÃO DE LIXO SAP
        # =========================================================
        if 'Classe_Custo' in df.columns:
            df['Classe_Custo'] = df['Classe_Custo'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            codigos = df['Classe_Custo'].str.extract(r'(\d+)\s*$')[0]
            mask_ok = (codigos.str.len() == 7) & (codigos != '1111111')
            df = df[mask_ok]

        if 'DenConta' in df.columns and 'Classe_Custo' in df.columns:
            den_conta_limpa = df['DenConta'].astype(str).str.replace('\n', ' ', regex=False).str.replace('\r', '', regex=False)
            df['Desc_Conta'] = den_conta_limpa + " - " + df['Classe_Custo']
        else:
            df['Desc_Conta'] = "Não Especificado"
            
        if 'Desc_Material' not in df.columns:
            df['Desc_Material'] = "Sem detalhamento de material"
            
        dfs.append(df)  
        
    df_final = pd.concat(dfs, ignore_index=True)
    
    colunas_texto = ['Centro_Custo', 'DenClsCst', 'Classe_Custo', 'DenConta', 
                     'Pacote', 'Tipo_Dado', 'Localidade', 'VP', 'P_L', 
                     'Desc_Conta', 'Desc_Material']
    
    for col in colunas_texto:
        if col in df_final.columns:
            df_final[col] = df_final[col].astype('category')
            
    for col in meses_cols + agregadores_cols + ['Valor_YTD', 'Valor_BOY', 'Valor_FY']:
        if col in df_final.columns:
            df_final[col] = pd.to_numeric(df_final[col], downcast='float')
            
    return df_final

def format_brl(val):
    """Formatação monetária."""
    prefix = "R$ "
    if val < 0:
        val_abs = abs(val)
        return f"{prefix}-{val_abs:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{prefix}{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def render_planejamento_ui(df_nivel, dims, profundidade=0, filtro_contexto=None):
    """Função de renderização otimizada com Pré-cálculo e Batching."""
    foco_analise = st.session_state.get('radio_foco_ia', 'Análise 360° (Ambos)')
    
    msg_topo = st.empty()
    aviso_texto = st.empty()
    barra_progresso = st.progress(0)
    
    with st.spinner("Otimizando tabelas e renderizando visão executiva..."):
        # 🚀 PASSO 1: Pré-calcular todos os agrupamentos necessários para as dimensões selecionadas
        # Isso evita que o Python filtre o DataFrame repetidamente dentro dos loops.
        with st.expander("Detalhamento do processamento", expanded=False):
            st.write("Agrupando dimensões...")
            
        # Criamos um dicionário de busca rápida (Lookup Table)
        # Agrupamos por todas as dimensões de uma vez para acesso instantâneo
        lookup_df = df_nivel.groupby(dims + ['Tipo_Dado'], observed=True, as_index=False)[
            ['Valor_YTD', 'Valor_BOY', 'Valor_FY']
        ].sum()
        
        # 🚀 PASSO 2: Motor de renderização em lotes
        teve_dados = _gerar_html_alta_performance(
            lookup_df, dims, 0, {}, foco_analise, aviso_texto, barra_progresso
        )
        
    aviso_texto.empty()
    barra_progresso.empty()
    
    if not teve_dados:
        msg_topo.info(f"Nenhum registro encontrado para: **{foco_analise}**")
    else:
        msg_topo.success("✅ Relatório gerado com sucesso!")


def _gerar_html_alta_performance(df_lookup, dims, profundidade, filtro_contexto, foco_analise, text_ui=None, progress_ui=None):
    """Motor que utiliza tabelas de busca para renderização instantânea."""
    if not dims or profundidade >= len(dims):
        return ""

    col = dims[profundidade]
    
    # Aplica os filtros acumulados no dataframe de lookup
    df_temp = df_lookup.copy()
    if filtro_contexto:
        for c, v in filtro_contexto.items():
            df_temp = df_temp[df_temp[c].astype(str) == str(v)]

    itens = sorted(df_temp[col].unique().astype(str).tolist())
    total_itens = len(itens)
    
    # Limite de segurança visual
    if total_itens > 150 and profundidade == 0:
        st.warning(f"⚠️ Volume alto detectado ({total_itens} itens). O relatório será renderizado em blocos.")

    encontrou_dados = False
    batch_html = []
    
    for idx, item in enumerate(itens):
        if profundidade == 0 and text_ui is not None and progress_ui is not None:
            porcentagem = int(((idx + 1) / total_itens) * 100)
            text_ui.info(f"🚀 Renderizando {idx + 1}/{total_itens}: **{item}**")
            progress_ui.progress(porcentagem)

        # Filtra o lookup apenas para o item atual
        df_item = df_temp[df_temp[col].astype(str) == item]
        
        # Cálculos de valores usando o Tipo_Dado pré-agrupado
        def get_sum(mask_type, col_val):
            return df_item[df_item['Tipo_Dado'].astype(str).str.contains(mask_type, na=False)][col_val].sum()

        ytd_real = get_sum(r'P\d{2}F', 'Valor_YTD')
        ytd_aop  = get_sum('AOP26', 'Valor_YTD')
        ytd_2025 = get_sum('2025', 'Valor_YTD')
        
        boy_proj = get_sum(r'P\d{2}F', 'Valor_BOY')
        boy_2025 = get_sum('2025', 'Valor_BOY')
        
        fy_total = get_sum(r'P\d{2}F', 'Valor_FY')
        fy_2025  = get_sum('2025', 'Valor_FY')
        
        var_2025 = ytd_real - ytd_2025
        
        if foco_analise == "Apenas Savings (Eficiência)" and var_2025 > 0: continue
        if foco_analise == "Apenas Desvios (Gastos)" and var_2025 <= 0: continue

        encontrou_dados = True
        cor_var = '#d32f2f' if var_2025 > 0 else '#2e7d32' if var_2025 < 0 else '#666'
        sinal_var = '+' if var_2025 > 0 else ''
        label_pref = '📌' if profundidade == 0 else '➥'
        
        # Sub-renderização (Recursiva)
        novo_contexto = (filtro_contexto or {}).copy()
        novo_contexto[col] = item
        html_filhos = _gerar_html_alta_performance(df_temp, dims, profundidade + 1, novo_contexto, foco_analise)

        # 🚀 HTML resumido colado em UMA LINHA (Evita a quebra das caixas do Streamlit)
        html_item = (
            f"<details style='margin-bottom: 8px; border: 1px solid #d1d5db; border-radius: 8px; background-color: #ffffff;'>"
            f"<summary style='padding: 12px; font-weight: bold; cursor: pointer; font-family: sans-serif; font-size: 14px;'>"
            f"{label_pref} {item} <span style='font-weight: normal; color: #555; margin-left: 10px;'>"
            f"| YTD: {format_brl(ytd_real)} | Var: <span style='color: {cor_var};'>{sinal_var}{format_brl(var_2025)}</span></span>"
            f"</summary>"
            f"<div style='padding: 15px; border-top: 1px solid #eee;'>"
            
            # ÚNICO CONTAINER FLEX PARA TODOS OS CARDS (O segredo para não quebrar o HTML)
            f"<div style='display: flex; gap: 10px; flex-wrap: wrap;'>"
            
            # --- CARDS YTD ---
            f"{_get_card_mini('YTD Real', ytd_real)}"
            f"{_get_card_mini('Meta AOP (YTD)', ytd_aop, var_valor=ytd_real - ytd_aop)}"
            f"{_get_card_mini('Real 2025 (YTD)', ytd_2025, var_valor=var_2025)}"
            
            # --- CARDS BOY ---
            f"{_get_card_mini('BOY Projetado', boy_proj)}"
            f"{_get_card_mini('BOY 2025', boy_2025, var_valor=boy_proj - boy_2025)}"
            
            # --- CARDS FY ---
            f"{_get_card_mini('FY Estimado', fy_total)}"
            f"{_get_card_mini('FY 2025', fy_2025, var_valor=fy_total - fy_2025)}"
            
            f"</div>"
            
            f"<div style='margin-top: 10px; padding-left: 15px; border-left: 2px solid #eee;'>"
            f"{html_filhos}"
            f"</div>"
            
            f"</div>"
            f"</details>"
        )
        
        batch_html.append(html_item)
        
        # Renderiza a cada 10 itens no nível mestre para manter a fluidez e burlar o limite
        if profundidade == 0 and len(batch_html) >= 10:
            st.markdown("".join(batch_html), unsafe_allow_html=True)
            batch_html = []

    # Renderiza o restante do lote ao final do loop
    if profundidade == 0 and batch_html:
        st.markdown("".join(batch_html), unsafe_allow_html=True)
        return encontrou_dados
    
    return "".join(batch_html)

def _get_card_mini(titulo, valor, var_valor=None):
    """Gera um card HTML com valor principal e variação opcional entre parênteses."""
    valor_formatado = format_brl(valor)
    
    # Se houver valor de variação, formata com a cor e os parênteses
    texto_extra = ""
    if var_valor is not None:
        cor_var = '#d32f2f' if var_valor > 0 else '#2e7d32' if var_valor < 0 else '#666'
        sinal_var = '+' if var_valor > 0 else ''
        # Adiciona os parênteses em um <div> para forçar a quebra de linha visual, com uma margem no topo
        texto_extra = f"<div style='font-size: 11.5px; font-weight: 600; color: {cor_var}; margin-top: 2px;'>({sinal_var}{format_brl(var_valor)})</div>"

    return f"<div style='flex: 1; min-width: 140px; padding: 8px; background-color: #fcfcfc; border: 1px solid #eee; border-radius: 5px;'><div style='font-size: 11px; color: #777;'>{titulo}</div><div style='font-size: 14px; font-weight: bold; color: #111;'>{valor_formatado}{texto_extra}</div></div>"