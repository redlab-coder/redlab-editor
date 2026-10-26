# Desenvolvimento

Aplicativo desktop local em Python, Pillow e HTML/CSS/JavaScript, com a mesma família visual, bandeja, instância única, autenticação de loopback e distribuição dos outros editores RedLab. Não é uma publicação web multiusuário.

| Módulo | Responsabilidade |
| --- | --- |
| `formats.json` | Catálogo oficial único |
| `engine.py` | Precisão decimal, seleção da folha, geometria, cor, prévia e exportação |
| `photo_store.py` | Bytes originais imutáveis, metadados e proxies reduzidos |
| `jobs.py` | Fila única, progresso, cancelamento, nomes e falhas individuais |
| `projects.py` | Lotes `.medidas`, com limites, hashes e validação |
| `app.py` | API local autenticada e ciclo de vida |
| `ui/` | Interface, interação e exclusividade de edição entre abas |
| `desktop.py`, `updater.py` | Integração Windows e atualização verificada |

## Dependência de exportação

Pillow permanece no tratamento de entrada/ICC e nas prévias. Uma folha máxima tem 7205 × 29528 pixels: um único buffer RGB do Pillow pode ocupar aproximadamente 812 MiB, antes de cópias e do original. Foi acrescentado `pyvips[binary]` para executar a composição e a codificação JPEG sob demanda, por partes.

O Windows recebe a libvips junto ao executável; não existe instalação manual de bibliotecas pelo operador. Isso aumenta o tamanho do pacote e exige os avisos/licenças indicados em [THIRD-PARTY.md](../THIRD-PARTY.md).

O original é normalizado um por vez para TIFF temporário; a folha final não é montada em um canvas de resolução completa. O cache de operações libvips é desativado, seu cache de memória é limitado a 32 MiB e são usadas duas threads internas. A fila exporta um item de cada vez. O JPEG é gravado em arquivo temporário e disponibilizado somente depois de concluído. O download de exportações é transmitido diretamente ao gerenciador do navegador por uma URL local com chave por tarefa; a interface não monta o ZIP completo em um Blob JavaScript.

O teste real do formato máximo monitora memória do processo e inspeciona pequenos blocos do resultado, evitando decodificar a folha inteira no próprio teste. O consumo também depende da entrada: normalizar uma fotografia de 60 megapixels demanda mais memória que o arquivo sintético usado no teste. Espaço em disco é verificado antes da exportação.

## Executar e validar

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-build.txt playwright==1.59.0
.venv/Scripts/python.exe app.py
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe tests/large_export_check.py
```

Os testes de navegador usam Microsoft Edge e uma instância isolada. `tests/packaged_check.py` abre o executável real, valida a instância única, executa os fluxos do produto e encerra somente o processo de teste. `tests/installer_check.py` verifica instalação, atualização ao encerrar e desinstalação em conta Windows isolada e recusa substituir uma instalação existente.

```powershell
./scripts/bootstrap_inno.ps1
.venv/Scripts/python.exe scripts/build_windows.py
.venv/Scripts/python.exe tests/packaged_check.py dist/MedidasEditor-Portable.exe
```

As capturas públicas são geradas por `tests/browser_check.py` com imagens sintéticas. Nunca incluir fotos de clientes no repositório. O teste físico na Noritsu permanece separado e pendente.

[← Medidas Editor](../README.md)
