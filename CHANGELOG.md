# Changelog

Toda mudança relevante de `memory-lifecycle` é registrada aqui. O formato segue o
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto segue o
[Versionamento Semântico](https://semver.org/lang/pt-BR/). As entradas chegam como
fragmentos em `changelog/unreleased/` e são consolidadas a cada lançamento
(`changelog/README.md`), nas seções Adicionado, Alterado, Descontinuado, Removido,
Corrigido e Segurança.

## [Não lançado]

## [0.1.0] - 2026-11-23

### Adicionado

- `Memory`: memória persistente, contextual e bitemporal para agentes de IA,
  embutida na aplicação sobre PostgreSQL + pgvector. `remember`, `supersede`,
  `correct`, `expire`, `invalidate_context`, `forget`, `history` e
  `migrate`, com uma versão imutável por mudança: só o tempo de registro de uma
  linha se fecha, então "o que sabíamos" nunca é reescrito (ADR 0002).
- `recall` em três modos — agora, `as_of` (o que era verdade, pelo que
  sabemos hoje) e `known_at` (o que, naquele instante, sabíamos ser verdade) —
  com escopo estrito por `contexts` e `entities` (`None` na lista inclui os sem
  id), filtro por `kind`, `limit` obrigatório e busca por similaridade exata
  com `score` em `[0, 1]` (ADR 0009).
- Concorrência explícita: duas escritas sobre a mesma versão, uma vence e a outra
  levanta `ConflictError`; `expected_version_id` torna a escrita condicional.
- Conexão emprestada pelo app, sem segundo pool (ADR 0004): `DSNProvider`,
  `PsycopgPoolProvider`, `DjangoProvider` (entra no `atomic()` do request) e
  `SQLAlchemyProvider` (engine, ou sessão com savepoint por operação), todos
  extras opcionais; `load_provider` lê a fábrica de
  `MEMORY_LIFECYCLE_CONNECTION_PROVIDER`. SQL igual em psycopg 3 e psycopg2.
- `EmbeddingProvider`, o protocolo do provedor, e `FakeEmbeddingProvider`,
  determinístico e sem rede, para as suítes das aplicações.
- Migrações próprias num schema próprio do banco do app: idempotentes,
  conferidas por hash, com a dimensão do vetor fixada e a extensão pgvector
  instalada quando há privilégio.
- Erros tipados (`InvalidArgumentError`, `NotFoundError`, `ConflictError`,
  `EmbeddingError`, `ConfigurationError`, …). Entradas inválidas e schema não
  migrado são recusados antes de qualquer instrução, para não abortar a
  transação do app.
- API e código em inglês, com docstrings e comentários em inglês e português;
  documentação em português, com o vocabulário em `docs/glossario.md` (ADR 0010).
  Licença MIT.
- Um README que apresenta o modelo de memória do começo, em linguagem simples. Uma
  conversa de exemplo, em tabela, mostra o que a memória sabe a cada mensagem e o
  que ainda dá para saber do passado. Depois vêm os conceitos: o que é uma memória e
  as suas etiquetas, versões imutáveis, os dois relógios (validade e registro), as
  três perguntas de `recall`, quando usar `supersede`, `expire` ou `correct`,
  escopo, busca por similaridade, status, isolamento, concorrência e `forget`. Ele
  também cobre o ciclo de um agente, instalação, conexão, provedor de embeddings,
  erros, desempenho e testes. Cada exemplo de código dos conceitos roda na suíte e
  imprime o que o texto diz.
- Guia de conceitos (`docs/conceitos.md`): os dois eixos de tempo, as três
  operações, os três modos de consulta, o escopo estrito, o status derivado e a
  tabela de erros, com trechos que rodam na suíte contra o PostgreSQL.
- Guia de integração (`docs/integracao.md`): instalação, a escolha do provedor de
  conexão e o modo de transação de cada um, Django do começo ao fim (memória por
  tenant, migração junto com o `manage.py migrate`, view na transação do request),
  SQLAlchemy, configuração pelo ambiente, o provedor de embeddings próprio,
  desempenho medido e uso nas suítes de teste.
- Exemplos executáveis em `examples/`: o fluxo de uma conversa com agente
  (recuperar, montar contexto, responder, gravar pela política da aplicação) e o
  mesmo fluxo numa view Django; os dois rodam na suíte.
- Publicação no PyPI como `memory-lifecycle`: `pip install "memory-lifecycle[psycopg]"`
  (ou `[django]`, `[sqlalchemy]`). O pacote declara os tipos (`py.typed`), e a página
  do PyPI liga ao repositório, à documentação, ao CHANGELOG e às issues.
- Política de versões (ADR 0011): SemVer, em que antes da 1.0 uma versão `minor` pode
  quebrar compatibilidade e o CHANGELOG diz quando. O schema só avança, sem downgrade:
  depois de migrar com uma versão nova, uma anterior recusa o schema em
  `Memory.migrate()`.
