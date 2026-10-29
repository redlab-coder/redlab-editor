# Desenvolvimento

As ferramentas são independentes em `apps/bottons-editor`, `apps/polaroid-editor` e `apps/medidas-editor`. Cada pasta contém o aplicativo Python, a interface local, o instalador e os testes. Consulte também o guia de desenvolvimento de cada aplicativo.

Use um ambiente Python próprio para cada ferramenta e instale seu `requirements-build.txt`. Os testes de navegador usam Playwright e Chromium; os testes de instalação exigem Windows e uma conta isolada sem instalações reais dessas ferramentas.

Na raiz, execute `python -m unittest discover -s tests -v` para validar os contratos de publicação e a comparação de impressão com o Moldura aprovado. Dentro da pasta do aplicativo, execute o mesmo comando para testar sua API, motor e atualização.

Os workflows de cada produto compilam e testam o executável portátil, a interface e o instalador no Windows. O Bottons Editor também testa a atualização a partir de uma compilação do Moldura histórico. Os arquivos publicados são os mesmos aprovados nesses testes.

Os commits originais foram importados com `git subtree`, sem compactar o histórico. O teste de regressão consulta o motor original pelo commit preservado; mantenha o histórico completo no checkout de CI.

Alterações no Bottons Editor devem preservar Square e Round G/M/P, medidas físicas, sangria, guias e montagem das folhas. Melhorias de interface compartilhadas não devem introduzir a conferência do Polaroid no Bottons.

O Medidas Editor usa Pillow para entrada/ICC e prévias, e libvips empacotada para exportar as maiores folhas por partes. Seu teste `tests/large_export_check.py` gera de fato o formato máximo e mede memória. A tabela oficial fica somente em `formats.json`; a interface recebe a mesma fonte. Consulte sua documentação para revisão, projetos, cor e os testes físicos pendentes na Noritsu.

A preparação de atualização fica em `recovery.py`; o controlador visual em `ui/update.js`. Esses dois módulos têm o mesmo contrato nos três produtos e devem ser mantidos coerentes. O adaptador de cada `app.py` e `ui/app.js` traduz o estado específico da ferramenta. A cópia usa o formato de lote já existente e não recodifica os originais. `scripts/check_update_flow.py` valida API e interface; `scripts/update_test_helpers.py` também é usado pelos testes reais dos instaladores para comparar o estado antes e depois do reinício.

## Identidade da família

Cada produto define sua identidade e paleta em `ui/theme.json`. `python scripts/generate_branding.py` gera os tokens CSS, o símbolo vetorial e o ícone Windows com nove resoluções; `--check` detecta arquivos desatualizados. `branding.py`, `tray_panel.py` e `ui/family.css` são comuns aos três produtos e têm testes contra divergência. Ajustes de cor devem usar tokens, preservando as cores funcionais de guias de corte e avisos. O servidor entrega tema, estrutura e componentes em uma única resposta CSS, reduzindo as conexões locais necessárias para abrir cada aba.

O painel da bandeja usa Tkinter do Python, carregado sob demanda em uma única thread, com criação, eventos e destruição no mesmo contexto, conforme o [modelo de threads do Tkinter](https://docs.python.org/3.14/library/tkinter.html#threading-model). Não exige uma nova dependência de pip. O build fixa PyInstaller 6.22.3, cuja [correção para Tcl/Tk 9 com recursos embutidos](https://pyinstaller.org/en/stable/CHANGES.html) permite usar o Python atual no Windows. O PyInstaller inclui Tcl/Tk no executável; isso acrescenta arquivos e tamanho ao pacote, mas o painel só é inicializado ao abrir. A bandeja continua com um menu nativo de compatibilidade. Os testes do executável devem abrir o painel de fato para verificar os recursos empacotados, além de encerrar com ele aberto.

`python scripts/check_family_ui.py <produto>` verifica cores de hover e arraste, seis larguras, toque e redução de movimento. `python scripts/check_tray_panel.py <produto>` exercita o callback real da bandeja em uma instância descartável, Tab, Escape, ações e escalas de 100% a 250%. O teste não procura nem controla as instalações do operador.

Os banners são regenerados com `python scripts/docs_assets.py`; as capturas reais dos três editores com `python scripts/capture_release_docs.py`. Os scripts usam somente artes de demonstração e não acessam as instalações ou as fotos do operador.

## Pacote completo Windows

O distribuidor fica em `bundle/`. `package.json` fixa sua composição; `scripts/bundle.py` verifica os instaladores e gera as seções Inno com as identidades já declaradas por cada produto. `redlab-editor.iss` verifica versões e mutexes, valida todos os instaladores escolhidos antes de iniciar e executa-os sequencialmente. As ferramentas continuam sendo as únicas proprietárias dos arquivos, atalhos, registros e desinstaladores.

Em uma conta de desenvolvimento, é possível compilar sem instalar nada:

```powershell
python scripts/bundle.py fetch
./apps/bottons-editor/scripts/bootstrap_inno.ps1
python scripts/bundle.py build
```

As versões fixadas precisam estar publicadas para `fetch`. Use uma pasta de entradas nova em uma nova tentativa (`--inputs <pasta>`). O workflow do PR obtém entradas compiladas do próprio código; a tag usa os instaladores públicos exatos. Não execute `check_bundle.py` ou `capture_bundle.py` na conta do operador: eles exigem o runner Windows descartável. A validação de interface captura somente a janela criada pelo próprio teste.

O instalador suporta `/COMPONENTS=bottons_editor,polaroid_editor,medidas_editor` e `/TASKS=desktopicon`, além dos parâmetros padrão do Inno. Para implantação administrada e testes, `/INSTALLROOT=<pasta>` altera a base apenas das instalações novas; instalações registradas mantêm sua localização. `/LOGDIR=<pasta>` altera o destino dos registros e do resumo `result.ini`. Instalações parciais retornam 1; falhas de preparação usam o código padrão do Inno. O pacote não força o fechamento de editores nem reverte instalações já concluídas.
