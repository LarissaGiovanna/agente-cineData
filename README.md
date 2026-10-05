# CineData — agente de filmes (Text-to-SQL)
Agente que responde perguntas em português sobre o catálogo de filmes da CineData Analytics, consultando a camada Gold (`cinerocket.db`) em tempo real. Você pergunta sem saber SQL, o modelo gera o `SELECT`, executa no SQLite e responde.

Feito com Python + PydanticAI + modelos gratuitos do OpenRouter com tool calling. Roda no terminal estilo CLI (comando `cinedata`); o notebook explica cada parte do código.

## Aviso importante
1. **O banco não vai no repositório.** O `cinerocket.db` tem mais de 200MB. Baixe o arquivo do banco de dados e coloque em `src/cinedata/data/cinerocket.db`. Sem ele, o agente mostra `Banco não encontrado em .../data/`.
2. **Cota gratuita do OpenRouter: 50 requests por dia** (zera às 21h, horário de Brasília). Uma pergunta costuma gastar 2 a 3 requests. Planeje os testes: o projeto já economiza de propósito (`max_retries=0`, prompt enxuto, cache de repetidas).
3. **Chave gratuita:** crie em https://openrouter.ai/keys e guarde no `.env`. Sem ela, o terminal pede para colar a chave.

## Como funciona
1. Você digita uma pergunta no terminal (ex: `Lucro médio por gênero`)
2. O agente monta o prompt do sistema (esquema fixo das 10 tabelas + regras) e chama o modelo
3. O modelo chama a tool `consultar_banco(sql)` e só aceita `SELECT` (guardrails em 3 camadas: prompt, validação no código, banco somente leitura)
4. Se o SQL vier errado, o erro volta como texto e o modelo tenta de novo (até 3 tentativas; isso é retry, não troca de modelo)
5. Só troca de modelo se o provider estiver lotado (erro 429 do provider). Cota diária esgotada ou chave inválida (401) não trocam.
6. Pergunta repetida sem histórico volta do `data/cache.json` (0 requests). O comando `/limpar` apaga o arquivo


## Estrutura do projeto
```
notebooks/agente.ipynb    # código explicado, na ordem dos módulos
src/cinedata/             # config, banco, guardrails, modelos, prompt, cache, agente, cli, trace
src/cinedata/tests/       # testes sem gastar cota + teste_tool_calling.py
src/cinedata/data/        # cinerocket.db (baixar) + cache.json (apagável com /limpar)
.env.example / .env       # chave do OpenRouter (não versionado)
pyproject.toml            # comando `cinedata`
```

## Como executar
### Requisitos:
1. Um PC com Windows e Python 3.13 (testado com 3.13.3)
2. O arquivo `cinerocket.db` da atividade
3. Uma chave gratuita do OpenRouter

### 1. Banco de dados
1. Baixe o `cinerocket.db` da pasta compartilhada da atividade
2. Copie para dentro do projeto, neste caminho exato:
```
src/cinedata/data/cinerocket.db
```
3. Confira se o arquivo está lá (ele não aparece no `git status` de propósito: está no `.gitignore`).

### 2. Instalação das dependências
*Nota: este projeto usa `pip` com `venv` (sem `uv`).*
1. Abra o terminal na pasta do projeto
2. Crie e ative a venv:
```bat
python -m venv .venv
.venv\Scripts\activate
```
3. Instale o projeto (isso também cria o comando `cinedata`):
```bat
pip install -e ".[dev]"
```

### 3. Configuração da chave
1. Copie o exemplo e edite:
```bat
copy .env.example .env
```
2. Abra o `.env` no Bloco de Notas e cole sua chave:
```
OPENROUTER_API_KEY=sua_chave_aqui
```

### 4. Rodar os testes (não gastam cota)
No Windows, o `pytest` direto pode não funcionar; use sempre com `python -m`:
```bat
python -m pytest
```
Esperado: `28 passed`. Um dos testes força a leitura da `alembic_version` e dá o erro esperado `access to alembic_version.version_num is prohibited` — é a prova de que o banco barra tabela fora da lista.

Para testar se os modelos aceitam tool calling (gasta ~2 requests por modelo):
```bat
python src/cinedata/tests/teste_tool_calling.py
```
Resultado em 05/10/2026: `nemotron-3.5-lightning:free` OK; `z-ai/glm-5.2:free` deu 404 (slug aposentado, removido da lista); `google/gemma-4-26b-a4b-it:free` deu 429 (provider lotado, mantido como fallback).

