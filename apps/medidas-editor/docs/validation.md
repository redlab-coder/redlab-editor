# Validação — Medidas Editor 1.0.0

26/10/2026. Referência de publicação: tag `medidas-v1.0.0`.

- 30 testes locais de geometria, processamento, cor, fila, API, projetos, integração Windows e atualizador aprovados.
- Quatro testes do repositório aprovados, incluindo o contrato do terceiro produto e a regressão de impressão do Bottons contra o Moldura preservado.
- Exemplo real de 30 × 36 cm exportado como 3602 × 4724 pixels, 300 ppi, JPEG qualidade 100/4:4:4 e ICC sRGB. A composição da foto é 3543 × 4252, deixando 59 pixels à direita e 472 abaixo. Original preservado byte a byte.
- Seleção decimal exata, casos de não encaixe, giro de acomodação após recorte, proporção, modo inteira, EXIF, perfis inválidos, transparência e resolução efetiva cobertos.
- Testes de navegador aprovados no executável real: importação inválida sem interromper as demais fotos, arraste ampliado, medidas por seleção, revisão, projetos, recarregamento, troca repetida entre abas, reversão do arraste no limite, cancelamento de uma exportação máxima, limpeza com falha e recuperação, liberação de recursos e telas de 320 a 1440 pixels.
- Exportação real de 61 × 250 cm: 7205 × 29528 pixels, 300 ppi, aproximadamente 98,5 MiB de pico de memória residente e 14,26 segundos na execução local registrada. Entrada sintética RGB de 1220 × 5000 pixels. O teste inspeciona a saída em blocos; não a decodifica inteira em outro buffer. Os números não representam o consumo de todas as entradas possíveis.
- Links locais revisados e capturas feitas com conteúdo sintético.

A publicação exige também instalação, instância única, atualização ao encerrar e desinstalação no Windows isolado do GitHub Actions. O workflow reexecuta os testes e publica somente os arquivos aprovados.

**Pendente:** impressão na Noritsu para confirmar tamanho físico, escala e cor, além da definição do modelo da máquina e de sua política de entrada de cor. As verificações digitais não substituem essa aprovação física.

[Medidas Editor](../README.md) · [Impressão](printing.md)
