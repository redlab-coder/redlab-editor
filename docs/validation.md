# Validação da integração

20/10/2026. Versões publicadas: Bottons Editor 1.1.0 e Polaroid Editor 1.1.2.

- **71 testes distintos** de API, processamento, armazenamento, lotes, integração com Windows e contratos de publicação aprovados localmente: 33 do Bottons, 35 do Polaroid e 3 da integração.
- Os quatro gabaritos do Bottons produziram os mesmos pixels que o motor preservado do Moldura nos casos de regressão, incluindo ajustes, rotação e composição das folhas.
- Os executáveis passaram nos testes de navegador, importação, edição, filtros, exportação, troca de abas, limpeza e telas estreitas. O Polaroid manteve suas verificações específicas de conferência e preenchimento branco; o Bottons permaneceu sem conferência.
- Instalação, instância única, atualização ao encerrar e desinstalação aprovadas no Windows do GitHub Actions. A migração real de uma compilação do Moldura histórico para Bottons Editor também passou, incluindo troca de executável e atalhos.
- Releases e canais públicos verificados. Os instaladores das releases de transição nos repositórios anteriores têm o mesmo tamanho e SHA-256 dos instaladores aprovados no monorepo. Os manifestos públicos passaram nos validadores dos respectivos clientes antigos e novos.
- Links locais da documentação e banners revisados. Capturas usam conteúdo de demonstração, sem fotografias de clientes.

Evidência de publicação: [Bottons Editor](https://github.com/redlab-coder/redlab-editor/actions/runs/39481393608) · [Polaroid Editor](https://github.com/redlab-coder/redlab-editor/actions/runs/39481393793).

Os testes automatizados usam imagens sintéticas e cenários definidos; não cobrem todas as combinações possíveis de arquivos, drivers e computadores.
