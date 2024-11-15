#!/home/.../anaconda3/bin/python3

import mysql.connector
from datetime import datetime
import time

# Parâmetros de conexão do banco de dados
db_config = {
    'user': 'aluno',
    'password': 'xxx',
    'host': '127.0.0.1',
    'database': 'contikidb',
}

# Conecte-se ao banco de dados MySQL
try:
    conn = mysql.connector.connect(**db_config)
    c = conn.cursor()
    print("Conectado com sucesso ao banco de dados.")
except mysql.connector.Error as e:
    print(f"Erro ao conectar ao banco de dados MySQL: {e}")
    exit()

# Função para inserir dados do sensor no banco de dados
def insert_sensor_data(id_experimento, cenario, id_sensor, created, descricao, valor):
    try:
        c.execute("INSERT INTO sensor (id_experimento, cenario, id_sensor, created, descricao, valor) VALUES (%s, %s, %s, %s, %s, %s)",
                  (id_experimento, cenario, id_sensor, created, descricao, valor))
        conn.commit()
    except mysql.connector.Error as e:
        print(f"Erro ao inserir dados no banco de dados MySQL: {e}")
        return False  # Indica falha na inserção
    return True  # Indica inserção bem-sucedida

# Função para buscar o próximo id_experimento
def fetch_next_id_experimento():
    try:
        c.execute("SELECT MAX(id_experimento) as id FROM sensor")
        result = c.fetchone()
        id_experimento = result[0] if result[0] is not None else 0
        return id_experimento + 1
    except mysql.connector.Error as e:
        print(f"Erro ao buscar o próximo id_experimento do banco de dados MySQL: {e}")
        exit()

# Função para buscar o último nome do cenário da tabela "application"
def fetch_last_scenario_name():
    try:
        c.execute("SELECT cenario FROM application ORDER BY id DESC LIMIT 1")
        result = c.fetchone()
        return result[0] if result else None
    except mysql.connector.Error as e:
        print(f"Erro ao buscar o último nome de cenário do banco de dados MySQL: {e}")
        return None

# Defina os caminhos
log_files_directory = "/home/.../.../Logs_contiki/"
filtered_files_directory = "/home/.../.../Logs_contiki/Arquivos_filtrados/"

# Define a lista de nomes de arquivos de log originais
log_files = [
    'mote2.log', 'mote3.log', 'mote4.log', 'mote5.log', 'mote6.log', 'mote7.log'
]

# Inicializa o contador de tempo total
start_time_total = time.time()

# Processo de filtragem
for file in log_files:
    start_time = time.time()  # Hora de início da filtragem
    full_file_path = log_files_directory + file
    with open(full_file_path, 'r') as infile:
        filtered_filename = file.replace('.log', '_filtrado.log')
        full_filtered_file_path = filtered_files_directory + filtered_filename
        with open(full_filtered_file_path, 'w') as outfile:
            for line in infile:
                # Verifica se a linha contém o texto específico a ser ignorado
                if "[WARN: IPv6      ] tcp: got reset, aborting connection." in line:
                    continue  # Ignora esta linha e vai para a próxima iteração do loop
                
                line_without_info = line.replace('[INFO: RPL BR    ]', '')
                if 'metric:' in line_without_info and 'clock_ticks_for' not in line_without_info:
                    line_without_metric = line_without_info.replace('metric:', '')
                    words = line_without_metric.split()
                    words_with_semicolons = ';'.join(words)
                    outfile.write(words_with_semicolons + '\n')

    end_time = time.time()  # Fim do tempo de filtragem
    elapsed_time = end_time - start_time  # Tempo gasto na filtragem
    print(f"Filtragem concluída para {file}. Tempo gasto: {elapsed_time:.2f} segundos")

id_experimento = fetch_next_id_experimento()
cenario = fetch_last_scenario_name()

if not cenario:
    print("Falha ao buscar o último nome do cenário. Verifique o banco de dados.")
    exit()

# Carregando dados para o banco de dados
log_dir = "/home/.../.../Logs_contiki/Arquivos_filtrados/"
log_files = [
    'mote2_filtrado.log', 'mote3_filtrado.log',
    'mote4_filtrado.log', 'mote5_filtrado.log', 'mote6_filtrado.log', 'mote7_filtrado.log'
]

for file_name in log_files:
    start_time = time.time()  # Hora de início do upload
    total_inserted = 0
    try:
        id_sensor = int(file_name.split("/")[-1].replace("mote", "").replace("_filtrado.log", ""))
        with open(log_dir + file_name, 'r') as file:
            for line in file:
                data = line.strip().split(';')
                if len(data) >= 2:
                    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    descricao, valor = data[0], data[1]
                    if insert_sensor_data(id_experimento, cenario, id_sensor, created, descricao, valor):
                        total_inserted += 1
    except Exception as e:
        print(f"Ocorreu um erro com o arquivo {file_name}: {e}")

    end_time = time.time()  # Hora de término do upload
    elapsed_time = end_time - start_time  # Tempo necessário para upload
    print(f"Inserido com sucesso {total_inserted} registros de {file_name} no banco de dados. Tempo gasto: {elapsed_time:.2f} segundos")

# Calcula o tempo total gasto em todo o processo
end_time_total = time.time()
total_elapsed_time = end_time_total - start_time_total
print(f"Tempo total gasto em todo o processo: {total_elapsed_time:.2f} segundos")

# Feche a conexão com o banco de dados
conn.close()
print("Conexão com o banco de dados fechada.")
