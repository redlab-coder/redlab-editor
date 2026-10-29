# Validação da integração

## Medidas Editor 1.0.1 — interface

A interface passou a mostrar miniaturas da composição na Preparação e uma prévia ampliada. O download permanece automático, com progresso e cancelamento discretos. Foram removidos o painel persistente de arquivos prontos e as explicações repetidas.

Validação: 32 testes de unidade/API e quatro contratos do repositório, além dos fluxos do executável real. A galeria foi verificada com 12 imagens: carregamento sob demanda, fila única, cache reutilizado ao conferir, invalidação após mudar posição, branco da folha, ampliação, exportação e liberação de recursos. Testes de cancelamento, falhas individuais, projetos e telas de 320 a 1440 pixels também cobrem o novo fluxo.

O workflow de [publicação 1.0.1](https://github.com/redlab-coder/redlab-editor/releases/tag/medidas-v1.0.1) exige novamente motor, maior formato, executável e instalação no Windows. O motor de impressão e os canais dos outros editores foram preservados.

## Medidas Editor — 26/10/2026

O terceiro aplicativo passou por 31 testes de processamento, geometria, fila, API, projetos, integração Windows e atualizador. Os quatro testes atuais do repositório também passaram, incluindo o isolamento do novo canal e a regressão do motor de impressão do Bottons.

Os testes de interface foram executados no programa compilado, cobrindo o exemplo de 30 × 36 cm, medidas por seleção, revisão, lote salvo, arraste, troca de abas, limpeza, falhas individuais, cancelamento real do formato máximo e telas estreitas. Instalação, atualização ao encerrar e desinstalação foram verificadas no Windows isolado. As verificações de Bottons e Polaroid também passaram na integração; seus motores e versões publicadas foram preservados.

O formato de 61 × 250 cm foi gerado de fato com 7205 × 29528 pixels e 300 ppi, usando processamento por partes. Medições e condições do cenário estão na [validação do Medidas Editor](../apps/medidas-editor/docs/validation.md).

Evidência: [integração aprovada](https://github.com/redlab-coder/redlab-editor/pull/1) · [pipeline da publicação 1.0.0](https://github.com/redlab-coder/redlab-editor/actions/runs/40372404776).

**Pendente:** validação física de escala e cor na Noritsu e definição de seu modelo/política de entrada de cor. A saída inicial é JPEG sRGB com ICC, qualidade 100, 4:4:4 e 300 ppi.

## Integração inicial — 20/10/2026

20/10/2026. Versões publicadas: Bottons Editor 1.1.0 e Polaroid Editor 1.1.2.

- **71 testes distintos** de API, processamento, armazenamento, lotes, integração com Windows e contratos de publicação aprovados localmente: 33 do Bottons, 35 do Polaroid e 3 da integração.
- Os quatro gabaritos do Bottons produziram os mesmos pixels que o motor preservado do Moldura nos casos de regressão, incluindo ajustes, rotação e composição das folhas.
- Os executáveis passaram nos testes de navegador, importação, edição, filtros, exportação, troca de abas, limpeza e telas estreitas. O Polaroid manteve suas verificações específicas de conferência e preenchimento branco; o Bottons permaneceu sem conferência.
- Instalação, instância única, atualização ao encerrar e desinstalação aprovadas no Windows do GitHub Actions. A migração real de uma compilação do Moldura histórico para Bottons Editor também passou, incluindo troca de executável e atalhos.
- Releases e canais públicos verificados. Os instaladores das releases de transição nos repositórios anteriores têm o mesmo tamanho e SHA-256 dos instaladores aprovados no monorepo. Os manifestos públicos passaram nos validadores dos respectivos clientes antigos e novos.
- Links locais da documentação e banners revisados. Capturas usam conteúdo de demonstração, sem fotografias de clientes.

Evidência de publicação: [Bottons Editor](https://github.com/redlab-coder/redlab-editor/actions/runs/39481393608) · [Polaroid Editor](https://github.com/redlab-coder/redlab-editor/actions/runs/39481393793).

Os testes automatizados usam imagens sintéticas e cenários definidos; não cobrem todas as combinações possíveis de arquivos, drivers e computadores.

## Etapa 1 — encerramento (29/10/2026, em desenvolvimento)

Validação local com os três aplicativos em processos isolados no Windows, usando a bandeja real e a interface no Edge: fechar com fotos carregadas, sem diálogo; fechar com o cache deliberadamente ocupado; fechar durante uma exportação real de 61 × 250 cm no Medidas; verificar término do processo e indisponibilidade da porta local. O teste aciona o callback real do menu pela janela pertencente ao processo de teste. Não acessa instalações ou fotos do operador.

Comando: `apps/medidas-editor/.venv/Scripts/python.exe scripts/check_shutdown.py`. Os workflows executam o mesmo teste por produto antes da compilação. Os testes da API, processamento e distribuição continuam obrigatórios. A publicação dos instaladores atualizados fica para a etapa de entrega prevista no plano; os canais públicos não foram alterados nesta etapa.

## Etapa 2 — Bottons por imagem e lote (em desenvolvimento)

40 testes locais do Bottons aprovados: inclui planejamento físico, posições antigas, todas as combinações dos quatro modelos até cinco imagens, lotes aleatórios de 100 itens, colisões, limites, modelo e ajustes por foto, arquivos de lote inválidos e recuperação dos originais. O caso de um quadrado e dois P gera uma única folha de 1795 × 1205 pixels a 300 DPI.

No navegador, a exportação antes e depois de salvar/reabrir `.bottons` produziu JPEGs idênticos. O download da folha ampliada também foi idêntico ao da exportação completa de uma folha mista. Foram verificados modelo individual, preservação de zoom, sessão legada com modelo global, falha de abertura sem substituir o lote, troca entre abas e telas de 320 a 1440 pixels. O workflow exige ainda compilação, executável e instalador no Windows antes da integração. Versões e canais públicos permanecem preservados até a etapa final de publicação.
