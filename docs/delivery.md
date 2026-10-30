# Entregas e validação

As ferramentas continuam independentes. Uma atualização do Bottons não precisa gerar versões do Polaroid, do Medidas ou do pacote completo.

## Caminho de uma alteração

| Evento | O que executa |
| --- | --- |
| Documentação, banner ou captura | Contratos rápidos do repositório, sem gerar instalador. |
| Revisão de código de um editor | Testes do aplicativo, encerramento, recuperação, painel, cores e responsividade no Windows. |
| Código integrado no `main` | Validação completa, uma compilação e testes do executável, instalação e atualização. |
| Tag de publicação | Reutilização da compilação completa aprovada do mesmo commit; se ela não estiver disponível, validação completa no Windows. |
| Pacote completo | Releases públicas fixadas são reutilizadas; somente componentes ainda não publicados são compilados durante a preparação. |

No Medidas, o maior formato e o uso de memória continuam sendo testados. No Bottons, a entrega completa também verifica a migração do Moldura. A revisão rápida não substitui a aprovação do executável final.

Os três produtos chamam `_editor-windows.yml`. Mudanças compartilhadas nos scripts, testes e nesse fluxo acionam os produtos afetados pelos filtros. Uma revisão substituída por novos commits pode ser cancelada; uma publicação não é cancelada automaticamente.

## Preparar uma versão individual

Use o Python do ambiente de desenvolvimento e instale os requisitos de testes (`requirements-ci.txt`). Escreva as notas reais da alteração em um arquivo UTF-8. Exemplo para uma versão futura:

```powershell
python scripts/release.py prepare bottons-editor --version 1.2.4 --notes-file artifacts/notas.md
```

O comando mostra a diferença e não grava nada. Para aplicar:

```powershell
python scripts/release.py prepare bottons-editor --version 1.2.4 --notes-file artifacts/notas.md --write
```

Ele atualiza `version.py`, a versão padrão do Inno, os links atuais, os changelogs e as notas. Não altera as versões dos outros produtos, os canais de atualização ou a composição do pacote. Histórico de versões publicadas é preservado. Revise a diferença, execute as validações e integre o PR.

Capturas precisam ser atualizadas quando a interface representada mudar; uma alteração interna não exige novas capturas. Os banners usam a identidade das ferramentas e não precisam ser regenerados por causa de um incremento de versão.

Após a integração, atualize seu checkout para o `main` e use:

```powershell
python scripts/release.py publish bottons-editor
```

Esse segundo comando exige checkout limpo e igual ao `origin/main`, executa os contratos e cria/envia uma tag nova. Não substitui tags existentes. O workflow publica somente depois de obter um executável com validação completa. Uma compilação do `main` que ainda esteja em andamento pode ser aguardada por até dez minutos; na ausência de aprovação reutilizável, a tag faz sua própria compilação e validação.

Os nomes aceitos são `bottons-editor`, `polaroid-editor`, `medidas-editor` e `bundle`. Preparar arquivos e publicar são ações separadas para permitir a revisão do resultado concreto.

## Preparar o pacote completo

O pacote tem versão e composição próprias. Exemplo:

```powershell
python scripts/release.py prepare bundle --version 1.0.3 --include bottons-editor=1.2.4 --notes-file artifacts/notas-pacote.md
```

Use `--write` para aplicar o plano. Componentes não informados em `--include` mantêm a versão fixada. O comando atualiza a composição, suas notas, o catálogo e o guia do pacote, preservando os downloads individuais. Publique os componentes necessários antes de `python scripts/release.py publish bundle`.

Durante a revisão, o planejador consulta cada versão fixada. Uma release pública estável é uma entrada imutável: ela será baixada e verificada, mesmo que o código de desenvolvimento já esteja em outra versão. Um componente inexistente só pode ser compilado se sua versão corresponder ao código do PR. Erros de rede, autorização e limite da API interrompem o plano; não são interpretados como ausência de versão.

Na tag do pacote, todos os componentes precisam estar públicos. Os arquivos efetivamente incluídos passam pelos testes reais do conjunto em uma conta Windows descartável. Um pacote preparado com componentes ainda não publicados não é promovido diretamente: os binários públicos podem ter hashes diferentes, então a tag monta e valida o conjunto com as releases exatas.

O catálogo informa a composição do pacote. Quando houver versões individuais posteriores, seus links e canais continuam independentes. Não é necessário republicar o pacote a cada correção individual.

## Origem e integridade da compilação

`release_artifacts.py` só aceita uma execução bem-sucedida do workflow correto, neste repositório, no `main`, com o commit exato da tag. Artefatos de PRs ou forks não são promovidos. A exceção é a compilação completa feita pela própria tag, cujo job Windows precisa ter concluído com sucesso.

Depois dos testes, o Windows registra `build.json` com produto, versão, commit, execução, tentativa e hashes. A publicação confere os dados da API do GitHub, o SHA-256 do ZIP e o conteúdo esperado; depois confere manifesto, instalador, portátil e comprovante. `build.json` é evidência interna do CI e não é acrescentado aos downloads públicos dos produtos.

Os artefatos aprovados são retidos por 30 dias; diagnósticos por sete dias. Ausência ou expiração provoca uma nova validação, sem enfraquecer os critérios de aprovação. Falhas de comunicação são reportadas. Isso usa artefatos do GitHub, sem novos serviços externos.

## Medição

Referência: publicação do Bottons 1.2.3, execução `40933432507`, em 29/10/2026. Job Windows de quatro minutos: dependências 26 s, compilação 18 s, executável/interface 79 s, instalação/atualização 22 s, migração 23 s. São tempos observados de uma execução, sem incluir revisão, fila ou pacote.

Cache de pip usa os requisitos do produto e do CI. Python e ferramentas diretas de teste têm versões explícitas. Os executáveis já comprimidos são enviados como artefatos sem recompressão. O ganho deve ser comparado por etapa e por número de compilações, sem prometer um tempo fixo para toda entrega.

A otimização dos cenários de navegador deve preservar as verificações de exportação, geometria e recuperação. Testes independentes podem compartilhar infraestrutura apenas se mantiverem isolamento de estado; esperas de debounce ou persistência não devem ser simplesmente removidas.
