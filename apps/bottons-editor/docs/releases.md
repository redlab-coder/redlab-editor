# Publicação do Bottons Editor

A distribuição deste aplicativo é mantida no repositório [RedLab Editor](https://github.com/redlab-coder/redlab-editor).

1. Atualize `version.py`, `CHANGELOG.md`, `RELEASE_NOTES.md`, o link de download e as capturas quando necessário.
2. Execute os testes do aplicativo e os testes de contratos na raiz.
3. Envie uma tag `bottons-v<versão>` correspondente ao aplicativo.

O workflow próprio compila e testa no Windows. Depois de validar executável, interface e instalador, publica os mesmos binários e atualiza somente `updates/bottons-editor.json`. As releases de outro aplicativo não interferem neste canal. O envio é feito por um job Linux.

O instalador é conferido por tamanho, SHA-256, produto e endereço esperado. A instalação acontece ao encerrar normalmente. A edição portátil não instala atualizações.

[Processo completo e transição](../../../docs/maintenance.md) · [← Documentação](README.md)
