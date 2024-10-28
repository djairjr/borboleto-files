import base64
import json
import click
from pythonosc import udp_client
from sscma.micro.client import SerialClient
from sscma.micro.device import Device

class USBtoTouchDesignerOSC:
    def __init__(self, port, baudrate, osc_ip, osc_port):
        self.port = port
        self.baudrate = baudrate
        self.osc_client = udp_client.SimpleUDPClient(osc_ip, osc_port)
        self.connected = False

    def process_data(self, data):
        """Processa os dados recebidos da serial: imagens e bounding boxes."""
        if "image" in data:
            # Decodificar a imagem base64
            image_b64 = data["image"]
            image_data = base64.b64decode(image_b64)
            self.send_image_to_touchdesigner(image_b64)  # Enviar imagem codificada base64 via OSC
        
        if "boxes" in data:
            # Obter as bounding boxes em formato JSON
            bounding_boxes = data["boxes"]
            self.send_bounding_boxes_to_touchdesigner(bounding_boxes)  # Enviar JSON via OSC

    def send_image_to_touchdesigner(self, image_b64):
        """Envia a imagem em base64 para o TouchDesigner via OSC."""
        # Enviar a imagem codificada em base64 como string via OSC
        self.osc_client.send_message("/image", image_b64)
        click.echo("Imagem enviada via OSC")

    def send_bounding_boxes_to_touchdesigner(self, bounding_boxes):
        """Envia as bounding boxes (JSON) para o TouchDesigner via OSC."""
        bounding_boxes_json = json.dumps(bounding_boxes)
        self.osc_client.send_message("/boxes", bounding_boxes_json)
        click.echo("Bounding boxes enviadas via OSC")

    def on_monitor(self, device, msg):
        """Callback para monitorar e processar os dados recebidos."""
        self.process_data(msg)

    def on_connect(self, device):
        click.echo("Dispositivo conectado")
        self.connected = True

    def on_disconnect(self, device):
        click.echo("Dispositivo desconectado")
        self.connected = False

    def start_device(self):
        """Inicializa a conexão com o dispositivo e começa a monitorar."""
        try:
            client = SerialClient(self.port, self.baudrate)
            device = Device(client)

            device.on_connect = self.on_connect
            device.on_disconnect = self.on_disconnect
            device.on_monitor = self.on_monitor

            device.loop_start()

            while True:
                if not self.connected:
                    click.echo("Esperando o dispositivo estar pronto...")
                # Aqui você pode adicionar lógica para encerrar se necessário
                pass

            device.loop_stop()

        except Exception as e:
            click.echo(f"Erro: {e}")

# Exemplo de uso:
if __name__ == "__main__":
    port = "COM11"  # Porta USB
    baudrate = 921600
    osc_ip = "127.0.0.1"  # Endereço IP do TouchDesigner (localhost ou outro)
    osc_port = 8000  # Porta OSC do TouchDesigner

    usb_interface = USBtoTouchDesignerOSC(port, baudrate, osc_ip, osc_port)
    usb_interface.start_device()
