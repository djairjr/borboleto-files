import os
import ctypes
import subprocess
import re
import random
import cv2
import base64
import numpy as np
import serial
import threading
import time
import logging
import signal
from sscma.micro.client import Client
from sscma.micro.device import Device
from sscma.micro.const import *

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

# Caminho da pasta com as imagens
IMAGES_PATH = "images_png"
images_list = []
current_image_index = 0

JSON_WIDTH = 480
JSON_HEIGHT = 480

recieve_thread_running = True

def get_screen_resolution():
    # Inicializa largura e altura como None
    width, height = None, None

    if os.name == 'nt':  # Windows
        user32 = ctypes.windll.user32
        width = user32.GetSystemMetrics(0)  # Largura da tela
        height = user32.GetSystemMetrics(1)  # Altura da tela

    elif os.name == 'posix':  # Linux ou MacOS
        # Tenta usar `xdpyinfo`
        try:
            output = subprocess.run(['xdpyinfo'], capture_output=True, text=True, check=True)
            resolution = re.search(r'dimensions:\s+(\d+)x(\d+)', output.stdout)
            if resolution:
                width = int(resolution.group(1))
                height = int(resolution.group(2))
        except Exception as e:
            print(f"Erro ao usar 'xdpyinfo': {e}. Tentando xrandr...")
            # Tenta usar `xrandr`
            try:
                output = subprocess.run(['xrandr'], capture_output=True, text=True, check=True)
                for line in output.stdout.splitlines():
                    if '*' in line:
                        parts = line.split()
                        width = int(parts[0])  # Largura
                        height = int(parts[2])  # Altura
                        break
            except Exception as e:
                print(f"Erro ao executar 'xrandr': {e}. Tentando acessar arquivos de sistema...")

                # Tenta acessar /sys/class/drm/ para obter a resolução
                try:
                    for filename in os.listdir('/sys/class/drm/'):
                        if 'card' in filename:
                            mode_file = os.path.join('/sys/class/drm/', filename, 'modes')
                            with open(mode_file) as f:
                                for line in f:
                                    parts = line.split()
                                    if parts:
                                        resolution = parts[0]  # A primeira linha geralmente tem a resolução
                                        width, height = map(int, resolution.split('x'))
                                        return width, height
                except Exception as e:
                    print(f"Erro ao acessar arquivos de sistema: {e}")

    if width is not None and height is not None:
        return width, height
    else:
        raise Exception("Não foi possível obter a resolução da tela.")

DISPLAY_WIDTH, DISPLAY_HEIGHT = get_screen_resolution()

def recieve_thread(serial_port, client):
    while recieve_thread_running:
        if serial_port.in_waiting:
            msg = serial_port.read(serial_port.in_waiting)
            if msg != b'':
                client.on_recieve(msg)

def load_images():
    """Carrega as imagens da pasta e as embaralha."""
    global images_list
    images_list = os.listdir(IMAGES_PATH)
    random.shuffle(images_list)  # Embaralha as imagens no início

def get_next_image():
    """Obtém a próxima imagem da lista, reembaralhando se necessário."""
    global current_image_index

    if current_image_index >= len(images_list):
        # Reembaralhar quando todas as imagens já tiverem sido usadas
        random.shuffle(images_list)
        current_image_index = 0

    img_path = os.path.join(IMAGES_PATH, images_list[current_image_index])
    current_image_index += 1

    # Carregar a imagem
    img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)  # Ler com o canal alfa (transparência, se houver)
    return img

def resize_bounding_boxes(boxes, img_width, img_height):
    resized_boxes = []
    for box in boxes:
        x_min = int((box[0] / JSON_WIDTH) * img_width)
        y_min = int((box[1] / JSON_HEIGHT) * img_height)
        x_max = int((box[2] / JSON_WIDTH) * img_width)
        y_max = int((box[3] / JSON_HEIGHT) * img_height)
        confidence = box[4]  # Mantemos o confidence, mas não exibimos
        class_id = box[5]    # Mantemos o class_id, mas não exibimos

        resized_boxes.append([x_min, y_min, x_max, y_max, confidence, class_id])
    return resized_boxes

