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
        self.stack_num = 3  # Número de elementos na pilha de imagens
        self.images = []  # Lista para armazenar múltiplas imagens
        self.shadows = []  # Lista para armazenar múltiplas sombras
        self.rect = pygame.Rect(x, y, w, h)  # Criação do retângulo para o sprite

    def add_image(self, image, shadow):
        """Adiciona uma nova imagem e sombra à pilha, com um limite máximo."""
        if len(self.images) < self.stack_num:  # Limitar a 3 imagens empilhadas
            self.images.append(image)
            self.shadows.append(shadow)
        else:
            # Remove a imagem mais antiga e adiciona a nova
            self.images.pop(0)
            self.shadows.pop(0)
            self.images.append(image)
            self.shadows.append(shadow)

    def update(self, x, y, w, h):
        """Atualiza a posição e dimensões do sprite."""
        self.rect.topleft = (x, y)
        self.rect.width = w
        self.rect.height = h

    def draw(self, surface):
        """Desenha todas as imagens na pilha no sprite, incluindo sombras."""
        for img, shadow in zip(self.images, self.shadows):
            # Desenha a sombra com deslocamento
            shadow_rect = shadow.get_rect(center=self.rect.center)
            surface.blit(shadow, shadow_rect.move(1, 1))  # Desloca a sombra em 1 pixel

            # Centralizar a imagem
            img_rect = img.get_rect(center=self.rect.center)
            surface.blit(img, img_rect)  # Desenha a imagem no centro do retângulo


