<!--
Fragmento de changelog da branch `docs/readme-completo`.
Mantenha só as seções que se aplicam. Escreva para quem lê o CHANGELOG da
biblioteca daqui a seis meses: o que mudou para quem usa a biblioteca e por quê,
não o nome do arquivo que você editou. Diga quando uma mudança é incompatível.

NÃO edite o CHANGELOG.md nem a versão no pyproject.toml — os dois são consolidados
de uma vez na branch de release. Este bloco de comentário pode ficar; ele não vai
para o CHANGELOG.
-->

### Adicionado
- Um README que apresenta o modelo de memória do começo, em linguagem simples. Uma conversa de exemplo, em tabela, mostra o que a memória sabe a
  cada mensagem e o que ainda dá para saber do passado. Depois vêm os conceitos:
  o que é uma memória e as suas etiquetas, versões imutáveis, os dois
  relógios (validade e registro), as três perguntas de `recall`, quando usar
  `supersede`, `expire` ou `correct`, escopo, busca por similaridade, status,
  isolamento, concorrência e `forget`. Ele também cobre o ciclo de um agente,
  instalação, conexão, provedor de embeddings, erros, desempenho e testes. Cada
  exemplo de código dos conceitos roda na suíte e imprime o que o texto diz.
