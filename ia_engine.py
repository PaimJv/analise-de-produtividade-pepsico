import streamlit as st
from groq import Groq

@st.cache_data(show_spinner=False)
def get_ai_insights(data_summary, context_text, api_key):
    """
    Motor de Auditoria Exaustiva.
    Analisa os dados de variação (YoY) buscando eficiência, 
    ofensores e padrões de produtividade.
    """
    if not api_key:
        return "⚠️ Erro: 'GROQ_API_KEY' não configurada nos Secrets do Streamlit."

    try:
        # 1. Inicialização do Cliente Groq
        client = Groq(api_key=api_key)

        # 2. Definição da Persona e Instruções de Auditoria
        system_instruction = (
            "Você é um Auditor Sênior de Controladoria e Engenheiro de Facilities. "
            "Sua especialidade é análise de variação de custo (Variance Analysis). "
            "Você deve realizar uma leitura técnica profunda, sem generalismos, focando em "
            "eficiência operacional, gestão de contratos e otimização de recursos. "
            "Terminologia técnica: 'Classe de Custo' refere-se às Contas contábeis."
        )

        # 3. Engenharia de Prompt (Foco em Auditoria Completa)
        user_prompt = f"""
        REALIZE UMA AUDITORIA EXAUSTIVA DE DESEMPENHO FINANCEIRO YOY baseada nos dados fornecidos.
        Analise todas as linhas, cruzando as dimensões para encontrar a causa raiz dos resultados.

        ### CONTEXTO DA AUDITORIA:
        {context_text}

        ### BASE DE DADOS (VARIAÇÕES POR DIMENSÃO):
        {data_summary}

        ---
        ### REQUISITOS DO RELATÓRIO TÉCNICO:
        1. **Detalhamento de Impactos Financeiros (Tabela):** Apresente uma tabela Markdown contendo TODOS os itens encontrados com variação de R$ 1.000,00 ou mais na base de dados fornecida. A tabela deve conter exatamente estas colunas: **Desc_Conta**, **Localidade**, **Centro_Custo** e **Variação**.
           - Logo após a tabela, forneça um resumo detalhado sobre as variações encontradas, detalhando onde houve os impactos e as maiores reduções de custo. 
           - Nota: Neste item, foque no detalhamento dos fatos e locais; não há necessidade de identificar causas raízes técnicas (como eficiência ou gestão contratual).

        2. **Identificação de Padrões Transversais:** Analise se existe um comportamento comum entre as localidades ou centros de custo para uma mesma conta ou grupo de despesas.

        ---
        ### REGRAS CRÍTICAS DE FORMATAÇÃO:
        - **Valores Monetários:** Utilize o padrão brasileiro (ex: **R$ 1.234.567,89**).
        - **Valores Negativos:** Devem ser apresentados obrigatoriamente seguindo este modelo: **R$ -1.000,00**.
        - Use Markdown e negrito para destacar KPIs e valores importantes.
        """

        # 4. Chamada ao Modelo Llama 3.3-70b
        # Temperature 0.1 para garantir máximo rigor técnico e evitar alucinações.
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=4000, # Espaço amplo para análises detalhadas e longas
            top_p=1,
            stream=False,
        )

        return completion.choices[0].message.content

    except Exception as e:
        return f"❌ Erro na Auditoria IA: {str(e)}"