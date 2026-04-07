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
            df_bruto = pd.read_csv(f, sep=';', encoding=enc_final, engine='c', header=None)
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
        
    # Junta tudo em uma base final
    df_final = pd.concat(dfs, ignore_index=True)
    
    # =========================================================
    # 🚀 OTIMIZAÇÃO EXTREMA DE MEMÓRIA (COMPRESSÃO DE DADOS)
    # =========================================================
    # 1. Converte textos repetitivos em categorias (Reduz 80% da RAM)
    colunas_texto = ['Centro_Custo', 'DenClsCst', 'Classe_Custo', 'DenConta', 
                     'Pacote', 'Tipo_Dado', 'Localidade', 'VP', 'P_L', 
                     'Desc_Conta', 'Desc_Material']
    
    for col in colunas_texto:
        if col in df_final.columns:
            df_final[col] = df_final[col].astype('category')
            
    # 2. Converte números gigantes (float64) para números leves (float32)
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
    """Função Wrapper com Animação de Carregamento em Tempo Real"""
    foco_analise = st.session_state.get('radio_foco_ia', 'Análise 360° (Ambos)')
    
    # 1. Cria os espaços reservados para a Animação na tela
    aviso_texto = st.empty()
    barra_progresso = st.progress(0)
    
    with st.spinner("Iniciando motor de renderização estrutural..."):
        # 2. Passa os componentes de animação para o motor rodar
        html_final = _gerar_html_recursivo(df_nivel, dims, 0, {}, foco_analise, aviso_texto, barra_progresso)
        
    # 3. Limpa a barra de progresso da tela quando o trabalho terminar
    aviso_texto.empty()
    barra_progresso.empty()
    
    if html_final.strip() == "":
        st.info(f"Nenhum registro encontrado com o critério: **{foco_analise}**")
    else:
        # Mensagem de sucesso rápida antes da tabela HTML
        st.success("✅ Relatório renderizado com sucesso!")
        st.markdown(f"<div style='padding-bottom: 50px;'>{html_final}</div>", unsafe_allow_html=True)


