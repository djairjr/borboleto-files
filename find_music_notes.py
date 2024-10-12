import librosa
import numpy as np

# Função para mapear frequências para notas musicais
def frequency_to_note(freq):
    A4 = 440  # Hz
    C0 = A4 * 2**(-4.75)
    h = round(12 * np.log2(freq / C0))
    octave = h // 12
    n = h % 12
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    if n >= 0 and n < len(note_names):
        return note_names[n] + str(octave)
    return None

# Carregar o arquivo MP3, limitando para os primeiros 15 segundos
audio_file = 'todoenrolado.mp3'  # Certifique-se de que este arquivo está no mesmo diretório que o script
y, sr = librosa.load(audio_file, duration=10.0)

# Definir um intervalo de tempo (em segundos) para calcular a frequência
frame_length = 2048
hop_length = 512
num_frames = int(np.ceil(len(y) / hop_length))

# Listas para armazenar notas
notes = []

# Calcular a frequência média em cada quadro
for i in range(num_frames):
    start = i * hop_length
    end = start + frame_length
    if end <= len(y):
        frame = y[start:end]
    else:
        frame = y[start:]

    # Calcular a Transformada Rápida de Fourier (FFT)
    fft_result = np.fft.fft(frame)
    frequencies = np.abs(fft_result)

    # Encontre a frequência mais alta em cada quadro
    dominant_frequency_index = np.argmax(frequencies)
    dominant_frequency = dominant_frequency_index * (sr / len(frame))

    # Converter a frequência dominante para uma nota musical
    note = frequency_to_note(dominant_frequency)
    if note:  # Adicionar nota se não for None
        notes.append(note)

# Converter a sequência de notas para notação RTTTL
def convert_to_rtttl(notes):
    rtttl = "melody:d=4,o=5,b=100:"
    for note in notes:
        if note:
            rtttl += f"{note},"
    return rtttl.rstrip(',')  # Remove a última vírgula

# Exibir a sequência de notas em notação RTTTL
rtttl_output = convert_to_rtttl(notes)
print("Sequência de notas em notação RTTTL:")
print(rtttl_output)

# Salvar a sequência de notas em um arquivo .txt
output_file = 'notes_rtttl.txt'  # Nome do arquivo
with open(output_file, 'w') as file:
    file.write(rtttl_output)

print(f"As notas foram salvas em {output_file}")
