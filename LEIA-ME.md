# VoxelSprite Studio 2.0 — Python Edition

Editor desktop de voxels e pixel art 3D, com interface escura, ferramentas à esquerda, opções à direita e câmeras na base, inspirado na referência visual do PixZels fornecida pela usuária. O aplicativo é uma implementação independente em Python: usa identidade, ícones e banner próprios.

## Abrir no Windows

1. Instale **Python 3.12 ou 3.13 de 64 bits** de https://www.python.org/downloads/windows/ e marque **Add python.exe to PATH**. Python 3.10–3.11 também é aceito.
2. Extraia **todo o ZIP em uma nova pasta**. Não execute de dentro do ZIP e não misture com os arquivos de versões anteriores.
3. Dê dois cliques em **iniciar_windows.bat**.
4. Na primeira abertura, aguarde a instalação das dependências. Precisa de internet nessa etapa; depois, o aplicativo funciona localmente.
5. Clique em **EXEMPLOS** para experimentar uma personagem de quatro vistas, um cogumelo ou uma árvore. Ou escolha **IMPORTAR VISTAS** para começar com sua arte.

O pacote contém o código-fonte. Não é um EXE pronto. O iniciador cria a pasta `.venv` localmente; não exige administrador. Se mover a pasta do aplicativo, apague somente `.venv` e deixe o iniciador recriá-la.

## Começar um modelo vazio

O aplicativo abre com uma grade vazia. Selecione **Adicionar (V)** e clique no chão da grade. O primeiro voxel aparece. Clique em suas faces para adicionar mais volume. Botão direito gira a câmera; botão do meio move; rodinha aproxima.

Escolha um tamanho de grade e clique em **APLICAR TAMANHO** para ampliar a área editável. Isso recentraliza o volume e reinicia o histórico. Uma redução que cortaria voxels é recusada. O tamanho real atual aparece na barra inferior; o seletor é o tamanho solicitado para a próxima aplicação.

## Ferramentas

| Ferramenta | Tecla | Uso |
| --- | --- | --- |
| Pintar | P | Clique ou arraste nas faces visíveis. Cada voxel tem seis cores independentes. |
| Adicionar | V | Adiciona voxels sobre a face atingida. Em espaço vazio, clique no chão. |
| Apagar | E | Remove voxels inteiros. |
| Conta-gotas | I | Captura a cor original da face, sem a iluminação. |
| Selecionar | M | Arraste um retângulo; clique simples seleciona um voxel. |
| Balde | B | Preenche a região de faces coplanares, conectadas e da mesma cor. |
| Navegar | H | Arraste com o botão esquerdo para girar sem editar. |

**TAMANHO** define a largura do pincel quadrado, de 1 a 16 voxels, no plano da face clicada. **OPAC. %** mistura a cor do pincel com a cor existente; não torna o voxel semitransparente. Adição de geometria usa a cor sólida atual.

**Shift + clique** ao pintar, adicionar ou apagar cria uma linha desde o último ponto, quando a orientação da face é a mesma. A linha percorre a grade entre os pontos; em curvas ou degraus pode deixar intervalos porque só edita as faces alcançadas nessa projeção. **Alt + clique** captura cor temporariamente. **Ctrl + clique** na ferramenta Pintar apaga voxels. Esses modificadores não substituem as ferramentas principais.

O pincel mostra a face central atingida. A prévia não desenha toda a área de um pincel largo nem uma linha antes de clicar. Ao adicionar, não é possível ultrapassar a grade: amplie-a antes.

### Seleção, mover e copiar

