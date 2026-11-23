<!--
Fragmento de changelog da branch `chore/preparar-publicacao`.
-->

### Adicionado
- Publicação no PyPI como `memory-lifecycle`: `pip install "memory-lifecycle[psycopg]"`
  (ou `[django]`, `[sqlalchemy]`). O pacote declara os tipos (`py.typed`), e a página
  do PyPI liga ao repositório, à documentação, ao CHANGELOG e às issues.
- Política de versões (ADR 0011): SemVer, em que antes da 1.0 uma versão `minor` pode
  quebrar compatibilidade e o CHANGELOG diz quando. O schema só avança, sem downgrade:
  depois de migrar com uma versão nova, uma anterior recusa o schema em
  `Memory.migrate()`.
