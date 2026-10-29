# Recursos de terceiros

O Medidas Editor usa os componentes abaixo. Seus avisos e licenças de distribuição acompanham os metadados dos pacotes no executável; esta lista não substitui essas licenças.

| Componente | Uso | Origem |
| --- | --- | --- |
| Python | Runtime | https://www.python.org/ |
| Pillow | Leitura, EXIF, perfis ICC e prévias | https://python-pillow.github.io/ |
| pyvips 3.2.0 | Binding do exportador | https://github.com/libvips/pyvips |
| pyvips-binary 8.18.7 / libvips | Processamento sob demanda e encoder JPEG | https://github.com/libvips/pyvips-binary |
| CFFI | Integração com biblioteca nativa | https://cffi.readthedocs.io/ |
| pystray | Bandeja Windows | https://github.com/moses-palmer/pystray |
| PyInstaller | Empacotamento | https://pyinstaller.org/ |
| Inno Setup | Instalador | https://jrsoftware.org/isinfo.php |

libvips é distribuída sob LGPL-2.1-or-later; o pacote binário inclui bibliotecas de terceiros com suas próprias licenças. Consulte o [projeto e fontes da libvips](https://github.com/libvips/libvips) e os [scripts de compilação do pacote binário](https://github.com/libvips/pyvips-binary). A biblioteca dinâmica distribuída mantém sua identidade e não recebe alterações neste projeto.

Ícones e banners do aplicativo são vetores próprios da família RedLab. Imagens das capturas são demonstrações sintéticas, não fotografias de clientes.

O painel da bandeja usa [Tkinter](https://docs.python.org/3/library/tkinter.html) e os componentes Tcl/Tk distribuídos com o Python. Seus recursos são incluídos pelo empacotador e conservam os avisos e licenças de origem. Os ícones da família são vetores próprios, gerados por `branding.py`; não há fontes adicionais distribuídas para desenhá-los.
