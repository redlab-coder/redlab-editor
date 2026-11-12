# Guia de uso

Instale o aplicativo ou abra a versão portátil pelo [catálogo do Medidas Editor](../README.md). A interface abre no navegador padrão e o programa fica disponível na bandeja do Windows até ser encerrado. A edição e a exportação funcionam offline.

## Escolher a ferramenta

Na tela **Ferramentas**, escolha **Medidas personalizadas** ou **Montagem para corte**. Use o menu no topo para alternar. Cada ferramenta conserva suas próprias fotos e ajustes enquanto o aplicativo estiver aberto.

Para montar fotos **3×4, 5×7 e 7×10** em folhas prontas para corte, consulte [Montagem para corte](montage.md). As instruções abaixo são para **Medidas personalizadas**.

## Preparar uma foto

Adicione as fotos pelo botão ou arrastando os arquivos para a biblioteca ou a área de enquadramento. Informe largura e altura em centímetros, aceitando vírgula ou ponto, e clique em **Aplicar nesta foto**. Deixar uma dimensão vazia calcula a outra pela proporção original após corrigir EXIF. As duas dimensões vazias são rejeitadas.

**Consultar medidas do arquivo** mostra pixels, perfil de cor e tamanho calculado com a resolução registrada, quando válida. **Usar essas medidas** é uma ação explícita: o programa nunca presume o tamanho pedido pelo cliente a partir dos metadados.

**Preencher com recorte** é o modo inicial. Arraste para reposicionar e ajuste o zoom para ampliar o recorte. **Centralizar** reposiciona sem alterar a medida. **Girar** aplica 90° à imagem antes do enquadramento.

**Conter imagem inteira** preserva todo o conteúdo, com branco interno quando a proporção for diferente. O zoom e o arraste ficam desabilitados nesse modo para garantir que nenhuma parte seja cortada.

Os contornos e a legenda distinguem a área física solicitada do conteúdo visível no modo inteira. O branco externo pertence à folha comercial. Esses contornos existem somente na interface.

## Folha e revisão

A seleção automática considera as dimensões reais das 27 folhas e escolhe a menor área compatível. Um giro adicional de 90° pode acomodar a fotografia; esse giro é aplicado depois do recorte e preserva o enquadramento. A folha pode ser escolhida manualmente entre as opções compatíveis.

O padrão é **canto superior esquerdo**, sem margem adicional. Os outros três cantos e o centro também estão disponíveis.

Recortes que removem conteúdo e avisos de conversão de cor exigem revisão. Use **Conferir recorte** ou **F**; digitar em um campo não aciona o atalho. No filtro de pendentes, conferir avança para a próxima. Alterar medidas ou enquadramento remove a conferência anterior.

Uma resolução abaixo de 300 ppi gera aviso. O cálculo usa a parte do original aproveitada após o recorte e o zoom. Reamostrar aumenta a quantidade de pixels; não recupera detalhes inexistentes.

## Preparação, lotes e downloads

A seção **Preparação** mostra miniaturas da composição final, incluindo recorte e branco da folha. Clique para ampliar; a prévia permite voltar à edição ou exportar a foto. Antes de definir as medidas, a miniatura mostra somente o original, identificado como pendente.

Marque as fotos desejadas, informe as medidas e clique em **Aplicar às selecionadas**. Uma dimensão vazia é calculada individualmente pela proporção de cada original. Cada foto pode manter modo, medida, folha, posição e recorte próprios.

**Salvar na pasta** informa quando há itens pendentes e oferece exportar as fotos prontas. Cada foto gera um JPEG em uma subpasta identificada pela folha e pela medida solicitada, como `30x40 (30x36)`. A subpasta é criada junto às fotos selecionadas pelo Windows. Para um lote com origens diferentes ou desconhecidas, escolha a pasta de destino uma vez.

Os botões ao lado do nome exportam somente a foto atual. O progresso aparece ao lado de **Preparação**. Ao cancelar o salvamento direto, os JPEGs já concluídos ficam na pasta de saída. Use **Abrir pasta** para encontrá-los. Se já houver um JPEG com o mesmo nome, o novo arquivo recebe um sufixo.

**Baixar JPEG** ou **Baixar ZIP** usa o destino definido pelo navegador. Falhas de processamento aparecem em uma janela de avisos. Quando houver resultados válidos e falhas, o ZIP inclui `LEIA-ME-falhas.txt`.

**Salvar lote** baixa um `.medidas` com os bytes originais e os ajustes. **Abrir lote** substitui a sessão após confirmação. Remover todas as fotos também exige confirmação. Recarregar a aba preserva os ajustes enquanto a instância local e seus temporários existirem; salvar o lote é a forma de continuar depois de encerrar.

## Formatos e limites

Entradas: JPG, PNG, WebP, BMP e TIFF, primeira página. A sessão comporta até 100 fotos e 4 GB de originais entre as duas ferramentas, com até 50 MB e 60 megapixels por imagem. É necessário espaço temporário para normalização e resultados. HEIC e RAW precisam ser convertidos antes.

As prévias usam imagens de até 1600 pixels por lado. A exportação usa os originais e suporta todas as folhas cadastradas, inclusive 61 × 250 cm. O limite de 60 megapixels pertence à entrada, não à folha gerada.

A versão instalada consulta atualizações ao iniciar e a cada 30 minutos, baixa e verifica o instalador. Quando estiver pronto, o cabeçalho oferece **Atualizar e reiniciar**, que guarda uma cópia local das duas ferramentas e reabre o programa com o trabalho recuperado. Sem conexão, a edição continua disponível. [Funcionamento das atualizações](../../../docs/updates.md). A edição portátil não instala atualizações automaticamente.

[← Medidas Editor](../README.md)

## Encerramento

O botão de desligar e a opção Encerrar na bandeja finalizam o editor diretamente, sem confirmação. Uma operação em andamento é interrompida; resultados incompletos não são disponibilizados. Exporte ou salve seu trabalho antes de encerrar. Os originais e lotes já salvos são preservados. A aba poderá permanecer na tela de encerramento, mas o processo e o serviço local são finalizados.
