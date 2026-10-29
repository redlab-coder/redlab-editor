# Pacote completo RedLab Editor

[Baixar para Windows](https://github.com/redlab-coder/redlab-editor/releases/download/redlab-v1.0.0/RedlabEditor-Setup-1.0.0.exe)

Um único instalador reúne Bottons Editor, Polaroid Editor e Medidas Editor. Depois do download, a instalação funciona sem internet. Requer Windows 10 ou 11 de 64 bits e não exige administrador.

1. Salve seu trabalho e encerre os editores que serão instalados.
2. Abra `RedlabEditor-Setup-1.0.0.exe`.
3. Mantenha **Pacote completo** ou escolha as ferramentas desejadas.
4. Escolha se deseja atalhos na área de trabalho e instale.
5. Abra a ferramenta pela pasta **RedLab Editor** do menu Iniciar.

O pacote 1.0.0 inclui Bottons 1.2.1, Polaroid 1.2.1 e Medidas 1.1.1. Também é possível baixar [cada editor separadamente](../README.md#downloads-individuais).

## Instalações existentes

O instalador reutiliza a pasta e a identidade de cada editor. Versões anteriores são atualizadas; versões iguais podem ser reparadas. Uma versão mais recente que a incluída no pacote é preservada. Por isso, um editor preservado mantém seus próprios atalhos e configurações de instalação.

Se um editor selecionado estiver aberto ou outro instalador desse editor estiver em execução, o pacote solicita que ele seja encerrado antes de alterar qualquer ferramenta. Um editor aberto que não foi selecionado pode continuar em uso.

## Atualizar e remover

Cada editor continua usando seu próprio canal e o botão **Atualizar e reiniciar**. Não é preciso baixar o pacote novamente para receber uma atualização individual. O pacote tem versão própria; ela identifica uma combinação de instaladores estáveis, não a versão de cada ferramenta.

Para remover uma ferramenta, use **Aplicativos instalados** nas configurações do Windows. As demais continuam instaladas. O pacote não adiciona um quarto aplicativo, serviço ou atualizador.

## Se houver uma falha

O resultado identifica a ferramenta que falhou e mantém as demais instalações concluídas. Não há reversão automática do conjunto. Você pode corrigir a causa e executar o pacote novamente ou usar o instalador individual.

Os registros ficam em `%LOCALAPPDATA%\RedLab Editor\Setup`. Uma instalação parcial retorna código diferente de zero para automações. Não há download de componentes durante a instalação.
