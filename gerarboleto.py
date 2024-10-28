# -*- coding: utf-8 -*-
import random
import datetime
import faker
import os
from pyboleto import pdf
from pyboleto.bank.bradesco import BoletoBradesco
from pyboleto.bank.hsbc import BoletoHsbc
from pyboleto.bank.itau import BoletoItau
from pyboleto.bank.santander import BoletoSantander

from pdf2image import convert_from_path

# Função para gerar CPF/CNPJ aleatório
def gerar_cpf():
    num = random.randint(100000000, 999999999)
    cpf = f'{num:09d}-{random.randint(0, 9)}{random.randint(0, 9)}'
    return cpf


# Função para gerar boletos
def gerar_boletos(num_boletos, nome, endereco):
    # Instância do Faker para gerar dados aleatórios
    fake = faker.Faker()

    # Lista de classes de boletos dos bancos
    bancos = [
        BoletoBradesco,
        BoletoHsbc,
        BoletoItau,
        BoletoSantander,
    ]

    # Criar a pasta images_png se não existir
    os.makedirs('images_png', exist_ok=True)

    for i in range(num_boletos):
        d = random.choice(bancos)()  # Escolher um banco aleatório
        d.carteira = str(random.choice([109, 110, 112]))  # Carteira aleatória
        d.agencia_cedente = str(random.randint(1000, 9999))  # Agência aleatória
        d.conta_cedente = str(random.randint(10000, 99999))  # Conta aleatória
        d.conta_cedente_dv = str(random.randint(1, 9))  # DV aleatório

        # Gerar datas aleatórias entre 11 e 15 de outubro de 2024
        data_vencimento = datetime.date(2024, 10, random.randint(11, 15))
        d.data_vencimento = data_vencimento
        d.data_documento = data_vencimento
        d.data_processamento = data_vencimento

        # Valor aleatório entre R$200 e R$2500
        d.valor_documento = round(random.uniform(200.00, 2500.00), 2)
        d.nosso_numero = str(157 + i)
        d.numero_documento = str(456 + i)

        # Definir nome e endereço do pagador e do beneficiario
        d.cedente = fake.name()
        d.cedente_logradouro = fake.address().replace('\n', ', ')
        d.cedente_documento = gerar_cpf()  # CPF do beneficiário
        d.sacado_nome = nome
        d.sacado_endereco = endereco.replace('\n', ', ')
        d.sacado_documento = 'Your Doc Here'
        # Gerar PDF
        pdf_filename = f'boleto_{i + 1}.pdf'

        # Criar o objeto BoletoPDF
        boleto_pdf = pdf.BoletoPDF(pdf_filename)
        boleto_pdf.drawBoleto(d)  # Desenhar o boleto no PDF
        boleto_pdf.save()  # Salvar o PDF

        # Converter PDF para PNG
        images = convert_from_path(pdf_filename)
        for j, image in enumerate(images):
            png_filename = f'images_png/boleto_{i + 1}_{j + 1}.png'
            image.save(png_filename, 'PNG')

# Defina seu nome e endereço aqui
seu_nome = "Your Name Here"
seu_endereco = "Your Address Here"
# Gerar 100 boletos
gerar_boletos(100, seu_nome, seu_endereco)