- O retângulo seleciona os centros dos voxels dentro dele, **incluindo as profundidades escondidas**. Não é uma seleção apenas da superfície visível.
- Shift adiciona voxels à seleção existente. Ctrl+A seleciona tudo. Esc solta a seleção.
- Com uma seleção ativa, pintar/apagar/adicionar/balde ficam restritos às origens selecionadas. Adicionar pode criar o voxel vizinho fora da seleção.
- Na ferramenta Selecionar, **Shift + arraste sobre um voxel já selecionado** move a seleção no plano da câmera. **Ctrl + arraste** cria uma cópia. O contorno mostra o deslocamento aproximado antes de soltar.
- **MOVER / COPIAR** abre deslocamentos numéricos em X, Y e Z, com opção de cópia. X positivo = direita da frente; Y positivo = cima; Z positivo = frente.
- Destinos que já contêm outros voxels e movimentos para fora da grade são recusados, sem sobrescrever o modelo.
- Delete ou **APAGAR SELEÇÃO** remove os voxels selecionados.
- Ctrl+Z desfaz. Ctrl+Y ou Ctrl+Shift+Z refaz. O histórico cobre pincel, balde, adição, remoção e mover/copiar.

O histórico tem limite de 80 operações e cerca de 150 mil entradas de voxels alterados, mantendo ao menos a operação mais recente. Importar, abrir projeto, criar modelo e redimensionar grade reiniciam esse histórico.

## Importar até seis vistas

Clique em **IMPORTAR VISTAS**. Carregue arquivos separados de frente, costas, esquerda, direita, topo e base; **qualquer combinação não vazia é aceita**. A frente é recomendada, mas não obrigatória. Se faltar, o programa estima uma referência a partir da primeira vista disponível.

O volume é a interseção das silhuetas fornecidas: um voxel só permanece onde todas as vistas permitem. As faces recebem as cores da imagem correspondente. Nas vistas ausentes, use cores dominantes ou repetição da frente; uma lateral ausente pode receber as cores da oposta. A matemática não consegue recuperar detalhes escondidos que você não desenhou.

### Preparação e orientação

- Prefira PNG RGBA com fundo transparente. JPG e outras imagens opacas formam blocos preenchidos. Não há remoção automática de fundo.
- Use vistas ortográficas retas. Imagens em perspectiva ou isométricas não são entradas equivalentes.
- Alinhe cabeça/pés e mantenha escala e margens transparentes compatíveis. As telas inteiras são projetadas; cada vista não é recortada separadamente.
- Frente e costas: topo da imagem = topo do objeto. As costas são vistas de fora; o programa inverte a coordenada horizontal automaticamente. Não espelhe manualmente.
- Lateral direita significa a câmera do lado +X do modelo, à direita da imagem frontal, não o lado anatômico do personagem. A frente do personagem aponta para a esquerda nessa imagem. Na lateral esquerda, aponta para a direita.
- Topo: frente do objeto na parte **inferior** da imagem. Base: frente na parte **superior**. Ambas mantêm +X à direita.
- Resolução limita a imagem-base a até 128 pixels. Profundidade admite 1–64 camadas. Laterais são adaptadas para profundidade × altura; topo/base, para largura × profundidade. Usa vizinho mais próximo e pode alterar proporções se as telas não corresponderem.
- Para preservar proporções de uma lateral, use aproximadamente `profundidade = largura da lateral × altura final da frente / altura da lateral`.
- Arredondamento só atua sem lateral, topo ou base. Com essas vistas, a geometria desenhada tem prioridade.
- Corte alfa descarta pixels abaixo do valor escolhido. Os demais são sólidos.

A importação deixa uma margem de quatro voxels para editar ao redor. Se precisar, aumente a grade. Há limites de um milhão de voxels e 400 mil faces externas por modelo.

### Arquivos em folha

Esta versão importa **PNGs separados**, não recorta sprite sheets automaticamente. A exportação ortográfica gera os seis arquivos separados e uma folha adicional `six_views.png`; para reconstruir, carregue os seis arquivos separados.

Reconstruir a partir de silhuetas pode perder cavidades que nenhuma vista consegue revelar. Para preservar exatamente o modelo editado, use **Salvar projeto**.

## Editar as vistas em pixels (3D ORTHO)

**3D ORTHO · EDITAR 2D** abre as seis projeções atuais em abas. Você pode pintar com pincel, apagar pixels, preencher com balde e capturar cor. Cada aba tem desfazer/refazer local (30 etapas), zoom de 2× a 24× e uma opção para participar da reconstrução.

