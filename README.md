## Alguns scripts para a instalação do Mola
Eu estou trabalhando em alguns scripts Python para interfacear a Grove Vision AI V2 com uma Orange Pi 3LTS via serial.
Para isso, utilizei as bibliotecas python-sscma, open-cv, python-boleto

* Primeiro eu utilizei a biblioteca python-boleto para gerar uma série aleatória de boletos no meu nome (como pagador);
* Depois eu converti todos os PDFs em Imagens PNG e salvei na pasta images_png
* As três variações de script realizam operações diferentes: boleto.py checa as dimensões e posição das bounding boxes e
  posiciona um boleto aleatório com dimensões proporcionais ao da pessoa detectada. boleto_silhueta.py, faz o mesmo que o
  anterior, mas usa uma máscara de vídeo sobre a imagem do boleto. E por fim, boleto_videofeed.py exibe o feed de video
  da GroveVision AI V2.

  
