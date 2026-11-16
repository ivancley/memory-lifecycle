# memory-lifecycle

Memória de longo prazo para agentes de IA, que lembra **o que é verdade**,
**o que era verdade** e **o que o agente sabia** em cada momento. Ela vive dentro
do seu PostgreSQL (com pgvector), na sua transação, sem servidor extra, framework
ou ORM, e sem amarrar você a um provedor de LLM.

> **Status:** 0.1.0, testada contra PostgreSQL 16 + pgvector com psycopg 3,
> psycopg2, o pool do psycopg, Django e SQLAlchemy. Ainda **não publicada** no
> PyPI; instale a partir do repositório.

## Por que outra biblioteca de memória?

Um assistente que conversa com a mesma pessoa por semanas precisa lembrar do que
ouviu. Guardar frases num banco vetorial resolve o primeiro dia. O problema
aparece quando os fatos **mudam**:

- A pessoa preferia respostas curtas e agora quer respostas detalhadas. Qual das
  duas o agente deve usar? (A nova, mas a antiga não pode sumir do histórico.)
- A pessoa disse "trabalho na Acme" e, dias depois, corrigiu: "me enganei, é
  Apex". Foi um engano, não uma mudança: a versão errada não deve aparecer em
  nenhuma resposta.
- Um cliente pergunta: "por que o assistente me disse aquilo na terça?". Para
  responder, é preciso saber o que a memória continha **na terça**, e não o que
  ela contém hoje.

A memory-lifecycle trata esses três casos de três jeitos diferentes, e consegue
responder a cada uma das perguntas acima.

## Sumário

