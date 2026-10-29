# Usar o Bottons Editor

Baixe o `BottonsEditor-Setup-<versão>.exe` na página de [versões oficiais](https://github.com/redlab-coder/redlab-editor/releases/tag/bottons-v1.2.1) e execute o instalador. A instalação é por usuário, com atalho no menu Iniciar e desinstalação pelas configurações do Windows. A interface abre no navegador padrão e o ícone fica na bandeja, ao lado do relógio. Não precisa instalar Python ou conectar uma conta. A edição e a exportação funcionam offline. Windows 10/11 de 64 bits.

A versão instalada consulta atualizações ao iniciar e a cada 30 minutos, baixa e verifica o instalador. Quando estiver pronto, o cabeçalho oferece **Atualizar e reiniciar**, que guarda uma cópia local do lote e reabre o programa com o trabalho recuperado. Sem conexão, a edição continua disponível. [Funcionamento das atualizações](../../../docs/updates.md).

A cópia portátil **BottonsEditor-Portable.exe** funciona sem instalação e não aplica atualizações automáticas.

Clique no ícone para abrir a interface. Com o botão direito, escolha **Abrir editor** ou **Encerrar editor**. Abrir o executável novamente reutiliza o mesmo processo e a mesma porta. O serviço escuta apenas em `127.0.0.1`: outros computadores da rede não têm acesso. As versões anteriores foram preservadas. Exporte sua sessão antiga antes de encerrá-la e passe a usar o atalho da versão instalada. A bandeja e o cabeçalho identificam a versão em execução.

1. Clique em **Adicionar fotos** ou arraste arquivos para qualquer ponto da coluna Fotos ou da área de enquadramento. Um destaque mostra onde soltar; o painel Ajustes não importa arquivos.
2. Selecione uma foto na coluna esquerda e escolha seu modelo (Quadrado ou Redondo G/M/P). Essa escolha afeta somente ela. Arraste a imagem na prévia para enquadrar, use o zoom e ajuste as cores. O contorno pontilhado delimita a área visível do modelo escolhido. **Guias** mostra/oculta as marcações; **Centralizar** reposiciona sem alterar zoom ou cores. O botão **?** reúne as orientações de uso. Clique na prévia e use as setas para mover um pixel da imagem original; Shift + seta move dez pixels.
3. Digite o valor exato no campo ao lado de cada ajuste. Brilho, contraste e saturação vão de -100 a +100; nitidez de -100 a +200; zoom de 1,00 a 5,00. O botão **↺** zera somente aquele ajuste (zoom retorna a 1,00). Os filtros respondem gradualmente perto do zero e os campos numéricos aceitam duas casas decimais. As setas no campo fazem ajustes de 0,01. Durante o movimento, uma prévia rápida acompanha sua mão; ao soltar, a prévia final é calculada pelo mesmo processamento usado na exportação.
4. Confira as folhas abaixo; clique em uma para ampliar. O ícone de download ao lado de fechar baixa somente essa folha, em JPG na resolução final a 300 DPI. Clique em uma foto ou no espaço da lista e use ↑/↓ para selecionar a anterior/seguinte; a seleção acompanha a rolagem. Os pequenos botões de seta de cada linha continuam alterando a ordem das fotos nas folhas.
5. Clique em **Exportar** no topo da interface. Uma folha baixa como JPG; várias folhas baixam juntas em ZIP, contendo os JPGs individuais. O navegador salva na pasta de downloads ou pergunta onde salvar, conforme suas configurações.
6. Você pode fechar ou recarregar a aba e reabrir pelo ícone, usando o mesmo navegador/perfil: fotos, ajustes e ordem retornam enquanto o Bottons Editor continuar ativo na bandeja. Os ajustes e identificadores da sessão ficam no armazenamento local do navegador; os arquivos completos ficam em uma área temporária local, removida ao excluir as fotos ou encerrar normalmente o aplicativo. Salve o lote ou exporte antes de **Encerrar Bottons Editor**, desligar ou reiniciar o computador. A recuperação da aba não substitui o arquivo de lote e não funciona em outro navegador/perfil. Somente uma aba edita a sessão por vez em navegadores compatíveis com Web Locks, como o Edge testado. Outra aba mostra a sessão para consulta; clique em **Usar nesta aba** para transferir a edição. A aba anterior passa a somente consulta e não sobrescreve os ajustes ao fechar.

O ícone discreto de **Remover todas as fotos**, ao lado de Adicionar, limpa a sessão após confirmação. Exporte antes para guardar o resultado. Os originais permanecem intactos, e o gabarito selecionado continua ativo.

## Ampliar uma folha

A prévia ampliada reúne a folha e o botão para baixar somente aquele JPG.

![Folha ampliada com duas artes e download individual](images/sheet.png)

## Arquivos e limites

Aceita JPG, PNG, WebP, BMP e TIFF (primeira página). Transparência é composta sobre branco; a orientação EXIF é corrigida. Perfis ICC válidos são convertidos a sRGB. Arquivos de até 50 MB e 60 megapixels; o lote aceita até 100 fotos e 4 GB de arquivos originais em armazenamento temporário. O cache de imagens decodificadas é limitado a 160 MiB; isso não inclui a memória transitória necessária para processar uma foto e compor a folha. É necessário espaço livre no disco temporário. HEIC e RAW devem ser convertidos antes.

## Versão e atualizações

A versão aparece ao lado do nome do aplicativo. A verificação é automática; use **Atualizar e reiniciar** quando o botão estiver disponível. Antes desta primeira atualização a partir de uma versão anterior, salve ou exporte o trabalho.

[← Documentação](README.md) · [Bottons Editor](../README.md)

## Transição do Moldura

A versão de transição no repositório antigo permite chegar ao Bottons Editor pelo atualizador existente. O programa deve ser encerrado normalmente depois de exportar as folhas. A identidade de instalação é preservada; o nome, executável e atalhos passam a Bottons Editor. Uma instalação atualizada pode manter a pasta antiga para preservar o caminho registrado; instalações novas usam a pasta Bottons Editor.

## Encerramento

O botão de desligar e a opção Encerrar na bandeja finalizam o editor diretamente, sem confirmação. Uma operação em andamento é interrompida; resultados incompletos não são disponibilizados. Exporte ou salve seu trabalho antes de encerrar. Os originais e lotes já salvos são preservados. A aba poderá permanecer na tela de encerramento, mas o processo e o serviço local são finalizados.

## Salvar e abrir lote

O cabeçalho oferece **Salvar lote** e **Abrir lote**, no mesmo padrão dos outros editores. O arquivo `.bottons` contém cópias integrais dos originais, nomes, ordem, modelo de cada imagem, enquadramento, rotação e filtros. Ele pode ser aberto em outra sessão sem depender dos caminhos dos arquivos originais. Não há etapa de conferência no Bottons.

Abrir outro lote pede confirmação de substituição. Se a leitura falhar, a sessão atual permanece disponível. O arquivo é validado por estrutura, tamanho, modelos e SHA-256 de cada original; lotes de outros editores são rejeitados. O destino dos downloads segue a configuração do navegador.