def extract_silhouette(frame, box):
    """Extrai a silhueta da pessoa dentro da bounding box usando segmentação simples."""
    x_min, y_min, x_max, y_max, _, _ = box

    # Cortar a região da bounding box do frame
    roi = frame[y_min:y_max, x_min:x_max]

    # Converter para escala de cinza e aplicar um threshold para extrair a silhueta
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, silhouette = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY)

    return silhouette

def apply_silhouette_mask(image, silhouette_mask):
    """Aplica a silhueta binária como máscara para a imagem da pasta."""
    if silhouette_mask.shape != image.shape[:2]:
        silhouette_mask = cv2.resize(silhouette_mask, (image.shape[1], image.shape[0]))

    # Aplicar a máscara binária à imagem (substitui os pixels onde a máscara é branca)
    masked_image = cv2.bitwise_and(image, image, mask=silhouette_mask)

    return masked_image

def overlay_image(background, overlay, x, y):
    """Sobrepõe a imagem 'overlay' em 'background' nas coordenadas (x, y)."""
    if overlay.shape[2] == 4:  # Se a imagem de sobreposição tiver canal alfa (transparência)
        overlay_img = overlay[:, :, :3]
        overlay_mask = overlay[:, :, 3:]
        bg_region = background[y:y+overlay_img.shape[0], x:x+overlay_img.shape[1]]
        mask_inv = cv2.bitwise_not(overlay_mask)
        bg_region = cv2.bitwise_and(bg_region, bg_region, mask=mask_inv)
        overlay_img = cv2.bitwise_and(overlay_img, overlay_img, mask=overlay_mask)
        background[y:y+overlay_img.shape[0], x:x+overlay_img.shape[1]] = cv2.add(bg_region, overlay_img)
    else:
        background[y:y+overlay.shape[0], x:x+overlay.shape[1]] = overlay
    return background

def monitor_handler(device, msg):
    if "image" in msg:
        # Decodificar a imagem em Base64
        jpeg_bytes = base64.b64decode(msg["image"])
        nparr = np.frombuffer(jpeg_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)  # Imagem original

        if "boxes" in msg:
            boxes = msg["boxes"]

            # Criar uma imagem em branco (preta) para a exibição
            img = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 3), dtype=np.uint8)

            # Redimensiona as bounding boxes de acordo com a resolução
            resized_boxes = resize_bounding_boxes(boxes, DISPLAY_WIDTH, DISPLAY_HEIGHT)

            for box in resized_boxes:
                x_min, y_min, x_max, y_max, _, _ = box

                # Obtenha a silhueta da pessoa dentro da bounding box
                silhouette_mask = extract_silhouette(frame, box)

                # Obtenha a próxima imagem aleatória da pasta
                overlay_img = get_next_image()

                # Aplicar a máscara de silhueta à imagem selecionada
                masked_image = apply_silhouette_mask(overlay_img, silhouette_mask)

                # Redimensionar a imagem mascarada para caber na bounding box
                masked_image_resized = cv2.resize(masked_image, (x_max - x_min, y_max - y_min))

                # Sobrepor a imagem mascarada na posição da bounding box
                img = overlay_image(img, masked_image_resized, x_min, y_min)

            # Exibir a imagem final com as silhuetas sobrepostas
            cv2.imshow('Detecções com Silhuetas', img)
            cv2.waitKey(1)

        msg.pop("image")

    print(msg)

def on_device_connect(device):
    print("device connected")
    device.Invoke(-1, False, True)
    device.tscore = 70
    device.tiou = 70

def signal_handler(signal, frame):
    print("Ctrl+C pressed!")
    global recieve_thread_running
    recieve_thread_running = False
    exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    serial_port = serial.Serial("COM11", 921600, timeout=0.1)
    #serial_port = serial.Serial("/dev/ttyACM0", 921600, timeout=0.1)
    client = Client(lambda msg: serial_port.write(msg))
    threading.Thread(target=recieve_thread, args=(serial_port, client)).start()

    device = Device(client)
    device.on_monitor = monitor_handler
    device.on_connect = on_device_connect
    device.loop_start()

    # Carrega as imagens da pasta no início do programa
    load_images()

    print(device.info)

    i = 60
    while True:
        #print(device.wifi)
        #print(device.mqtt)
        #print(device.info)
        #print(device.model)
        device.tscore = i
        device.tiou = i
        i = i + 1
        if i > 100:
            i = 30

        time.sleep(2)

if __name__ == "__main__":
    main()
