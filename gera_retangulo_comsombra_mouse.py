import os
import random
import time
import threading
import pygame
import click
from PIL import Image, ImageFilter
from sscma.micro.client import SerialClient
from sscma.micro.device import Device


class ImageFiller:
    def __init__(self, pasta_imagens):        
        # As dimensões da imagem são no máximo, a bounding box
        self.image_w = 0
        self.image_h = 0
        self.image_x = 0
        self.image_y = 0

        self.fps = 30
        
        self.pasta_imagens = pasta_imagens
        
        self.imagens = [os.path.join(pasta_imagens, img) for img in os.listdir(pasta_imagens) if img.endswith('.png')]
        self.intervalo = 1 / self.fps
        self.stop_thread = False
        self.connected = False  # Sinalizador para indicar se a conexão foi estabelecida

        # Inicializar o Pygame
        pygame.init()
        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)  # Tela cheia
        # As dimensões do retângulo ocupam toda a tela
        self.screen_info = pygame.display.Info()
        self.rect_w = self.screen_info.current_w
        self.rect_h = self.screen_info.current_h       
        self.rect_x = 0 
        self.rect_y = 0
        self.retangulo = Image.new('RGBA', (self.rect_w, self.rect_h), (0, 0, 0, 255))  # Correção dos atributos w e h

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
                        if box !=[]:
                            self.image_w, self.image_h, self.image_x, self.image_y = box[0], box[1], box[2], box[3]
                            print(f"Updated bounding box: w={self.image_w}, h={self.image_h}, x={self.image_x}, y={self.image_y}")
                        else:
                            self.image_w, self.image_h, self.image_x, self.image_y = 0,0,0,0
                            print ("no box info")

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

    def fill(self):
        """Função que preenche o retângulo com imagens sobrepostas, apenas se houver bounding boxes válidas."""
        camera_frame_height = 240  # Altura do frame da câmera
        screen_height = self.screen.get_height()  # Altura da tela atual
        scale_factor = screen_height / camera_frame_height  # Fator de escala entre a câmera e a tela

        while not self.stop_thread:
            if self.image_w == 0 and self.image_h == 0:
                # Não há bounding box, a tela deve ficar preta
                time.sleep(self.intervalo)
                continue

            # Multiplicar as bounding boxes pelo fator de escala
            scaled_w = int(self.image_w * scale_factor)
            scaled_h = int(self.image_h * scale_factor)
            scaled_x = int(self.image_x * scale_factor)
            scaled_y = int(self.image_y * scale_factor)

            # Calcular os limites de tamanho das imagens com base nas bounding boxes escaladas
            min_area = int(0.6 * scaled_w * scaled_h)  # 60% da área total da bounding box escalada
            max_area = int(scaled_w * scaled_h)  # 100% da área total da bounding box escalada

            # Escolher uma imagem aleatória da pasta
            img_path = random.choice(self.imagens)
            imagem = Image.open(img_path).convert('RGBA')

            # Calcular a área aleatória entre os limites
            area = random.randint(min_area, max_area)

            # Calcular nova largura e altura mantendo a proporção
            aspect_ratio = imagem.height / imagem.width
            new_width = int((area / aspect_ratio))
            new_height = int(new_width * aspect_ratio)

            # Redimensionar a imagem
            imagem = imagem.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Aplicar rotação aleatória
            angle = random.randint(-60, 60)
            imagem = imagem.rotate(angle, expand=True)

            # Criar sombra
            shadow = self.create_shadow(imagem, angle)

            # Calcular coordenadas aleatórias para posicionar a imagem dentro do retângulo escalado
            pos_x = random.randint(scaled_x, max(scaled_x, scaled_x + scaled_w - new_width))
            pos_y = random.randint(scaled_y, max(scaled_y, scaled_y + scaled_h - new_height))

            # Colocar a sombra e a imagem no retângulo
            self.retangulo.paste(shadow, (pos_x, pos_y + 10), shadow)  # Colocar sombra abaixo
            self.retangulo.paste(imagem, (pos_x, pos_y), imagem)

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

            # Preencher a tela com preto
            self.screen.fill((0, 0, 0))

            # Converter a imagem PIL para Surface do Pygame
            mode = self.retangulo.mode
            size = self.retangulo.size
            data = self.retangulo.tobytes()
            pygame_image = pygame.image.fromstring(data, size, mode)

            # Blitar a imagem no retângulo especificado
            self.screen.blit(pygame_image, (self.image_x, self.image_y))

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

    # Iniciar a thread que preenche o retângulo
    filler_thread = threading.Thread(target=filler.fill, daemon=True)
    filler_thread.start()

    # Exibir as imagens
    filler.display()

    # Finalizar as threads após a exibição
    filler.stop()
