# Publicação e atualização

| Aplicativo | Pasta | Tag | Canal |
| --- | --- | --- | --- |
| Bottons Editor | `apps/bottons-editor` | `bottons-v1.2.0` | `updates/bottons-editor.json` |
| Polaroid Editor | `apps/polaroid-editor` | `polaroid-v1.2.0` | `updates/polaroid-editor.json` |
| Medidas Editor | `apps/medidas-editor` | `medidas-v1.1.0` | `updates/medidas-editor.json` |

Cada produto mantém sua própria versão em `version.py`. Atualize também o changelog, as notas, os links de download e a versão padrão do instalador antes de criar uma tag. As tags têm prefixos distintos para impedir que uma atualização de um aplicativo seja oferecida ao outro.

O workflow correspondente testa e compila no Windows antes da publicação. `scripts/publish.py` valida produto, tag, origem, tamanho e SHA-256; publica instalador, portátil, manifesto e checksums; confere os arquivos enviados; só então avança o canal desse produto. O canal não aceita regressão de versão nem troca do instalador de uma versão já publicada. O README aponta para releases explícitas, pois o conceito global de “latest” não representa vários produtos independentes.

Se uma publicação falhar, examine o workflow e a release antes de retomar. Uma release pública deve permanecer imutável. Corrija o problema em uma nova versão quando os arquivos públicos precisarem mudar. O canal pode ser retomado com `update_feed` apenas usando o manifesto da release pública já verificada.

## Transição dos repositórios anteriores

Os clientes antigos consultam o `update.json` da release mais recente de seu repositório original e exigem o formato de URL anterior. Por isso, cada repositório recebe uma release de transição com o instalador aprovado do monorepo, preservando o contrato antigo no manifesto. No Moldura, o nome do arquivo oferecido ao atualizador antigo continua `Moldura-Setup-1.1.0.exe`; seu conteúdo instala o Bottons Editor.

O Bottons Editor mantém o AppId do Moldura para atualizar a instalação existente, remove o executável e os atalhos antigos e passa a usar sua nova identidade e canal. Uma instalação nova usa a pasta Bottons Editor. O Polaroid Editor preserva sua identidade instalada e troca somente a origem de suas atualizações.

Os repositórios anteriores são históricos após essa transição; não devem continuar gerando releases independentes. Preserve seus commits, tags, downloads e a release de transição. O teste `scripts/check_migration.py` verifica a passagem do Moldura para Bottons Editor em uma conta Windows isolada.

## Atualização com reinício

A versão instalada verifica o canal ao iniciar e a cada 30 minutos; falhas de conexão ou download são tentadas novamente após 5 minutos. O download ocorre em segundo plano, com validação de produto, versão, origem, tamanho e SHA-256. O menu da bandeja não precisa oferecer uma verificação manual.

Quando o instalador está verificado, a interface oferece **Atualizar e reiniciar**. Se houver importação, exportação ou manipulação da imagem em andamento, a ação aguarda sua conclusão. Antes de encerrar, o aplicativo grava uma cópia local dos originais, ajustes e estado da interface em `%LOCALAPPDATA%/<Aplicativo>/updates/recovery`. A escrita é atômica e uma falha mantém o editor aberto.

O instalador aguarda o processo encerrar e reabre somente a ferramenta atualizada. A nova sessão recupera o lote, os modelos individuais, os recortes, a seleção e, no Medidas, os campos ainda não aplicados. A cópia permanece até a interface confirmar a recuperação. Se a instalação ou a reabertura falhar, ela continua disponível ao abrir o programa novamente; não há promessa de reversão automática de uma instalação interrompida. Uma falha na leitura informa onde a cópia foi preservada.

A atualização ao encerrar normalmente continua disponível. O reinício com recuperação é solicitado pelo botão da interface; não é um salvamento geral de sessões ao fechar. A edição portátil e a execução isolada não instalam atualizações nem acessam cópias da instalação do operador.

Os guias de uso apontam para [instalação e atualizações](updates.md). O catálogo sempre usa links explícitos por produto; a indicação global Latest do GitHub representa somente uma release e não substitui os três canais.
