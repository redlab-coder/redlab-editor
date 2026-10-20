<p align="center"><img src="docs/images/banner.svg" alt="RedLab Editor — ferramentas para preparar suas fotos" width="100%"></p>

Dois aplicativos independentes para preparar imagens para impressão. Processamento local, instalação para Windows e atualizações próprias para cada ferramenta.

| Ferramenta | Para que serve | Acesso |
| --- | --- | --- |
| **Bottons Editor** | Montagem nos gabaritos Square e Round G, M e P, com sangria espelhada e organização em folhas. | [Baixar instalador](https://github.com/redlab-coder/redlab-editor/releases/download/bottons-v1.1.0/BottonsEditor-Setup-1.1.0.exe) · [Documentação](apps/bottons-editor/README.md) |
| **Polaroid Editor** | Enquadramento, ajustes e montagem de fotos no template de polaroid, com conferência antes de exportar. | [Baixar instalador](https://github.com/redlab-coder/redlab-editor/releases/download/polaroid-v1.1.2/PolaroidEditor-Setup-1.1.2.exe) · [Documentação](apps/polaroid-editor/README.md) |

## Bottons Editor

O Moldura agora se chama **Bottons Editor**. A produção mantém os mesmos tamanhos, guias, sangria e montagem em 300 DPI. A interface oferece importação por arraste na biblioteca e no editor, filtros graduais e limpeza do lote com confirmação. O fluxo é direto, sem etapa de conferência.

![Área de trabalho do Bottons Editor](apps/bottons-editor/docs/images/workspace.png)

[Guia de uso](apps/bottons-editor/docs/usage.md) · [Gabaritos](apps/bottons-editor/docs/templates.md) · [Versão portátil](https://github.com/redlab-coder/redlab-editor/releases/download/bottons-v1.1.0/BottonsEditor-Portable.exe)

## Polaroid Editor

Prévia em pé para editar e conferir; exportação deitada para impressão. Fotos de 8 × 8 cm em um gabarito de 12,7 × 9 cm, a 300 DPI, com a faixa de corte preservada.

![Área de trabalho do Polaroid Editor](apps/polaroid-editor/docs/images/workspace.png)

[Guia de uso](apps/polaroid-editor/docs/usage.md) · [Impressão](apps/polaroid-editor/docs/printing.md) · [Versão portátil](https://github.com/redlab-coder/redlab-editor/releases/download/polaroid-v1.1.2/PolaroidEditor-Portable.exe)

## Instalação e atualizações

Baixe somente a ferramenta que deseja usar. Cada aplicativo tem instalador, versão e canal de atualização próprios; atualizar um deles não instala o outro. As imagens são processadas no computador. O acesso à internet é usado para consultar e baixar atualizações.

Os repositórios anteriores de [Moldura](https://github.com/redlab-coder/moldura) e [Polaroid Editor](https://github.com/redlab-coder/polaroid-editor) preservam o histórico. Suas versões de transição encaminham as instalações existentes para este repositório. No Moldura, exporte o trabalho antes de fechar para atualizar; no Polaroid Editor, salve o lote.

## Projeto

O código e o histórico das duas ferramentas estão reunidos aqui, mantendo seus motores de impressão separados.

- [Desenvolvimento e testes](docs/development.md)
- [Publicação, canais e transição](docs/maintenance.md)
- [Validação desta integração](docs/validation.md)
- [Alterações](CHANGELOG.md)
- [Contribuir](CONTRIBUTING.md)
- [Relatar um problema](https://github.com/redlab-coder/redlab-editor/issues/new/choose)
