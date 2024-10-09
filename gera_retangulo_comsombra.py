import os
import random
import time
import threading
import pygame
from PIL import Image, ImageFilter

class ImageFiller:
    def __init__(self, x, y, width, height, fps, pasta_imagens):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.fps = fps
        self.pasta_imagens = pasta_imagens
        self.imagens = [os.path.join(pasta_imagens, img) for img in os.listdir(pasta_imagens) if img.endswith('.png')]
        self.intervalo = 1 / fps
        self.stop_thread = False

        # Inicializar o Pygame
        pygame.init()
        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)  # Tela cheia
        self.retangulo = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 255))

    def update(self, x=None, y=None, width=None, height=None, fps=None):
        """Atualiza dinamicamente os parâmetros de posição e tamanho do retângulo."""
        if x is not None:
            self.x = x
        if y is not None:
            self.y = y
        if width is not None:
            self.width = width
        if height is not None:
            self.height = height
        if fps is not None:
            self.fps = fps
            self.intervalo = 1 / fps

    def stop(self):
        """Encerra a thread."""
        self.stop_thread = Trueshadow = shadow.filter(ImageFilter.GaussianBlur(2))  # Adicionar desfoque

    def create_shadow(self, img, angle):
        """Cria uma sombra para a imagem rotacionada."""
        shadow = img.copy()
        shadow = shadow.filter(ImageFilter.GaussianBlur(2))  # Adicionar desfoque
        shadow = shadow.convert("RGBA")
        
        # Rotacionar a sombra
        shadow = shadow.rotate(angle, expand=True)
        
        return shadow

    def fill(self):
        """Função que preenche o retângulo com imagens sobrepostas."""
        while not self.stop_thread:
            # Calcular os limites de tamanho das imagens
            min_area = int(0.2 * self.width * self.height)  # 10% da área total
            max_area = int(0.4 * self.width * self.height)  # 60% da área total

            # Escolher uma imagem aleatória da pasta
            img_path = random.choice(self.imagens)
            imagem = Image.open(img_path).convert('RGBA')

            # Calcular a área aleatória entre os limites
            area = random.randint(min_area, max_area)

            # Calcular nova largura e altura mantendo a proporção
            aspect_ratio = imagem.height / imagem.width
            new_width = int((area / aspect_ratio) ** 0.5)
            new_height = int(new_width * aspect_ratio)

            # Redimensionar a imagem
            imagem = imagem.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Aplicar rotação aleatória
            angle = random.randint(-60, 60)
            imagem = imagem.rotate(angle, expand=True)

            # Criar sombra
            shadow = self.create_shadow(imagem, angle)

            # Calcular coordenadas aleatórias para posicionar a imagem dentro do retângulo
            pos_x = random.randint(0, max(0, self.width - new_width))
            pos_y = random.randint(0, max(0, self.height - new_height))

            # Colocar a sombra e a imagem no retângulo
            self.retangulo.paste(shadow, (pos_x, pos_y + 10), shadow)  # Colocar sombra abaixo
            self.retangulo.paste(imagem, (pos_x, pos_y), imagem)

            time.sleep(self.intervalo)

    def display(self):
        """Função para exibir as imagens usando Pygame."""
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q:  # Sair ao pressionar 'q'
                        running = False

            # Preencher a tela com preto
            self.screen.fill((0, 0, 0))

            # Converter a imagem PIL para Surface do Pygame
            mode = self.retangulo.mode
            size = self.retangulo.size
            data = self.retangulo.tobytes()
            pygame_image = pygame.image.fromstring(data, size, mode)

            # Blitar a imagem no retângulo especificado
            self.screen.blit(pygame_image, (self.x, self.y))

            pygame.display.flip()  # Atualizar a tela
            time.sleep(self.intervalo)

        pygame.quit()

# Exemplo de uso:
if __name__ == "__main__":
    pasta_imagens = 'images_png'  # Caminho para a pasta com imagens
    filler = ImageFiller(x=100, y=100, width=600, height=400, fps=30, pasta_imagens=pasta_imagens)
    
    # Iniciar a thread que preenche o retângulo
    filler_thread = threading.Thread(target=filler.fill)
    filler_thread.start()

    # Exibir as imagens
    filler.display()

    # Finalizar a thread após 15 segundos
    filler.stop()
    filler_thread.join()