### 5. Conversar no terminal
```bat
cinedata
```
Comandos (atalhos de terminal):
```
  /ajuda   mostra a ajuda
  /limpar  apaga o cache (data/cache.json) e zera o histórico
  /sair    encerra (vale /exit, /quit e Ctrl+C)
```
Exemplo:
```
❯ Lucro médio por gênero em R$?
⠋ buscando no catálogo...
(com a resposta + critérios usados)
```

OBS.: Se preferir sem instalar, vale `python -m cinedata.cli`. Para tirar as cores, rode com `NO_COLOR=1 cinedata`.

### 6. Notebook explicado
Abra `notebooks/agente.ipynb` no VSCode ou Jupyter. Ele segue a ordem dos módulos (`config` → `banco` → `guardrails` → `modelos` → `prompt` → `cache` → `agente` → `cli`), mostra o código explicado e roda cada parte. As anotações de cada módulo estão em `docs/anotacoes_notebook.md`.

No notebook, perguntas ao modelo usam sempre `await` (o `run_sync` dá `RuntimeError` no Jupyter):
```python
from cinedata.agente import perguntar_async
resp, res = await perguntar_async("Quantos filmes há no catálogo?")
```

## Definições usadas no prompt
- **Esquema fixo no prompt:** as 10 tabelas vão coladas no prompt do sistema. 
- **Moeda padrão R$** (colunas `_brl`); `_usd` só se pedirem dólar. A resposta sempre diz a moeda.
- **Margem de lucro = lucro ÷ receita**: (receita e orçamento informados, receita > 0) Ordenando pela conta sem arredondar. Se o topo vier com orçamento menor que R$ 10.000, a resposta avisa que parece erro nos dados.
- **Lucro:** o campo foi calculado com NULL virando zero. Perguntas de lucro usam só filmes com receita informada; margem exige receita e orçamento. 
- **"Últimos 5 anos":** inclui o ano atual e só filmes lançados até hoje: `data_lancamento >= date('now','start of year','-4 years') AND data_lancamento <= date('now')`. A data de hoje é injetada por `montar_prompt()`, então acompanha o ano atual (2026).
- **Nota padrão = IMDb** (`nota_imdb`). Nota de usuários = `dim_reviews.nota_media_usuarios`. `nota_tmdb` só vale com `qtd_tmdb > 0` (0 sem votos = "sem votos").
- **"Mais avaliados":** desempate por `qtd_avaliacoes_usuarios DESC`, `nota_media_usuarios DESC`, `titulo`. Ao listar filmes, sempre mostra o `ano_lancamento`.
- **Cache/contexto:** pergunta normalizada (minúsculas, sem espaços extras, sem acentos, sem `?!.` final); guarda só pergunta → resposta final; janela de 4 trocas no histórico; só usa/grava cache sem histórico; erros e a recusa `Só sei responder perguntas sobre o catálogo de filmes.` nunca entram; `/limpar` apaga o arquivo.
- **Tentativas:** 2 retries de SQL (até 3 tentativas). SQL errado = retry; fallback só com provider lotado.

## Limitações dos dados
1. **Duplicadas da fonte:** ~4.558 títulos repetidos (ex: "Die Hart" com ~60 entradas no mesmo dia). Afeta rankings como "mais avaliados". A resposta avisa quando há títulos repetidos.
2. **Orçamentos absurdamente baixos** no topo da margem (ex: R$ 3,29). O agente avisa que parecem erro.
3. **Lucro com nulo como zero** e **base pequena com receita** (~3.373 com receita, ~1.630 com receita e orçamento em 95.645 linhas).
4. **Eventos de luta livre no catálogo** (ex: duplas ator-diretor de WWE): aparecem nos rankings de elenco.

## Modelos e fallback
Ordem atual em `src/cinedata/config.py`:
1. `nvidia/nemotron-3.5-lightning:free` (principal — passou no teste de tool calling)
2. `google/gemma-4-26b-a4b-it:free` (fallback quando o provider do 1º lotar)

`z-ai/glm-5.2:free` foi removido: em 05/10 deu 404 `unavailable for free`.

## Extras: o que entrou e o que ficou de fora
Entraram: guardrails em 3 camadas, fallback entre modelos, cache de respostas, memória de conversa (4 trocas), CLI com cores e loading, e `mostrar_trace()` (ciclo ReAct) para a apresentação.
Ficaram de fora de propósito (tempo/cota): gráficos, busca semântica nas sinopses (agente híbrido), avaliação automática com gabarito e conexão com o Databricks.