Em um projeto vazio, pinte uma vista para começar; ela é ativada automaticamente. Vistas vazias são ignoradas. No modelo já existente, desative as vistas que não devem restringir suas novas formas. Reconstruir substitui o volume pelo resultado da interseção das vistas ativas e reinicia o histórico 3D. Salve antes se quiser preservar cavidades e detalhes escondidos.

O editor 2D suporta as grades de até 128 pixels de largura/altura e até 64 de profundidade. Em grades maiores, o programa pede para reduzir o tamanho antes. Pintura 2D é sólida; o controle de opacidade da janela principal é da pintura 3D.

## Visualização

- **Botão direito:** girar. **Botão do meio ou Espaço + botão esquerdo:** mover. **Rodinha:** zoom.
- **ENQUADRAR:** recentraliza e ajusta o zoom.
- Botões S/SO/O/NO/N/NE/L/SE: oito ângulos com elevação de 30°. São rótulos de órbita, não direções do personagem.
- Seletor da base: isométrica, frente, costas, esquerda, direita, topo e base.
- **Câmera ortográfica:** sem convergência de perspectiva. Desmarque para perspectiva.
- **PIXEL ART 2×/3×:** renderiza a prévia em resolução reduzida, ampliada por vizinho mais próximo. **3D:** resolução total do viewport.
- **Contorno da silhueta:** um pixel da resolução interna, com cor configurável. Não detecta nem destaca todas as arestas internas.
- **Iluminação:** sombreamento direcional simples. Direção e elevação mudam a posição da luz.
- **BG:** muda a cor de fundo da prévia. PNGs exportados permanecem transparentes.

## Salvar e abrir projetos

Ctrl+S ou **SALVAR PROJETO** grava um `.json` com dimensões, ocupação e seis cores por voxel, além das opções de aparência. **Arquivo → Salvar como** cria outra cópia.

Ctrl+O ou **ABRIR PROJETO** reabre um projeto. O formato é próprio do **VoxelSprite Studio 2.0**; **não importa JSON do PixZels** nem OBJ externo. O histórico de desfazer, a seleção e os caminhos dos PNGs de entrada não são salvos.

Ao fechar, criar, abrir ou importar outro modelo, o aplicativo pergunta se você quer salvar alterações pendentes. Não há salvamento automático: salve regularmente.

## Exportações

Abra **EXPORTAR** ou Ctrl+E.

| Opção | Arquivos e comportamento |
| --- | --- |
| OBJ + MTL + atlas PNG | Malha das faces externas, um material e atlas RGB com UVs. Mantenha os três arquivos juntos. |
| PNG do ângulo atual | Imagem transparente, reenquadrada automaticamente em um quadro quadrado, com a orientação atual. |
| Spritesheet 8 direções | Uma linha de oito quadros; começa na frente e aumenta o ângulo da câmera em 45°. |
| Spritesheet 16 direções | Oito colunas e duas linhas; passos de 22,5°. |
| GIF | Rotação completa, 8–64 quadros, duração configurável, paleta de 255 cores mais transparência. |
| 6 vistas ortográficas | Frente/costas/laterais/topo/base em PNG, sem iluminação e sem contorno, e uma folha de referência. |
| RPG Maker | Grade 3×4, com poses estáticas repetidas nas três colunas, ordem frente/+X/−X/costas. **Não gera caminhada.** |

Raster: quadros de 64, 128, 256 ou 512 pixels. Ajuste a elevação nos spritesheets/GIF. Todos os quadros de uma rotação compartilham centro e escala para evitar oscilações. A exportação raster usa projeção ortográfica, mantém iluminação/contorno, remove grade e interface, e reenquadra o modelo inteiro. Não é uma captura literal do zoom/pan da janela.

**GIF** tem as limitações do formato: paleta reduzida e transparência binária. Para cores mais fiéis, use PNG.

**RPG Maker:** use o prefixo `$` no nome de um personagem individual. O tamanho de célula é o escolhido no diálogo. Confira o resultado na versão do RPG Maker que você usa; não foi validado no engine nesta entrega.