- [Em um minuto](#em-um-minuto)
- [Uma conversa com o Pedro](#uma-conversa-com-o-pedro)
- [Os conceitos](#os-conceitos)
  1. [Memória: um fato sobre alguém](#1-memória-um-fato-sobre-alguém)
  2. [Versões: nada é escrito por cima](#2-versões-nada-é-escrito-por-cima)
  3. [Os dois relógios: validade e registro](#3-os-dois-relógios-validade-e-registro)
  4. [Três perguntas: agora, como era, o que sabíamos](#4-três-perguntas-agora-como-era-o-que-sabíamos)
  5. [Como uma memória muda](#5-como-uma-memória-muda)
  6. [Escopo: o que está em jogo nesta conversa](#6-escopo-o-que-está-em-jogo-nesta-conversa)
  7. [Busca por significado](#7-busca-por-significado)
  8. [Status e histórico](#8-status-e-histórico)
  9. [Isolamento e concorrência](#9-isolamento-e-concorrência)
  10. [Esquecer](#10-esquecer)
- [Um agente com memória](#um-agente-com-memória)
- [Instalação](#instalação)
- [Conectando ao seu banco](#conectando-ao-seu-banco)
- [O seu provedor de embeddings](#o-seu-provedor-de-embeddings)
- [Erros](#erros)
- [Desempenho](#desempenho)
- [Testando a sua aplicação](#testando-a-sua-aplicação)
- [Documentação](#documentação)

## Em um minuto

```python
import os

from memory_lifecycle import FakeEmbeddingProvider, Memory
from memory_lifecycle.connection.dsn import DSNProvider

connection = DSNProvider(os.environ["DATABASE_URL"])
embeddings = FakeEmbeddingProvider()  # troque pelo seu provedor de embeddings
memory = Memory(connection=connection, embeddings=embeddings, tenant_id="org-1")
memory.migrate()  # cria um schema próprio dentro do seu banco; pode rodar sempre

v1 = memory.remember("agent-7", "Prefere respostas curtas", kind="preference")
memory.supersede("agent-7", v1.memory_id, "Prefere respostas detalhadas")

now = memory.recall("agent-7", query="estilo de resposta", contexts=[None])
then = memory.recall("agent-7", as_of=v1.recorded_at)
known = memory.recall("agent-7", known_at=v1.recorded_at)
print([r.version.content for r in now])    # ['Prefere respostas detalhadas']
print([r.version.content for r in then])   # ['Prefere respostas curtas']
print([r.version.content for r in known])  # ['Prefere respostas curtas']

memory.forget("agent-7", everything=True)  # apaga de verdade toda versão
```

A próxima seção mostra o mesmo movimento numa conversa de seis meses; depois,
[Os conceitos](#os-conceitos) explicam cada peça em detalhe.

## Uma conversa com o Pedro

Antes dos conceitos, veja a memória funcionando. O Pedro começa a conversar com
um assistente em janeiro, e o sistema ainda não sabe nada sobre ele. Cada linha
abaixo é uma mensagem dele. A última coluna é o que diferencia esta biblioteca:
o que mudou não some, e dá para perguntar sobre o passado.

| quando | o Pedro diz | o que a memória sabe agora | o que ainda dá para saber do passado |
|---|---|---|---|
| 10/jan | *(primeira conversa)* | nada sobre o Pedro | — |
| 10/jan | "Meu nome é Pedro." | • se chama Pedro | — |
| 10/jan | "Moro em Fortaleza." | • se chama Pedro<br>• mora em Fortaleza | — |
| 20/fev | "Trabalho na Acme." | • se chama Pedro<br>• mora em Fortaleza<br>• trabalha na **Acme** ⚠️ *o Pedro se enganou, mas ninguém sabe ainda* | — |
| 05/mar | "Estou de férias." | • se chama Pedro<br>• mora em Fortaleza<br>• trabalha na Acme<br>• está de férias | — |
| 20/mar | "Voltei das férias." | • se chama Pedro<br>• mora em Fortaleza<br>• trabalha na Acme | Esteve de férias de 05/mar a 20/mar. |
| 02/abr | "Me enganei: não é Acme, é Apex!" | • se chama Pedro<br>• mora em Fortaleza<br>• trabalha na **Apex** | Trabalha na Apex desde 20/fev: o passado também foi corrigido.<br>Mas, entre 20/fev e 02/abr, o assistente acreditava em Acme, porque foi o que o Pedro disse, e isso fica registrado para auditoria. |
| 15/jul | "Me mudei para Recife no começo de junho." | • se chama Pedro<br>• mora em **Recife**<br>• trabalha na Apex | Morou em Fortaleza até 01/jun.<br>De 01/jun a 15/jul, o assistente ainda achava que era Fortaleza: só soube da mudança em 15/jul. |

Repare em três coisas:

- **Férias:** "voltei" não apaga nada. A memória só deixa de valer *agora*, e
  continua verdadeira para o período em que valeu (é um `expire`).
- **Engano:** o Pedro informou errado e corrigiu depois. A correção não apaga o
  erro do histórico; ela o marca como errado (é um `correct`). Perguntas sobre o passado passam a responder Apex, mas a
  auditoria ainda sabe que o assistente acreditou em Acme por um tempo.
- **Mudança de cidade:** o Pedro contou em julho algo que aconteceu em junho. A
  memória guarda as duas datas: quando a mudança **aconteceu** e quando o sistema
  **ficou sabendo** (é um `supersede` com data retroativa).

Em julho, depois da conversa toda, a aplicação pode perguntar:

| pergunta | consulta | resposta |
|---|---|---|
| Onde o Pedro mora? | `recall()` (agora) | Recife |
| Onde ele morava em 1º de maio? | `recall(as_of=01/mai)` | Fortaleza |
| Onde ele morava em 20 de junho, pelo que sabemos hoje? | `recall(as_of=20/jun)` | Recife |
| Em 20 de junho, onde o assistente *achava* que ele morava? | `recall(known_at=20/jun)` | Fortaleza |
| Onde ele trabalhava em 1º de março? | `recall(as_of=01/mar)` | Apex |
| Em 1º de março, o que o assistente *achava* sobre o trabalho dele? | `recall(known_at=01/mar)` | Acme |
| Ele estava de férias em 10 de março? | `recall(as_of=10/mar)` | sim |

As duas últimas colunas da primeira tabela e as perguntas `as_of`/`known_at` são
os dois relógios da biblioteca, explicados na [seção 3](#3-os-dois-relógios-validade-e-registro)
dos conceitos.

### O código da conversa

O bloco abaixo reproduz a conversa inteira e roda na suíte de testes, então as
tabelas acima não mentem. Duas observações:

- **Quem escolhe o comando é a sua aplicação**, normalmente com ajuda do LLM:
  "voltei das férias" vira `expire`, "me enganei, não é Acme" vira `correct`. A biblioteca
  guarda e responde.
- **`clock` é o relógio da memória.** Aqui ele é avançado à mão para colocar cada
  mensagem no seu dia. Em produção você não o passa, e a biblioteca usa a hora
  atual.

```python
from datetime import datetime, timezone


def day(d, m):
    """Um dia de 2025, às 9h UTC."""
    return datetime(2025, m, d, 9, tzinfo=timezone.utc)


today = day(10, 1)
assistant = Memory(
    connection=connection, embeddings=embeddings, tenant_id="org-1", clock=lambda: today
)


def knows(**moment):
    """O que a memória sabe sobre o Pedro, em ordem alfabética."""
    return sorted(r.version.content for r in assistant.recall("pedro", **moment))


print(knows())  # []

# 10/jan: "Meu nome é Pedro." / "Moro em Fortaleza."
assistant.remember("pedro", "se chama Pedro", kind="name")
home = assistant.remember("pedro", "mora em Fortaleza", kind="address")

# 20/fev: "Trabalho na Acme." (o Pedro se enganou)
today = day(20, 2)
job = assistant.remember("pedro", "trabalha na Acme", kind="job")

# 05/mar: "Estou de férias."   20/mar: "Voltei das férias."
today = day(5, 3)
vacation = assistant.remember("pedro", "está de férias", kind="status")
today = day(20, 3)
assistant.expire("pedro", vacation.memory_id)

# 02/abr: "Me enganei: não é Acme, é Apex!"
today = day(2, 4)
assistant.correct("pedro", job.memory_id, "trabalha na Apex")

# 15/jul: "Me mudei para Recife no começo de junho."
today = day(15, 7)
assistant.supersede("pedro", home.memory_id, "mora em Recife", valid_from=day(1, 6))

print(knows())  # ['mora em Recife', 'se chama Pedro', 'trabalha na Apex']
print(knows(kind="address", as_of=day(1, 5)))      # ['mora em Fortaleza']
print(knows(kind="address", as_of=day(20, 6)))     # ['mora em Recife']
print(knows(kind="address", known_at=day(20, 6)))  # ['mora em Fortaleza']
print(knows(kind="job", as_of=day(1, 3)))          # ['trabalha na Apex']
print(knows(kind="job", known_at=day(1, 3)))       # ['trabalha na Acme']
print(knows(kind="status", as_of=day(10, 3)))      # ['está de férias']
```

## Os conceitos

Esta seção apresenta o modelo de memória do começo. Cada trecho de código
continua o anterior (o `memory` é o de [Em um minuto](#em-um-minuto)), e todos rodam na suíte de
testes do repositório contra um PostgreSQL real: o que está nos comentários
`# [...]` é a saída de verdade.

### 1. Memória: um fato sobre alguém

Uma **memória** é uma frase curta que vale a pena guardar: "mora em Recife",
"prefere respostas curtas", "o projeto Atlas usa Python". Ela sempre pertence a
alguém e pode vir com etiquetas que ajudam a encontrá-la depois:

| campo | o que é | exemplo |
|---|---|---|
| `content` | o fato, em texto | `"mora em Recife"` |
| `kind` | a categoria, livre (obrigatória) | `"preference"`, `"fact"`, `"address"` |
| `tenant_id` | a organização. Fixado na `Memory`; toda consulta filtra por ele | `"org-1"` |
| `owner_id` | o **dono**: a quem a memória pertence (um usuário, um agente) | `"ana"` |
| `entity_id` | a **entidade**: sobre o que a memória é (um cliente, um produto) | `"cliente-42"` |
| `context_id` | o **contexto**: onde ela se aplica (um projeto, um período) | `"sprint-12"` |
| `source` | de onde veio, para a sua auditoria | `"chat:2026-11-09"` |

Entidade e contexto são ids **opacos**: a biblioteca não sabe o que significam,
só filtra por eles. O significado é da sua aplicação.

```python
from datetime import datetime, timezone

UTC = timezone.utc


def contents(**query):
    """O conteúdo das memórias da Ana que respondem à consulta, em ordem alfabética."""
    return sorted(r.version.content for r in memory.recall("ana", **query))


memory.remember("ana", "prefere respostas curtas", kind="preference", source="chat")
print(contents(kind="preference"))  # ['prefere respostas curtas']
```

### 2. Versões: nada é escrito por cima

Quando uma memória muda, a biblioteca **não altera a linha antiga**: ela grava
uma **versão** nova. Cada memória tem um `memory_id`, que fica o mesmo para
sempre, e cada versão tem o seu próprio `version_id`. A versão nova aponta para
a anterior em `previous_version_id`, e a lista inteira sai de `history`.

O motivo é simples: uma memória que pode ser reescrita não consegue responder "o
que você sabia antes?". Numa linha já gravada, a única coisa que muda depois é a
data em que o sistema deixou de acreditar nela. O único apagamento de verdade é
`forget`, para pedidos de privacidade (seção 10).

### 3. Os dois relógios: validade e registro

Toda versão carrega **dois intervalos de tempo**, e entender a diferença entre
eles é entender a biblioteca:

| relógio | campos | pergunta que responde |
|---|---|---|
| **validade** | `valid_from`, `valid_to` | quando isto era verdade **no mundo**? |
| **registro** | `recorded_at`, `superseded_at` | quando o **sistema** acreditava nisto? |

Na maior parte do tempo os dois andam juntos: a pessoa conta algo, o agente grava
na hora. Eles se separam quando você descobre um fato **depois** de ele
acontecer. A Ana mora em Recife desde 2024. Hoje ela conta que se mudou para São
Paulo **em março**:

```text
                jan/2024                 mar/2026                  hoje
validade   ─────[ mora em Recife ────────)[ mora em São Paulo ───────────▶
registro                                                           ▲
                                                 o sistema só soube agora
```

```python
home = memory.remember(
    "ana", "mora em Recife", kind="address", valid_from=datetime(2024, 1, 1, tzinfo=UTC)
)
memory.supersede(
    "ana", home.memory_id, "mora em São Paulo", valid_from=datetime(2026, 3, 1, tzinfo=UTC)
)
print(contents(kind="address"))                                        # ['mora em São Paulo']
print(contents(kind="address", as_of=datetime(2025, 6, 1, tzinfo=UTC)))  # ['mora em Recife']
```

Três regras técnicas valem para todo o tempo na biblioteca:

- `None` num fim de intervalo quer dizer **aberto** ("ainda vale"), nunca
  "desconhecido".
- Os intervalos são semiabertos, `[início, fim)`: no instante exato de uma troca,
  vale a versão nova.
- Todo `datetime` precisa ter fuso horário. Um sem fuso é recusado com
  `InvalidArgumentError`.

### 4. Três perguntas: agora, como era, o que sabíamos

Com dois relógios, `recall` sabe responder três perguntas diferentes:

| modo | pergunta | para que serve |
|---|---|---|
| agora (sem argumento) | o que é verdade agora? | responder à pessoa |
| `as_of=D` (como em) | o que era verdade em D, **pelo que sabemos hoje**? | relatórios, "onde ela morava em 2025?" |
| `known_at=D` (sabido em) | o que, em D, o sistema **sabia** ser verdade? | auditoria: o que o agente sabia quando respondeu |

A diferença entre as duas últimas aparece quando uma informação chega atrasada.
Em `as_of`, a mudança para São Paulo já vale a partir de março, porque hoje
sabemos disso. Em `known_at` olhando para o instante em que gravamos Recife, a
resposta é Recife, porque naquele momento era isso o que o sistema sabia:

```python
print(contents(kind="address", as_of=datetime(2026, 4, 1, tzinfo=UTC)))  # ['mora em São Paulo']
print(contents(kind="address", known_at=home.recorded_at))             # ['mora em Recife']
```

Passar `as_of` e `known_at` juntos é recusado com `InvalidArgumentError`.

### 5. Como uma memória muda

Três situações parecem iguais de longe e são tratadas de jeitos diferentes. Para
escolher, faça duas perguntas:

```text
O fato que está gravado já foi verdade algum dia?
├── não: foi informado ou anotado errado ────────────────────► correct
└── sim
    └── Algo novo tomou o lugar dele?
        ├── sim: "agora prefere X", "mudou para São Paulo" ──► supersede
        └── não: simplesmente deixou de valer ───────────────► expire
```

| operação | situação | o que fica gravado |
|---|---|---|
| `supersede` (substituir) | um fato novo toma o lugar do antigo | o antigo vale até a troca; o novo, dali em diante |
| `expire` (encerrar) | o fato era verdade e deixou de ser | o fato com um fim de validade (`valid_to`) |
| `correct` (corrigir) | o fato nunca foi verdade | o certo no lugar do errado, com as mesmas datas de validade |

`supersede` você já viu na seção 3. Um fato que termina sem dar lugar a outro é
um `expire`: ele some das consultas de agora, mas continua no passado.

```python
trip = memory.remember("ana", "está de férias", kind="status")
memory.expire("ana", trip.memory_id)
print(contents(kind="status"))                         # []
print(contents(kind="status", as_of=trip.recorded_at))  # ['está de férias']
```

Um fato informado ou anotado errado é um `correct`. A validade não muda, só o registro: o
errado desaparece de "agora" e de "como era", mas continua em `known_at`, porque
a auditoria precisa saber que o agente acreditou nele por um tempo.

```python
job = memory.remember("ana", "trabalha na Acme", kind="job")
memory.correct("ana", job.memory_id, "trabalha na Apex")
print(contents(kind="job"))                            # ['trabalha na Apex']
print(contents(kind="job", as_of=job.recorded_at))     # ['trabalha na Apex']
print(contents(kind="job", known_at=job.recorded_at))  # ['trabalha na Acme']
```

Por baixo, as três fazem o mesmo movimento: fecham o registro da versão vigente
(`superseded_at`) e inserem versões novas. Nenhuma reescreve validade.

### 6. Escopo: o que está em jogo nesta conversa

Quem sabe quais projetos, períodos ou clientes estão ativos numa conversa é a
sua aplicação. Ela informa isso a `recall` pelo **escopo**, e a biblioteca filtra
de forma estrita:

| argumento | o que volta naquele eixo |
|---|---|
| `contexts=None` (padrão) | tudo: não filtra |
| `contexts=["sprint-12"]` | só as memórias do contexto `sprint-12` |
| `contexts=["sprint-12", None]` | as de `sprint-12` e as que não têm contexto |
| `contexts=[]` | nada |

A mesma regra vale para `entities`. Repare no `None` dentro da lista: é ele que
traz as memórias gerais, sem contexto. Por isso o exemplo de "Em um minuto" usa
`contexts=[None]`.

Tirar um id do escopo **não apaga nada**: a memória volta quando o id volta.
Quando um contexto realmente acabou, diga isso com uma escrita explícita,
`invalidate_context`, que encerra (`expire`) tudo o que ainda valia nele.

```python
memory.remember("ana", "o sprint 12 foca em pagamentos", kind="note", context_id="sprint-12")
print(contents(kind="note", contexts=["sprint-12"]))  # ['o sprint 12 foca em pagamentos']
print(contents(kind="note", contexts=["sprint-13"]))  # []

memory.invalidate_context("ana", "sprint-12")
print(contents(kind="note", contexts=["sprint-12"]))  # []
```

### 7. Busca por significado

Com `query`, `recall` ordena os resultados por **similaridade de significado**:
cada memória é convertida num vetor numérico (um *embedding*) quando é gravada, a
pergunta também, e o pgvector mede a distância entre eles. Cada resultado traz
um `score` entre 0 e 1, maior quando é mais parecido. Sem `query`, os resultados
vêm do mais recente para o mais antigo, com `score=None`.

A busca sempre respeita os outros filtros (escopo, `kind`, o modo de tempo) e
sempre tem limite: `limit`, que vale 20 por padrão.

```python
results = memory.recall("ana", query="onde a Ana mora?", kind="address", limit=3)
print([r.version.content for r in results])  # ['mora em São Paulo']
```

Os exemplos deste README usam o `FakeEmbeddingProvider`, que gera vetores
determinísticos e não entende significado nenhum: serve para testes. Em
produção, você passa o seu provedor ([veja abaixo](#o-seu-provedor-de-embeddings)).

### 8. Status e histórico

O status de uma versão (`ACTIVE`, `EXPIRED`, `SUPERSEDED`, `CORRECTED`) **não é
guardado**: `derive_status` o calcula a partir das datas da versão e da versão
seguinte. Assim ele nunca fica desatualizado em relação aos dados.

```python
from memory_lifecycle import Status, derive_status

versions = memory.history("ana", job.memory_id)
successor = {v.previous_version_id: v for v in versions}
statuses = [
    derive_status(v, now=datetime.now(UTC), successor=successor.get(v.version_id))
    for v in versions
]
print([s.value for s in statuses])  # ['corrected', 'active']
```

### 9. Isolamento e concorrência

Toda instrução que a biblioteca manda ao banco filtra por `tenant_id` **e**
`owner_id`. Uma organização nunca vê a memória de outra, e um dono nunca vê a de
outro dono. Permissões mais finas que isso são da sua aplicação.

```python
other_org = Memory(connection=connection, embeddings=embeddings, tenant_id="org-2")
print([r.version.content for r in other_org.recall("ana")])  # []
```

Duas escritas sobre a mesma versão nunca vencem as duas: a segunda levanta
`ConflictError`. Para garantir que você está mudando exatamente a versão que
leu, passe `expected_version_id`:

```python
from memory_lifecycle import ConflictError

coffee = memory.remember("ana", "gosta de café", kind="taste")
memory.supersede("ana", coffee.memory_id, "gosta de chá", expected_version_id=coffee.version_id)
try:  # outra escrita, baseada na mesma leitura antiga
    memory.supersede("ana", coffee.memory_id, "gosta de mate", expected_version_id=coffee.version_id)
except ConflictError:
    pass  # alguém mudou antes: releia com history e decida
print(contents(kind="taste"))  # ['gosta de chá']
```

### 10. Esquecer

`forget` é o **único apagamento físico**, feito para pedidos de privacidade. Ele
apaga toda versão do alvo, inclusive o histórico: depois dele, nem `known_at`
encontra o que foi esquecido. O alvo é exatamente um entre uma memória
(`memory_id`), uma entidade (`entity_id`) ou tudo do dono (`everything=True`).

```python
memory.forget("ana", everything=True)
print(contents())                          # []
print(contents(known_at=job.recorded_at))  # []
```

## Um agente com memória

O ciclo de um agente com memory-lifecycle tem quatro passos: recuperar o que
importa, montar o contexto, responder e gravar o que mudou. A biblioteca não fala
com nenhum LLM; essa parte é sua.

```py
def answer(memory, llm, owner_id, message, project_id):
    # 1. recuperar: o que importa para esta mensagem, neste projeto
    memories = memory.recall(owner_id, query=message, contexts=[project_id, None], limit=10)

    # 2. montar o contexto e 3. responder
    known = "\n".join(f"- {r.version.content}" for r in memories)
    reply = llm.complete(f"O que você sabe sobre a pessoa:\n{known}\n\nMensagem: {message}")

    # 4. gravar: o LLM propõe, a sua aplicação decide se é remember, supersede ou correct
    for fact in reply.new_facts:
        memory.remember(owner_id, fact.text, kind=fact.kind, context_id=project_id)
    return reply.text
```

O exemplo completo, que roda na suíte, está em
[`examples/agent_flow.py`](examples/agent_flow.py); a mesma coisa numa view
Django está em [`examples/django_app/`](examples/django_app/).

## Instalação

A biblioteca ainda não está no PyPI. Instale do repositório, com o extra do
driver que a sua aplicação já usa:

```bash
pip install "memory-lifecycle[psycopg] @ git+https://github.com/ivancley/PyBrain"     # psycopg 3 e pool
pip install "memory-lifecycle[django] @ git+https://github.com/ivancley/PyBrain"      # Django
pip install "memory-lifecycle[sqlalchemy] @ git+https://github.com/ivancley/PyBrain"  # SQLAlchemy
```

O núcleo não tem nenhuma dependência obrigatória: cada adaptador importa o que
precisa só quando é usado. O banco precisa ser PostgreSQL 13 ou mais novo, com a
extensão [pgvector](https://github.com/pgvector/pgvector) disponível. Para
experimentar localmente:

```bash
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres pgvector/pgvector:pg16
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres
```

`migrate()` cria um schema próprio dentro do seu banco (`memory_lifecycle`, por
padrão; mude com `Memory(schema=...)`), instala o pgvector se o usuário tiver
permissão e aplica as migrações pendentes. Ele pode rodar a cada deploy. A
dimensão dos vetores fica fixada na primeira migração, pela do seu provedor de
embeddings.

## Conectando ao seu banco

A biblioteca **nunca abre um segundo pool de conexões**: ela pede uma conexão
emprestada a um *provedor*, que usa o que a sua aplicação já tem. Existem dois
modos de transação:

- **própria** (`OWN`): cada operação da memória faz o seu próprio commit.
- **participar** (`PARTICIPATE`): a escrita entra na transação que a sua
  aplicação já abriu. Se a aplicação der rollback, a memória volta junto.

| provedor | extra | modo |
|---|---|---|
| `DSNProvider(dsn)` | `psycopg` | própria: uma conexão por operação, para scripts e jobs |
| `PsycopgPoolProvider(pool)` | `psycopg` | própria, com uma conexão do pool da aplicação |
| `DjangoProvider(alias)` | `django` | participar: entra no `atomic()` do request (fora de um, faz commit sozinha) |
| `SQLAlchemyProvider(engine)` | `sqlalchemy` | própria |
| `SQLAlchemyProvider.from_session(session)` | `sqlalchemy` | participar: um savepoint por operação, que vale no `session.commit()` |

```py
from memory_lifecycle import Memory
from memory_lifecycle.connection.django import DjangoProvider

memory = Memory(connection=DjangoProvider(), embeddings=MyEmbeddingProvider(client), tenant_id=org_id)
```

O SQL é o mesmo para psycopg 3 e psycopg2, e a biblioteca não registra nenhum
adaptador de tipo na sua conexão. Se preferir configurar pelo ambiente,
`load_provider()` lê a fábrica de `MEMORY_LIFECYCLE_CONNECTION_PROVIDER`
(`pacote.modulo:funcao`). Detalhes de cada provedor, com Django do começo ao
fim, em [`docs/integracao.md`](docs/integracao.md).

## O seu provedor de embeddings

A biblioteca não chama nenhum serviço de embeddings: você passa um objeto com
três membros, o protocolo `EmbeddingProvider`.

```py
from collections.abc import Sequence


class MyEmbeddingProvider:
    dimension = 1024              # fixa: o schema é criado com ela
    model_name = "my-model-v1"    # gravado em cada versão

    def __init__(self, client) -> None:
        self._client = client

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return self._client.embed(list(texts))  # um vetor por texto, na mesma ordem
```

- O embedding é calculado **antes** de a biblioteca pegar uma conexão: um
  provedor lento não segura uma conexão do seu pool.
- Uma falha do provedor vira `EmbeddingError`, com o erro original encadeado.
- Um vetor de tamanho diferente da dimensão do schema vira
  `EmbeddingDimensionError`. Trocar de modelo pede um schema novo.

## Erros

Todos os erros herdam de `MemoryLifecycleError`, e as mensagens são em inglês.
Entradas inválidas são recusadas **antes** de qualquer instrução no banco, para
não abortar a transação da sua aplicação.

| erro | quando | o que fazer |
|---|---|---|
| `InvalidArgumentError` | uma entrada que o contrato proíbe | corrigir a chamada |
| `NotFoundError` | id desconhecido, de outro dono ou de outro tenant | não diz qual dos três, de propósito |
| `ConflictError` | outra escrita chegou antes | reler com `history` e decidir |
| `EmbeddingError` | o provedor de embeddings falhou | tentar de novo ou desistir |
| `EmbeddingDimensionError` | o provedor gera vetores de outra dimensão | usar o provedor original ou outro schema |
| `ConfigurationError` | schema não migrado, autocommit ligado, pgvector ausente | seguir a mensagem |
| `MigrationError` | uma migração aplicada mudou ou é desconhecida | atualizar a biblioteca |

## Desempenho

- A busca por similaridade é **exata** (sem índice aproximado): a distância é
  calculada para toda versão que passa nos filtros. Com vetores de 1536
  dimensões, medimos até 11 ms para 2 mil versões por dono e 82 ms para 24 mil.
- **O escopo é a alavanca**: com `contexts` ou `entities`, a mesma consulta cai
  para menos de 1 ms de SQL. Passe o escopo da conversa.
- Sem `query`, a consulta lê só as linhas pedidas pelo `limit`.

## Testando a sua aplicação

- `FakeEmbeddingProvider` é determinístico e não usa rede: textos iguais dão
  vetores iguais.
- `Memory(clock=...)` recebe uma função que devolve o "agora". Com ela, um teste
  coloca as escritas em datas escolhidas, sem `sleep`; é assim que se testa
  `as_of` e `known_at`.
- Use um schema por teste (`Memory(schema=...)`) e apague-o no fim.

## Documentação

- [`docs/conceitos.md`](docs/conceitos.md): os conceitos deste README com mais
  detalhe, incluindo como cada operação aparece no histórico.
- [`docs/integracao.md`](docs/integracao.md): instalação, cada provedor de
  conexão, o seu provedor de embeddings, desempenho e testes.
- [`docs/glossario.md`](docs/glossario.md): os termos, com o identificador do
  código ao lado de cada um (o código é em inglês; a documentação, em português).
- [`docs/architecture.md`](docs/architecture.md) e [`docs/adr/`](docs/adr/): as
  decisões de arquitetura e as alternativas que perderam.

## Desenvolvimento

O fluxo completo está em [`docs/development-workflow.md`](docs/development-workflow.md).
A versão curta:

```bash
make install && make hooks && make db-up && cp .env.example .env
make quality   # ruff, guardas e a suíte inteira contra o Postgres
```

## Licença

MIT. Veja [`LICENSE`](LICENSE).
