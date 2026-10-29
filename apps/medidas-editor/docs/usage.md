# Guia de uso

Instale `MedidasEditor-Setup-1.0.1.exe` ou abra a [versão portátil](https://github.com/redlab-coder/redlab-editor/releases/tag/medidas-v1.0.1). A interface abre no navegador padrão; o programa fica disponível na bandeja do Windows até ser encerrado. Não é necessário instalar Python. A edição e a exportação funcionam offline.

## Preparar uma foto

Adicione as fotos pelo botão ou arrastando os arquivos para a biblioteca ou a área de enquadramento. Informe largura e altura em centímetros, aceitando vírgula ou ponto, e clique em **Aplicar nesta foto**. Deixar uma dimensão vazia calcula a outra pela proporção original após corrigir EXIF. As duas dimensões vazias são rejeitadas.

**Consultar medidas do arquivo** mostra pixels, perfil de cor e tamanho calculado com a resolução registrada, quando válida. **Usar essas medidas** é uma ação explícita: o programa nunca presume o tamanho pedido pelo cliente a partir dos metadados.

**Preencher com recorte** é o modo inicial. Arraste para reposicionar e ajuste o zoom para ampliar o recorte. **Centralizar** reposiciona sem alterar a medida. **Girar** aplica 90° à imagem antes do enquadramento.

**Conter imagem inteira** preserva todo o conteúdo, com branco interno quando a proporção for diferente. O zoom e o arraste ficam desabilitados nesse modo para garantir que nenhuma parte seja cortada.

O contorno azul indica a área física solicitada. No modo inteira, o verde indica o conteúdo visível. O branco externo pertence à folha comercial. Esses contornos existem somente na interface.

## Folha e revisão

A seleção automática considera as dimensões reais das 27 folhas e escolhe a menor área compatível. Um giro adicional de 90° pode acomodar a fotografia; esse giro é aplicado depois do recorte e preserva o enquadramento. A folha pode ser escolhida manualmente entre as opções compatíveis.

O padrão é **canto superior esquerdo**, sem margem adicional. Os outros três cantos e o centro também estão disponíveis.

Recortes que removem conteúdo e avisos de conversão de cor exigem revisão. Use **Conferir recorte** ou **F**; digitar em um campo não aciona o atalho. No filtro de pendentes, conferir avança para a próxima. Alterar medidas ou enquadramento remove a conferência anterior.

Uma resolução abaixo de 300 ppi gera aviso. O cálculo usa a parte do original aproveitada após o recorte e o zoom. Reamostrar aumenta a quantidade de pixels; não recupera detalhes inexistentes.

## Preparação, lotes e downloads

A seção **Preparação** mostra miniaturas da composição final, incluindo recorte e branco da folha. Clique para ampliar; a prévia permite voltar à edição ou exportar a foto. Antes de definir as medidas, a miniatura mostra somente o original, identificado como pendente.

Marque as fotos desejadas, informe as medidas e clique em **Aplicar às selecionadas**. Uma dimensão vazia é calculada individualmente pela proporção de cada original. Cada foto pode manter modo, medida, folha, posição e recorte próprios.

**Exportar lote** informa quando há itens pendentes e oferece exportar somente as fotos prontas. Um lote gera um ZIP com um JPEG por foto; não existe composição de várias fotos independentes na mesma folha. Falhas de processamento são mostradas em uma janela de avisos e não impedem os demais arquivos. Quando houver resultados válidos e falhas, o ZIP inclui `LEIA-ME-falhas.txt`.

O botão de download ao lado do nome exporta somente a foto atual. A exportação acontece em segundo plano, um item por vez. O download começa automaticamente ao concluir; o progresso aparece no botão de exportação e ao lado de **Preparação**, sem painel de arquivos prontos. O ícone de cancelar ao lado do progresso interrompe a fila; resultados parciais não ficam disponíveis para download.

Os downloads seguem o destino e a política de nomes do navegador, como nas outras ferramentas RedLab. Para escolher uma pasta a cada download, habilite essa opção no navegador. O aplicativo não tem acesso irrestrito às pastas do computador. Prefixos numéricos evitam nomes duplicados dentro do ZIP, inclusive quando os originais têm o mesmo nome.

**Salvar lote** baixa um `.medidas` com os bytes originais e os ajustes. **Abrir lote** substitui a sessão após confirmação. Remover todas as fotos também exige confirmação. Recarregar a aba preserva os ajustes enquanto a instância local e seus temporários existirem; salvar o lote é a forma de continuar depois de encerrar.

## Formatos e limites

Entradas: JPG, PNG, WebP, BMP e TIFF, primeira página. Até 100 fotos, 50 MB e 60 megapixels por imagem; 4 GB de originais por lote, mais espaço temporário para normalização e resultados. HEIC e RAW precisam ser convertidos antes.

As prévias usam imagens de até 1600 pixels por lado. A exportação usa os originais e suporta todas as folhas cadastradas, inclusive 61 × 250 cm. O limite de 60 megapixels pertence à entrada, não à folha gerada.

Na versão instalada, atualizações verificadas são aplicadas ao encerrar normalmente. A versão portátil não instala atualizações automaticamente.

[← Medidas Editor](../README.md)

## Encerramento — próxima versão

O botão de desligar e a opção Encerrar na bandeja finalizam o editor diretamente, sem confirmação. Uma operação em andamento é interrompida; resultados incompletos não são disponibilizados. Exporte ou salve seu trabalho antes de encerrar. Os originais e lotes já salvos são preservados. A aba poderá permanecer na tela de encerramento, mas o processo e o serviço local são finalizados.