**OBJ:** eixo Y para cima, uma unidade por voxel. Sem faces internas. Quads externos são preservados; não há fusão de faces coplanares nem otimização avançada de topologia. O atlas é uma paleta RGB, com amostras no centro das células. No programa de destino, use Material Preview e filtragem nearest quando disponível. Sombras da prévia não são gravadas no atlas.

## Diferenças em relação ao PixZels

Esta versão reproduz a organização geral da referência e implementa as categorias principais de criação e exportação. **Não é uma réplica completa nem possui paridade comprovada de qualidade/desempenho com o PixZels.**

- Marca, banner, ícones, textos e código são próprios.
- Não há planos 2D de desenho suspensos na cena nem manipulação da luz por um ícone dentro do viewport; a entrada é por diálogo e a luz usa sliders.
- Mover/copiar admite Shift/Ctrl + arraste e diálogo numérico; o arraste usa o plano da câmera e pode diferir dos eixos/restrições do PixZels.
- O pincel, o balde, a seleção, o arredondamento e o contorno têm os comportamentos descritos neste guia, não os algoritmos proprietários do outro aplicativo.
- Não há animação de partes do modelo, camadas, importação de OBJ, seleção por laço ou compatibilidade de projetos com PixZels.
- O preset RPG Maker é uma disposição estática, não síntese de quadros de caminhada.
- A prévia combina edição de voxels e redução de resolução; não foi demonstrada equivalência pixel a pixel com o renderizador do PixZels.

Referência pública consultada: https://pixel-salvaje.itch.io/pixzels . O VoxelSprite não é afiliado ao PixZels. A proposta de reconstrução inicial também foi inspirada em https://github.com/GazPrash/2d-to-3d-voxelizer . Nenhum código, logo ou asset desses produtos está incluído.

## Solução de problemas

**Não encontrou Python:** instale Python 3.12/3.13 de 64 bits com PATH. Se houver várias versões, crie a pasta virtual com `py -3.12 -m venv .venv` dentro do projeto e execute o BAT.

**Falha na instalação:** confira internet e espaço livre. Qt ocupa algumas centenas de MB. Para refazer a instalação, remova somente `.venv` e execute o iniciador.

**Erro de OpenGL / prévia preta:** precisa de OpenGL 3.3 e drivers atuais. Sessões remotas e VMs podem limitar esse suporte. Exportação de sprites precisa da prévia funcionando. Conversão, projeto e exportação de geometria usam o motor independente.

**Lento ao editar:** experimente sprites de 32–64 px, profundidade menor e modelos com menos pixels isolados. A malha é refeita ao editar; esta versão não usa atualização por chunks. O limite de faces evita alguns casos excessivos, mas não garante fluidez em qualquer tamanho.

**Partes desaparecem ao importar:** reveja alinhamento e orientação das silhuetas. Frente/costas/laterais/topo precisam descrever o mesmo objeto. Um fundo opaco também muda a interseção.

**Pintura não atua em uma área:** solte a seleção com Esc. Verifique se você está tentando pintar uma face exposta. A área fora da grade não admite adição.

**Erro inesperado:** envie a mensagem exibida e, quando criado, `erro_voxelsprite.log`.

## Desenvolvimento

Dependências: PySide6 6.8.3, ModernGL 5.12.0, NumPy e Pillow. O código do aplicativo é Python; bibliotecas gráficas incluem componentes nativos.

```shell
python -m venv .venv
```

Windows:

```shell
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
.venv\Scripts\python -m unittest discover -s tests -v
```

Linux/macOS:

```shell
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
.venv/bin/python -m unittest discover -s tests -v
```

Linux também precisa das bibliotecas Qt/XCB e OpenGL do sistema, incluindo `libGL.so` para criação de contexto ModernGL.

Módulos: `core.py` (silhuetas/malha), `document.py` (volume/histórico/projeto), `picking.py` (raycast), `scene.py` (render), `viewport.py` (interação), `exports.py`, `dialogs.py`, `style.py`, `ortho_editor.py` e `ui.py`.

Consulte `VALIDACAO.md` para o que foi testado de fato. Não houve execução em Windows nesta sessão.