def _gerar_html_recursivo(df_nivel, dims, profundidade, filtro_contexto, foco_analise, text_ui=None, progress_ui=None):
    """Motor de geração de HTML/CSS com callback de progresso. (Seguro contra CodeBlocks do Markdown)"""
    if not dims or profundidade >= len(dims):
        return ""

    col = dims[profundidade]
    
    if filtro_contexto:
        for c, v in filtro_contexto.items():
            df_nivel = df_nivel[df_nivel[c] == v]

    itens = sorted(df_nivel[col].dropna().unique().astype(str).tolist())
    total_itens = len(itens)
    html_completo = ""

    # Máscaras Globais
    mask_pxxf = df_nivel['Tipo_Dado'].astype(str).str.contains(r'P\d{2}F', na=False)
    mask_aop = df_nivel['Tipo_Dado'] == 'AOP26'
    mask_2025 = df_nivel['Tipo_Dado'] == '2025'

    for idx, item in enumerate(itens):
        
        # =======================================================
        # 🔄 MOTOR DE ANIMAÇÃO 
        # =======================================================
        if profundidade == 0 and text_ui is not None and progress_ui is not None:
            porcentagem = int(((idx + 1) / total_itens) * 100)
            text_ui.info(f"⏳ Processando bloco mestre: **{item}** ({idx + 1}/{total_itens})")
            progress_ui.progress(porcentagem)

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
        
        var_2025 = ytd_real - ytd_2025
        
        # Filtro de negócio
        if foco_analise == "Apenas Savings (Eficiência)" and round(var_2025, 2) > 0:
            continue
        elif foco_analise == "Apenas Desvios (Gastos)" and round(var_2025, 2) <= 0:
            continue

        # Lógica de Cores da Variação
        cor_var = '#d32f2f' if round(var_2025, 2) > 0 else '#2e7d32' if round(var_2025, 2) < 0 else '#666'
        sinal_var = '+' if round(var_2025, 2) > 0 else ''

        label_dim = LABELS_MAP.get(col, col)
        label_pref = '📌' if profundidade == 0 else '➥'
        
        # Componente Visual de Card (HTML numa linha só para evitar bloco de código)
        def card_html(titulo, valor, var_valor=None):
            var_html = ""
            if var_valor is not None:
                c_var = '#d32f2f' if round(var_valor, 2) > 0 else '#2e7d32' if round(var_valor, 2) < 0 else '#666'
                s_var = '+' if round(var_valor, 2) > 0 else ''
                var_html = f"<div style='font-size: 13px; font-weight: 600; color: {c_var}; margin-top: 6px;'>{s_var}{format_brl(var_valor)} (Variação)</div>"
            
            return f"<div style='flex: 1; min-width: 180px; padding: 12px; background-color: #f8f9fa; border-radius: 8px; border: 1px solid #e0e0e0;'><div style='font-size: 13px; color: #666; font-weight: 600;'>{titulo}</div><div style='font-size: 20px; font-weight: bold; color: #111; margin-top: 4px;'>{format_brl(valor)}</div>{var_html}</div>"

        # Recursão (Mandamos None para as UIs para evitar que a barra pisque fora de ordem)
        novo_contexto = (filtro_contexto or {}).copy()
        novo_contexto[col] = item
        html_filhos = _gerar_html_recursivo(df_nivel, dims, profundidade + 1, novo_contexto, foco_analise, None, None)

        # Montagem do HTML pai colando as strings linha a linha sem espaços no começo
        html_item = (
            f"<details style='margin-bottom: 10px; border: 1px solid #d1d5db; border-radius: 8px; background-color: #ffffff; overflow: hidden; box-shadow: 0 1px 2px rgba(0,0,0,0.05);'>"
            f"<summary style='padding: 14px; font-weight: bold; cursor: pointer; background-color: #fcfcfc; border-bottom: 1px solid #eee; font-family: sans-serif; font-size: 15px;'>"
            f"{label_pref} {item} <span style='font-weight: normal; color: #555; margin-left: 10px;'>| YTD Real: {format_brl(ytd_real)} | Variação: <span style='color: {cor_var}; font-weight: bold;'>{sinal_var}{format_brl(var_2025)}</span></span>"
            f"</summary>"
            f"<div style='padding: 20px; font-family: sans-serif;'>"
            f"<div style='margin-bottom: 10px; font-size: 18px; font-weight: bold; color: #333; border-bottom: 2px solid #eee; padding-bottom: 5px;'>📊 Visão 1: Análise YTD</div>"
            f"<div style='display: flex; gap: 15px; flex-wrap: wrap; margin-bottom: 25px;'>"
            f"{card_html('YTD Real', ytd_real)}"
            f"{card_html('Meta (AOP)', ytd_aop, ytd_real - ytd_aop)}"
            f"{card_html('Vs Ano Ant. (2025)', ytd_2025, var_2025)}"
            f"</div>"
            f"<div style='margin-bottom: 10px; font-size: 18px; font-weight: bold; color: #333; border-bottom: 2px solid #eee; padding-bottom: 5px;'>🔮 Visão 2: Projeção Resto do Ano (BOY)</div>"
            f"<div style='display: flex; gap: 15px; flex-wrap: wrap; margin-bottom: 25px;'>"
            f"{card_html('BOY Projetado', boy_proj)}"
            f"{card_html('BOY Ano Ant. (2025)', boy_2025, boy_proj - boy_2025)}"
            f"</div>"
            f"<div style='margin-bottom: 10px; font-size: 18px; font-weight: bold; color: #333; border-bottom: 2px solid #eee; padding-bottom: 5px;'>🎯 Visão 3: Ano Completo (FY)</div>"
            f"<div style='display: flex; gap: 15px; flex-wrap: wrap; margin-bottom: 20px;'>"
            f"{card_html('FY Estimado (YTD + BOY)', fy_total)}"
            f"{card_html('FY Ano Ant. (2025)', fy_2025, fy_total - fy_2025)}"
            f"</div>"
            f"<div style='margin-top: 15px; padding-left: 20px; border-left: 3px solid #e5e7eb;'>"
            f"{html_filhos}"
            f"</div>"
            f"</div>"
            f"</details>"
        )
        html_completo += html_item

    return html_completo