class ImageFiller:
    def __init__(self, pasta_imagens, music_file):
        # Inicializar atributos
        self.fps = 30
        self.pasta_imagens = pasta_imagens
        self.imagens = [os.path.join(pasta_imagens, img) for img in os.listdir(pasta_imagens) if img.endswith('.png')]
        self.intervalo = 1 / self.fps
        self.stop_thread = False
        self.connected = False  # Sinalizador para indicar se a conexão foi estabelecida
        self.sprites = pygame.sprite.Group()  # Grupo de sprites
        
        # Inicializar o Pygame
        pygame.init()
        pygame.mouse.set_visible(False)
        pygame.mixer.init()  # Inicializar o mixer do Pygame

        # Detectar a resolução da tela
        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)  # Tela cheia
        self.screen_info = pygame.display.Info()
        self.rect_w = self.screen_info.current_w #NTSC 720
        self.rect_h = self.screen_info.current_h #NTSC 480

        # Calcula o offset horizontal para centralizar os sprites
        self.offset = (self.rect_w - self.rect_h) // 2  # Considerando que a maior bounding box é 240x240
        self.vertical_offset = 0  # Offset vertical ajustável
        
        # Carregar a música
        pygame.mixer.music.load(music_file)

    def update(self, port, baudrate):
        """Conecta à porta serial e atualiza as bounding boxes."""
        try:
            client = SerialClient(port, baudrate)
            device = Device(client)

            def on_monitor(device, msg):
                data = msg
                # Obter a resolução da câmera
                self.camera_res = data.get("resolution", (240, 240))
                self.camera_width, self.camera_height = self.camera_res

                # Remover chaves desnecessárias
                keys_to_remove = ["image", "count", "perf", "resolution", "rotate"]
                for key in keys_to_remove:
                    data.pop(key, None)

                if "boxes" in data:
                    bounding_boxes = data["boxes"]

                    for box in bounding_boxes:
                        if box != []:
                            # Extrair as dimensões da bounding box: x, y, w, h, score, target_id
                            x, y, w, h, score, target = box

                            # Ajustar a posição da bounding box com o offset horizontal e vertical
                            x += self.offset
                            y += self.vertical_offset  # Aplicar o offset vertical

                            # Verifica se o sprite já existe, caso contrário cria um novo
                            sprite = next((s for s in self.sprites if s.rect.colliderect((x, y, w, h))), None)
                            if not sprite:
                                sprite = BoundingBoxSprite(x, y, w, h)
                                self.sprites.add(sprite)

                            # Criar a imagem e a sombra do sprite
                            sprite_image, shadow = self.create_sprite_image(w, h)
                            sprite.add_image(sprite_image, shadow)
                            sprite.update(x, y, w, h)

                    # Remover sprites que não estão mais sendo detectados
                    for sprite in list(self.sprites):  # Converter para lista para permitir remoção durante a iteração
                        if not any(sprite.rect.colliderect((box[2] + self.offset, box[3] + self.vertical_offset, box[0], box[1])) 
                                   for box in bounding_boxes if box != []):
                            if sprite.images:
                                sprite.images.pop(0)
                                sprite.shadows.pop(0)
                            if not sprite.images:
                                self.sprites.remove(sprite)

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
        shadow = shadow.rotate(angle, expand=True)
        return shadow

    def create_sprite_image(self, w, h):
        """Cria uma imagem de sprite redimensionada para manter a proporção da tela."""
        # Calcular escala baseado na altura da tela
        screen_height = self.rect_h
        scale_factor = (screen_height / self.camera_height) * random.uniform(0.4, 0.7)  # Ajustar fator de escala conforme necessário

        # Evitar que a escala ultrapasse os limites para evitar imagens muito grandes
        scale_factor = min(scale_factor, 1.0)

        # Calcular novas dimensões baseadas na escala
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

        # Redimensionar a imagem e sombra com um fator aleatório para variação de tamanho
        random_scale = random.uniform(0.4, 1.0)
        final_width = int(imagem.width * random_scale)
        final_height = int(imagem.height * random_scale)
        imagem = imagem.resize((final_width, final_height), Image.Resampling.LANCZOS)
        shadow = shadow.resize((final_width, final_height), Image.Resampling.LANCZOS)

        return pygame.image.fromstring(imagem.tobytes(), imagem.size, imagem.mode), pygame.image.fromstring(shadow.tobytes(), shadow.size, shadow.mode)

    def fill(self):
        """Função que preenche a tela com imagens sobrepostas."""
        while not self.stop_thread:
            self.screen.fill((0, 0, 0))  # Limpar a tela

            # Desenhar todos os sprites
            for sprite in self.sprites:
                sprite.draw(self.screen)

            pygame.display.flip()  # Atualizar a tela

            # Contar sprites visíveis (com imagens)
            visible_sprites = [s for s in self.sprites if s.images]
            if visible_sprites:
                if not pygame.mixer.music.get_busy():
                    pygame.mixer.music.play(-1)  # Tocar música em loop
            else:
                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()  # Parar música

            time.sleep(self.intervalo)

    def display(self):
        """Função para exibir as imagens usando Pygame."""
        running = True

        while not self.connected:
            time.sleep(0.1)

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q:
                        running = False
                    # Adicionar controles para ajustar vertical_offset
                    elif event.key == pygame.K_UP:
                        self.vertical_offset -= 10  # Ajustar conforme necessário
                        click.echo(f"Vertical offset ajustado para: {self.vertical_offset}")
                    elif event.key == pygame.K_DOWN:
                        self.vertical_offset += 10  # Ajustar conforme necessário
                        click.echo(f"Vertical offset ajustado para: {self.vertical_offset}")

            # Atualiza a tela com os sprites
            self.screen.fill((0, 0, 0))  # Limpar a tela
            for sprite in self.sprites:
                sprite.draw(self.screen)

            pygame.display.flip()  # Atualizar a tela

            # Contar sprites visíveis (com imagens)
            visible_sprites = [s for s in self.sprites if s.images]
            if visible_sprites:
                if not pygame.mixer.music.get_busy():
                    pygame.mixer.music.play(-1)  # Tocar música em loop
            else:
                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()  # Parar música

            time.sleep(self.intervalo)

        pygame.quit()


# Exemplo de uso:
if __name__ == "__main__":
    pasta_imagens = 'images_png'  # Caminho para a pasta com imagens
    music_file = 'todoenrolado.mp3'  # Caminho para o arquivo de música
    filler = ImageFiller(pasta_imagens=pasta_imagens, music_file=music_file)

    # Iniciar a thread que captura as bounding boxes
    serial_thread = threading.Thread(target=filler.update, args=("COM11", 921600), daemon=True)
    # serial_thread = threading.Thread(target=filler.update, args=("/dev/ttyACM0", 921600), daemon=True)
    serial_thread.start()

    # Iniciar a thread que preenche os sprites
    filler_thread = threading.Thread(target=filler.fill, daemon=True)
    filler_thread.start()

    # Exibir as imagens
    filler.display()

    # Finalizar as threads após a exibição
    filler.stop()
