# ADR 0011 — Versões, compatibilidade de schema e publicação no PyPI

- **Status:** aceito
- **Data:** 2026-11-20
- **Regra tocada:** regra 7 do `CLAUDE.md` (migrações só acrescentam); Etapa 9 de `.data/planejamento-macro.md`
- **Módulos afetados:** `migrations`, `pyproject.toml`, `.github/workflows/publish.yml`

## Contexto

A 0.1.0 é a primeira versão que sai do repositório. A partir dela, quem instala
do PyPI precisa saber três coisas que o código não diz: quando uma atualização
pode quebrar a aplicação, o que acontece com o schema da memória no banco dela
ao atualizar ou voltar uma versão, e de onde vem o arquivo que ela instala.

Duas forças pesam. O PyPI nunca deixa republicar um número de versão, nem depois
de um *yank*, então um pacote errado queima o número. E o schema vive no banco
do app (ADR 0008): ele sobrevive à troca da biblioteca, e duas versões dela podem
encontrá-lo ao longo do tempo.

## Decisão

A biblioteca segue o Versionamento Semântico, o schema só avança, e toda versão é
publicada pelo GitHub Actions a partir de uma tag, com ensaio no TestPyPI e
aprovação manual antes do PyPI.

- **Versões.** `MAJOR.MINOR.PATCH`. Antes da 1.0, uma mudança incompatível na API
  pública sobe o `minor` e um `patch` nunca quebra nada. Da 1.0 em diante, só o
  `major` quebra. O CHANGELOG marca toda mudança incompatível como
  **Incompatível**. A API pública é o que `memory_lifecycle.__all__` exporta;
  módulos com `_` no nome não fazem parte dela.
- **Schema.** Uma versão nova pode trazer migrações novas, e `Memory.migrate()` as
  aplica. Nenhuma migração apaga dados das versões de memória nem muda o que elas
  significam (regra 7, ADR 0008). **Não há downgrade de schema**: depois de
  migrar com uma versão nova, uma versão anterior recusa o schema em
  `Memory.migrate()` com `MigrationError` ("upgrade the library"). Voltar a
  biblioteca exige o backup do banco. Uma versão que traz migração diz isso no
  CHANGELOG.
- **Publicação.** `release/vX.Y.Z` consolida o CHANGELOG e sobe a versão
  (`changelog/README.md`). O merge vai para `main`, e a tag `vX.Y.Z` em `main`
  dispara `.github/workflows/publish.yml`. Esse workflow:
  - recusa uma tag que não bate com a versão do `pyproject.toml`;
  - roda `twine check` e instala e importa o wheel;
  - publica no TestPyPI;
  - espera a aprovação do dono no ambiente `pypi`, que só aceita tags `v*`, e
    publica no PyPI.

  A autenticação é por *Trusted Publishing* (OIDC), sem token guardado.

## Consequências

**Fica mais fácil**
- Quem consome sabe pelo número se pode atualizar sem ler o código, e pelo
  CHANGELOG se a atualização migra o banco.
- O número de versão só é queimado depois de o pacote passar pelo TestPyPI e por
  uma aprovação humana.
- Não há segredo de publicação para vazar ou expirar: o PyPI confia no
  repositório, no arquivo do workflow e no ambiente.

**Fica mais difícil**
- Uma migração que precisaria transformar dados existentes vira uma decisão de
  `major` (ou de `minor`, antes da 1.0), com caminho de migração documentado.
- Um app que atualiza a biblioteca, migra e depois precisa voltar não tem
  caminho automático: o rollback é do banco, não da biblioteca.
- Publicar depende do GitHub Actions e de três cadastros fora do código: os
  publicadores pendentes do PyPI e do TestPyPI e os ambientes `pypi` e
  `testpypi` do repositório.

## Alternativas consideradas

### Publicar à mão com token (`uv publish` ou `twine upload`)
- **Prós:** nenhum workflow nem cadastro de publicador.
- **Contras:** o token fica guardado na máquina ou num secret e dá upload em
  qualquer versão. O build sai do ambiente local, com o que estiver na árvore.
- **Rejeitada porque:** o build reproduzível a partir de uma tag e a ausência de
  segredo valem mais que o cadastro feito uma vez.

### Migrações com `down` (downgrade de schema)
- **Prós:** voltar a versão da biblioteca sem restaurar backup.
- **Contras:** um `down` que desfaz uma coluna apaga o que foi escrito nela,
  e esta biblioteca guarda histórico que não se reescreve (ADR 0002). É mais um
  SQL por migração para testar, nos dois sentidos.
- **Rejeitada porque:** perder versões de memória num rollback contradiz a razão
  de a biblioteca existir. O backup do banco já cobre esse caso.

### CalVer (`2026.11.0`)
- **Prós:** a data diz a idade da versão.
- **Contras:** o número não diz se a atualização quebra a aplicação.
- **Rejeitada porque:** para uma biblioteca embutida no código do app, a
  compatibilidade é a pergunta que o número precisa responder.

## Em aberto

- Uma guarda que compare `__all__` com a versão anterior e exija **Incompatível**
  no CHANGELOG quando um nome some.
- A partir de que versão Python a biblioteca é testada na CI (hoje só a 3.12,
  com 3.11 e 3.12 declaradas).

## Revisitar quando

A API pública estabilizar o bastante para a 1.0, ou um consumidor precisar voltar
uma versão da biblioteca depois de migrar.
