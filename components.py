import plotly.express as px
import pandas as pd

# def plot_drilldown_chart(df, level_col, ano_at, ano_ant):
#     """
#     Gera um gráfico de barras horizontal mostrando a variação absoluta (R$) 
#     entre o ano atual e o anterior para o nível hierárquico selecionado.
#     """
#     # 1. Agrupamento por Ano e pela Coluna de Nível (ex: Desc_Conta, Localidade)
#     pivot = df.groupby(['Ano', level_col])['Valor'].sum().unstack(level=0).fillna(0)
    
#     # Garantir que ambos os anos existem no DataFrame para evitar erros de cálculo
#     for ano in [ano_at, ano_ant]:
#         if ano not in pivot.columns:
#             pivot[ano] = 0
            
#     # 2. Cálculo da Variação (Saving vs Desvio)
#     pivot['Variacao'] = pivot[ano_at] - pivot[ano_ant]
    
#     # Ordenar para mostrar os maiores ganhos (savings) no topo ou base
#     pivot = pivot.sort_values(by='Variacao', ascending=True).reset_index()

#     # 3. Criação do Gráfico
#     # Usamos a escala RdYlGn_r (Red-Yellow-Green Reverse)
#     # Valores negativos (Savings) ficam VERDES | Valores positivos (Gastos) ficam VERMELHOS
#     fig = px.bar(
#         pivot,
#         x='Variacao',
#         y=level_col,
#         orientation='h',
#         color='Variacao',
#         color_continuous_scale='RdYlGn_r',
#         color_continuous_midpoint=0,
#         labels={'Variacao': 'Diferença YoY (R$)', level_col: ''},
#         title=f"Impacto Financeiro por {level_col} (Diferença {ano_ant} vs {ano_at})"
#     )

#     # Ajustes estéticos
#     fig.update_layout(
#         showlegend=False,
#         height=400 + (len(pivot) * 20), # Altura dinâmica baseada no número de itens
#         margin=dict(l=20, r=20, t=50, b=20),
#         yaxis={'categoryorder': 'total descending'}
#     )
    
#     return fig

def render_dynamic_table(df, level_col, ano_at, ano_ant):
    """
    Cria a matriz de variação mensal respeitando estritamente os filtros.
    """
    if df.empty:
        return pd.DataFrame()
    
    # 1. Pivotar dados por ano
    # Mês nas colunas, Nível nas linhas
    p_at = df[df['Ano'] == ano_at].pivot_table(
        index=level_col, columns='Mes', values='Valor', aggfunc='sum', observed=True
    ).fillna(0)
    
    p_ant = df[df['Ano'] == ano_ant].pivot_table(
        index=level_col, columns='Mes', values='Valor', aggfunc='sum', observed=True
    ).fillna(0)
    
    # 2. Harmonizar colunas (garantir que ambos tenham os mesmos meses)
    todos_indices = sorted(list(set(p_at.index) | set(p_ant.index)))
    todos_meses = sorted(list(set(p_at.columns) | set(p_ant.columns)))
    
    p_at = p_at.reindex(index=todos_indices, columns=todos_meses, fill_value=0)
    p_ant = p_ant.reindex(index=todos_indices, columns=todos_meses, fill_value=0)
    
    # 3. Calcular a Variação Mensal (Delta)
    df_delta = p_at - p_ant
    
    # 4. Adicionar Coluna de Total e Ordenar
    df_delta['Total Geral'] = df_delta.sum(axis=1)
    
    # Mapear números dos meses para nomes abreviados
    meses_br = {
        1:'Jan', 2:'Fev', 3:'Mar', 4:'Abr', 5:'Mai', 6:'Jun',
        7:'Jul', 8:'Ago', 9:'Set', 10:'Out', 11:'Nov', 12:'Dez'
    }
    df_delta.rename(columns=meses_br, inplace=True)
    
    # Ordenamos pelos maiores savings (mais negativos) primeiro
    return df_delta.sort_values(by='Total Geral')