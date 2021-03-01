from os import listdir
from os.path import isfile, join


def ler_char():
    return file.read(1)


def abrir_arquivo(path):
    global file
    file = open(path, 'r+')


def fechar_arquivo():
    file.close()
    print('Arquivo fechado!')


def escrever(mensagem, path):
    with open(path, 'w+') as archive:
        archive.write(mensagem)


def retorna_linhas(path):                                        # Retorna um vetor com as linhas da arquivo
    with open(path, 'r+') as archive:
        return archive.readlines()


def lista_arquivos(path):                                        # Caminho do diretório que será analisado
    files = [f for f in listdir(path) if isfile(join(path, f))]  # Não faço idéia do que ele está fazendo aqui
    print(files)                                                 # Printa os arquivos no diretório que foi passado
    print('O directório possui:', len(files), 'arquivos')        # len() retorn o tamanho do array
    print('#############################')
    return files


def voltar_cursor():
    file.seek(file.tell() - 1)
