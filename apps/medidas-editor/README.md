<p align="center"><img src="docs/images/banner.svg" alt="Medidas Editor — sua foto, na medida certa" width="100%"></p>

<p align="center"><a href="https://github.com/redlab-coder/redlab-editor/releases/download/medidas-v1.0.0/MedidasEditor-Setup-1.0.0.exe"><img src="docs/images/download.svg" alt="Baixar Medidas Editor para Windows" width="252" height="54"></a><br><sub>Windows 10 e 11 · 64 bits · Instalação sem administrador</sub></p>

![Área de trabalho do Medidas Editor](docs/images/workspace.png)

Prepare fotografias em medidas personalizadas, escolha a menor folha comercial compatível e exporte um JPEG por imagem, com fundo branco, zero margem adicional e 300 dpi.

1. Adicione suas fotos e informe a largura e a altura em centímetros.
2. Ajuste o enquadramento e confira os recortes pendentes.
3. Exporte o JPEG ou o ZIP com os arquivos individuais.

**Foto de 30 × 36 cm → folha comercial 30×40 → arquivo de 30,5 × 40 cm.** A fotografia mantém sua área de 30 × 36 cm; o branco fica nas sobras da folha. O padrão é o canto superior esquerdo.

- 27 folhas oficiais, com nome comercial separado da medida real.
- Medidas com vírgula ou ponto e cálculo proporcional quando uma dimensão é informada.
- Preencher com recorte ou conter a imagem inteira, sem deformação.
- Folha automática ou manual, considerando giro de 90° e encaixe físico.
- Medidas e enquadramento individuais ou aplicação do mesmo tamanho a uma seleção.
- Prévia leve, avisos de resolução e exportação sequencial com progresso e cancelamento.
- Lotes salvos em `.medidas`, contendo cópias dos originais e os ajustes.
- Funcionamento local; as fotos não são enviadas a um servidor externo.

Saída JPEG com qualidade 100, cor 4:4:4, resolução de 300 ppi e perfil sRGB incorporado. Perfis ICC válidos são convertidos para sRGB; falhas de perfil são informadas. A política de entrada da Noritsu e a impressão de validação de escala e cor ainda precisam ser confirmadas na REDLAB.

[Guia de uso](docs/usage.md) · [Medidas, cor e impressão](docs/printing.md) · [Desenvolvimento](docs/development.md) · [Validação](docs/validation.md) · [Publicação](docs/releases.md) · [Versão portátil](https://github.com/redlab-coder/redlab-editor/releases/download/medidas-v1.0.0/MedidasEditor-Portable.exe)

[← Todas as ferramentas RedLab](../../README.md)
