import os
import random
import time
import threading
import pygame
import click
from PIL import Image, ImageFilter
from sscma.micro.client import SerialClient
from sscma.micro.device import Device


class BoundingBoxSprite(pygame.sprite.Sprite):
    def __init__(self, x, y, w, h):
        super().__init__()
        self.images = []  # Lista para armazenar múltiplas imagens
        self.rect = pygame.Rect(x, y, w, h)  # Criação do retângulo para o sprite

    def add_image(self, image):
        """Adiciona uma nova imagem à pilha, com um limite máximo."""
        if len(self.images) < 7:  # Limitar a 10 imagens empilhadas
            self.images.append(image)

    def update(self, x, y, w, h):
        """Atualiza a posição e dimensões do sprite."""
        self.rect.topleft = (x, y)
        self.rect.width = w
        self.rect.height = h

    def draw(self, surface):
        """Desenha todas as imagens na pilha no sprite."""
        for img in self.images:
            img_rect = img.get_rect(center=self.rect.center)  # Centralizar a imagem
            surface.blit(img, img_rect)  # Desenha a imagem no centro do retângulo


class ImageFiller:
    def __init__(self, pasta_imagens):        
        # Inicializar atributos
        self.fps = 15
        self.pasta_imagens = pasta_imagens
        self.imagens = [os.path.join(pasta_imagens, img) for img in os.listdir(pasta_imagens) if img.endswith('.png')]
        self.intervalo = 1 / self.fps
        self.stop_thread = False
        self.connected = False  # Sinalizador para indicar se a conexão foi estabelecida
        self.sprites = pygame.sprite.Group()  # Grupo de sprites

        # Inicializar o Pygame
        pygame.init()
        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)  # Tela cheia
        self.screen_info = pygame.display.Info()
        self.rect_w = self.screen_info.current_w
        self.rect_h = self.screen_info.current_h
        self.offset = (self.rect_w - self.rect_h) // 2  # Cálculo do offset para centralizar

    def update(self, port, baudrate):
        """Conecta à porta serial e atualiza as bounding boxes."""
        try:
            client = SerialClient(port, baudrate)
            device = Device(client)

            def on_monitor(device, msg):
                data = msg
                if "image" in data:
                    del data["image"]
                    del data["count"]
                    del data["perf"]
                    del data["resolution"]
                    del data["rotate"]

                if "boxes" in data:
                    bounding_boxes = data["boxes"]
                    for box in bounding_boxes:
                        if box != []:
                            # Extrair as dimensões da bounding box
                            w, h, x, y = box[0], box[1], box[2], box[3]

                            # Ajustar a posição da bounding box com o offset
                            x += self.offset

                            # Verifica se o sprite já existe, caso contrário cria um novo
                            sprite = next((s for s in self.sprites if s.rect.colliderect((x, y, w, h))), None)
                            if not sprite:
                                sprite = BoundingBoxSprite(x, y, w, h)
                                self.sprites.add(sprite)

                            # Criar a imagem do sprite
                            sprite_image, _ = self.create_sprite_image(w, h)
                            sprite.add_image(sprite_image)  # Adiciona a nova imagem à pilha
                            sprite.update(x, y, w, h)  # Atualiza a posição do sprite

                    # Manter os sprites que estão nas listas de bounding boxes
                    for sprite in self.sprites:
                        if not any(sprite.rect.colliderect((box[2] + self.offset, box[3], box[0], box[1])) for box in bounding_boxes if box != []):
                            # Remover uma imagem da pilha se não houver bounding box
                            if sprite.images:
                                sprite.images.pop(0)  # Remove a primeira imagem da pilha

            def on_connect(device):
                click.echo("Device connected")
                self.connected = True  # Atualiza o sinalizador de conexão
                device.Invoke(-1)

            def on_disconnect(device):
                click.echo("Device disconnected")
                self.connected = False  # Atualiza o sinalizador de desconexão

            def on_log(device, log):
                click.echo(log)

            # Configurar callbacks
            device.on_connect = on_connect
            device.on_disconnect = on_disconnect
            device.on_monitor = on_monitor
            device.on_log = on_log
            click.echo("Waiting for device to be ready")
            device.loop_start()

            while not self.stop_thread:
                time.sleep(2)
                if not device.is_alive():
                    click.echo("Exited")
                    break

            device.loop_stop()

        except Exception as e:
            click.echo("Error: {}".format(e))

    def stop(self):
        """Encerra as threads."""        
        self.stop_thread = True

    def create_shadow(self, img, angle):
        """Cria uma sombra para a imagem rotacionada."""
        shadow = img.copy()
        shadow = shadow.filter(ImageFilter.GaussianBlur(2))  # Adicionar desfoque
        shadow = shadow.convert("RGBA")

        # Rotacionar a sombra
        shadow = shadow.rotate(angle, expand=True)

        return shadow

    def create_sprite_image(self, w, h):
        """Cria uma imagem de sprite redimensionada para manter a proporção da tela."""
        camera_frame_height = 240  # Altura do frame da câmera
        screen_height = self.rect_h  # Altura da tela atual
        scale_factor = (screen_height / camera_frame_height) * random.uniform(0.5, 0.8)  # Fator de escala entre a câmera e a tela

        # Calcular novas dimensões baseadas na altura da tela
        scaled_w = int(w * scale_factor)
        scaled_h = int(h * scale_factor)

        # Escolher uma imagem aleatória da pasta
        img_path = random.choice(self.imagens)
        imagem = Image.open(img_path).convert('RGBA')

        # Manter a proporção da imagem original ao redimensionar

        aspect_ratio = imagem.width / imagem.height
        new_height = scaled_h
        new_width = int(new_height * aspect_ratio)

        # Redimensionar a imagem
        imagem = imagem.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Aplicar rotação aleatória
        angle = random.randint(-60, 60)
        imagem = imagem.rotate(angle, expand=True)

        # Criar sombra
        shadow = self.create_shadow(imagem, angle)

        return pygame.image.fromstring(imagem.tobytes(), imagem.size, imagem.mode), pygame.image.fromstring(shadow.tobytes(), shadow.size, shadow.mode)

    def fill(self):
        """Função que preenche a tela com imagens sobrepostas, até 20 vezes por bounding box."""
        while not self.stop_thread:
            self.screen.fill((0, 0, 0))  # Limpar a tela

            # Desenhar todos os sprites
            for sprite in self.sprites:
                sprite.draw(self.screen)

            pygame.display.flip()  # Atualizar a tela
            time.sleep(self.intervalo)

    def display(self):
        """Função para exibir as imagens usando Pygame."""
        running = True
        
        # Aguarde até que a conexão seja estabelecida
        while not self.connected:
            time.sleep(0.1)

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q:  # Sair ao pressionar 'q'
                        running = False

            # Atualiza a tela com os sprites
            self.screen.fill((0, 0, 0))  # Limpar a tela
            # Desenhar todos os sprites
            for sprite in self.sprites:
                sprite.draw(self.screen)

            pygame.display.flip()  # Atualizar a tela
            time.sleep(self.intervalo)

        pygame.quit()


# Exemplo de uso:
if __name__ == "__main__":
    pasta_imagens = 'images_png'  # Caminho para a pasta com imagens
    filler = ImageFiller(pasta_imagens=pasta_imagens)

    # Iniciar a thread que captura as bounding boxes
    serial_thread = threading.Thread(target=filler.update, args=("COM11", 921600), daemon=True)
    serial_thread.start()

    # Iniciar a thread que preenche os sprites
    filler_thread = threading.Thread(target=filler.fill, daemon=True)
    filler_thread.start()

    # Exibir as imagens
    filler.display()

    # Finalizar as threads após a exibição
    filler.stop()
