# Medidas, qualidade e Noritsu

O aplicativo separa **original**, **área solicitada** e **folha comercial**. O recorte é aplicado à área solicitada. Uma folha maior acrescenta branco e não amplia essa área.

`formats.json` é a única tabela de produção: 27 formatos, com nome comercial e medidas reais separados. Não existe formato 50×190 nessa tabela. A interface recebe seus dados do processamento.

Medidas são comparadas com `Decimal`, antes de converter para pixels. Entradas aceitam até seis casas decimais; valores não positivos, vazios ou menores que um pixel a 300 ppi são rejeitados. O encaixe considera a foto na orientação informada e girada em 90°. A menor área vence; em empate, prefere-se a solução sem giro adicional e depois a ordem estável do catálogo.

A conversão é `cm ÷ 2,54 × 300`, arredondada para o inteiro mais próximo, com empates para cima. Foto e folha são convertidas separadamente; a diferença define o branco. Não é possível reduzir a foto silenciosamente para fazê-la caber.

## Exemplo de produção

| Elemento | Centímetros | Pixels |
| --- | --- | --- |
| Área solicitada | 30 × 36 | 3543 × 4252 |
| Folha comercial 30×40 | 30,5 × 40 | 3602 × 4724 |
| Branco à direita | aproximadamente 0,5 | 59 |
| Branco abaixo | aproximadamente 4 | 472 |

Posição padrão: `(0, 0)`, canto superior esquerdo. Uma solicitação de 36 × 30 cm usa a mesma folha, girando a área pronta em 90°. O recorte continua pertencendo à fotografia.

Para reproduzir com uma imagem sintética, execute `python scripts/example.py --output dist/exemplo-30x36.jpg`. O script recusa sobrescrever um arquivo existente. Para usar pela interface, adicione uma foto, informe 30 e 36, aplique, confira o recorte e exporte.

## Política de cor e JPEG

Pillow normaliza a orientação EXIF antes dos cálculos. Perfis ICC válidos são convertidos para sRGB, com intenção perceptual, seguindo a família de ferramentas existente. RGB sem perfil é interpretado como sRGB e identificado na consulta de metadados. CMYK sem perfil e ICC inválido usam conversão RGB aproximada, com aviso explícito e revisão obrigatória.

Transparência é composta sobre branco opaco. O original permanece byte a byte intacto. Não há aplicação automática de nitidez, filtros, aprimoramento por IA ou compensação da impressora.

O JPEG de produção usa libvips/libjpeg com `Q=100`, subamostragem desabilitada (4:4:4), codificação sequencial, resolução de 300 ppi e perfil sRGB incorporado. Existe uma única codificação JPEG de saída; o intermediário temporário é TIFF sem perdas. Os metadados fotográficos de entrada, inclusive localização e orientação antiga, não são copiados para a saída; são criados os metadados necessários de resolução e cor.

A otimização Huffman fica desabilitada deliberadamente: ela pode armazenar os coeficientes JPEG de toda a folha. Isso muda o tamanho do arquivo, não os valores de qualidade e subamostragem.

O modelo da Noritsu, sua política de entrada de cor, seus ajustes automáticos e a escala de impressão ainda não foram informados. **A aprovação física de tamanho e cor está pendente.** Validar o exemplo na máquina, usando a medida real da folha e sem ajuste automático de escala, antes de liberar a produção. Um JPEG correto em pixels e metadados não garante sozinho a escala ou a cor da impressão.

[← Medidas Editor](../README.md)
