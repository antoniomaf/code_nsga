#!/home/.../anaconda3/bin/python3

import socket
import threading
import subprocess
import tempfile
import mysql.connector
from mysql.connector import Error
import time
import os
from datetime import datetime
import sys
import multiprocessing
import re  # Importação necessária para expressões regulares na obtenção do próximo nome de cenário
import threading

# Evento global sinalizará término após 15 minutos
terminate_event = multiprocessing.Event()

# Configuração para seus motes: números de porta e nomes de arquivos de log
MOTE_CONFIG = {
    60002: "/home/.../.../Logs_contiki/mote2.log",
    60003: "/home/.../.../Logs_contiki/mote3.log",
    60004: "/home/.../.../Logs_contiki/mote4.log",
    60005: "/home/.../.../Logs_contiki/mote5.log",
    60006: "/home/.../.../Logs_contiki/mote6.log",
    60007: "/home/.../.../Logs_contiki/mote7.log",
}

# Inicializar um contador para conexões bem-sucedidas
successful_connections = 0
connection_lock = threading.Lock()

# Parâmetros de conexão do banco de dados
db_config = {
    'user': 'aluno',
    'password': 'xxx',
    'host': '127.0.0.1',
    'database': 'contikidb',
}

# Nós para benchmarking com nomes legíveis
nodes = {
    "node1": 0,
    "node2": 0,
    "node3": 0,
    "node4": 0,
    "node5": 0,
    "node6": 0,
    "node7": 0,
}

# Mapeia os nomes dos nós para os endereços IP para o processo de benchmarking real
node_ip_addresses = {
    "node1": "fd00::201:1:1:1",
    "node2": "fd00::202:2:2:2",
    "node3": "fd00::203:3:3:3",
    "node4": "fd00::204:4:4:4",
    "node5": "fd00::205:5:5:5",
    "node6": "fd00::206:6:6:6",
    "node7": "fd00::207:7:7:7",
}

# Função modificada para gerar IDs sequenciais a partir de um valor inicial
def id_generator(cursor):
    cursor.execute("SELECT MAX(id) as id FROM application")
    result = cursor.fetchone()
    current_id = 1 if result[0] is None else result[0] + 1
    while True:
        yield current_id
        current_id += 1

def handle_connection(mote_port, log_file_name):    
    global successful_connections
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(('localhost', mote_port))
            with connection_lock:
                successful_connections += 1
            print(f"Mote connected on port {mote_port}.")
            with open(log_file_name, 'w') as log_file:
                while not terminate_event.is_set():
                    s.settimeout(1.0)
                    try:
                        data = s.recv(1024)
                        if not data:
                            break
                        decoded_data = data.decode('utf-8', errors='replace')
                        log_file.write(decoded_data)
                    except socket.timeout:
                        continue
    except ConnectionRefusedError:
        print(f"Conexão recusada para mote na porta {mote_port}.")
    finally:
        print(f"Conexão de socket encerrada na porta {mote_port}.")

def countdown_and_benchmark(benchmark_duration):    
    while successful_connections < len(MOTE_CONFIG):
        time.sleep(1)

    time.sleep(10)
    
    benchmark_process = multiprocessing.Process(target=start_benchmarking)
    benchmark_process.start()

    time.sleep(benchmark_duration - 10)

    terminate_event.set()
    
    benchmark_process.join()
    print("Teste Benchmark concluído")
    
def start_benchmarking():
    conn, cursor = connect_to_database()
    id_gen = id_generator(cursor)  # Inicializa o gerador de IDs
    cenario_name = get_next_scenario_name(cursor)  # Obtém o nome do cenário no início do benchmark
    try:
        main_benchmarking(conn, cursor, id_gen, cenario_name)  # Passa o nome do cenário como argumento
    finally:
        cursor.close()
        conn.close()

def connect_to_database():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn, conn.cursor()
    except Error as e:
        print(f"Erro ao conectar ao banco de dados MySQL: {e}")
        exit(1)

def get_next_scenario_name(cursor):
    cursor.execute("SELECT cenario FROM application ORDER BY id DESC LIMIT 1")
    result = cursor.fetchone()
    if result and result[0]:
        match = re.search(r'(\d+)$', result[0])
        if match:
            last_cenario_id = int(match.group(0))
            next_cenario_id = last_cenario_id + 1
            return re.sub(r'\d+$', str(next_cenario_id), result[0])
        else:
            return f"{result[0]}_1"
    else:
        return "Simulation_1"

def parse_tsv_and_log_results(tsv_file, cursor, node, cenario, conn, id_gen):
    
    complete_requests = failed_requests = total_transferred = transfer_rate = None
    ctime = dtime = ttime = wait = None
    
    id_experimento = next(id_gen)  # Obtém o próximo ID do gerador
    starttime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    with open(tsv_file, 'r') as file:
        for line in file:
            parts = line.split(":")
            if len(parts) > 1:  # Garante que o caractere ":" foi encontrado
                key = parts[0].strip()
                # Assegura que há um valor numérico após ":" antes de tentar extrair o valor
                values = parts[1].strip().split()
                if values:  # Verifica se a lista não está vazia
                    value = values[0]  # Agora é seguro acessar o primeiro elemento
                    if 'Complete requests' in key:
                        complete_requests = value
                    elif 'Failed requests' in key:
                        failed_requests = value
                    elif 'Total transferred' in key:
                        total_transferred = value
                    elif 'Transfer rate' in key:
                        transfer_rate = value
                    elif 'Connect' in key:
                        ctime = value
                    elif 'Processing' in key:
                        dtime = value
                    elif 'Waiting' in key:
                        wait = value
                    elif 'Total' in key and 'Total time' not in key and 'Total transferred' not in key:
                        ttime = value

    if None in [complete_requests, failed_requests, total_transferred, transfer_rate, ctime, dtime, ttime, wait]:
        print("Erro: Não foi possível extrair todos os dados necessários.")
        return

    
    if None in [complete_requests, failed_requests, total_transferred, transfer_rate, ctime, dtime, ttime, wait]:
        print("Erro: Não foi possível extrair todos os dados necessários.")
        return

    sql = """INSERT INTO `contikidb_tmp`.application (
        id, complete_requests, failed_requests, 
        total_transferred, transfer_rate, starttime, 
        ctime, dtime, ttime, wait, node, cenario
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""

    data_tuple = (id_experimento, complete_requests, failed_requests, total_transferred, transfer_rate, starttime, ctime, dtime, ttime, wait, node, cenario)
    
    print(data_tuple);
    
    try:
        cursor.execute(sql, data_tuple)        
        conn.commit()  # Insere os dados no banco de dados    
        print(f"Dados inseridos com sucesso para o nó {node} no cenário {cenario}.")
    except Error as e:
        print(f"Erro de banco de dados: {e}")
        exit(1)

def main_benchmarking(conn, cursor, id_gen, cenario_name):
    delay = 25
    timeout = 300 # 5 minutos    
    start_time = time.time()
    tempo_total = 0

    try:
        for node_name in nodes.keys():
            if tempo_total > timeout:
                break
            benchmark_node(node_name, cursor, conn, id_gen, cenario_name)  # Passa o nome do cenário como argumento
            tempo_final = time.time() - start_time
            tempo_total += tempo_final
            print(f"Próxima solicitação em {delay} segundos. Tempo total usado: {tempo_total}s")
            if tempo_total + delay <= timeout:
                time.sleep(delay)
    except Exception as e:
        print(f"Erro durante o benchmarking: {e}")

def benchmark_node(node_name, cursor, conn, id_gen, cenario_name):
    nodes[node_name] += 1
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False) as tmp_file:
        print(f"Request {nodes[node_name]} on {node_name}")
        node_ip = node_ip_addresses[node_name]
        cmd = f"ab -s 30 -c 1 -n 1 -r http://[{node_ip}]/ > {tmp_file.name}"
        try:
            subprocess.run(cmd, shell=True, check=True)
            tmp_file.seek(0)
            parse_tsv_and_log_results(tmp_file.name, cursor, node_name, cenario_name, conn, id_gen)  # Usa o mesmo nome de cenário
        except subprocess.CalledProcessError as e:
            print(f"Error benchmarking {node_name}: {e}")
        finally:
            os.remove(tmp_file.name)

def countdown(countdown_duration):    
    hours, remainder = divmod(countdown_duration, 3600)
    minutes, seconds = divmod(remainder, 60)

    print(f"{hours}h:{minutes}m:{seconds}s restante...")
    for remaining in range(countdown_duration - 1, 0, -1):
        time.sleep(1)
        hours, remainder = divmod(remaining, 3600)
        minutes, seconds = divmod(remainder, 60)
        sys.stdout.write("\r")
        sys.stdout.write("{:02d}h:{:02d}m:{:02d}s restante...".format(hours, minutes, seconds))
        sys.stdout.flush()
    sys.stdout.write("\n")

def main():
    
    benchmark_duration = 5 * 60   # 5 minutos em segundos    
    countdown_duration = 300  # 5 minutos
    threads = []

    for port, log_file in MOTE_CONFIG.items():
        thread = threading.Thread(target=handle_connection, args=(port, log_file))
        thread.start()
        threads.append(thread)

    benchmark_thread = threading.Thread(target=countdown_and_benchmark, args=(benchmark_duration,))
    countdown_thread = threading.Thread(target=countdown, args=(countdown_duration,))
    benchmark_thread.start()
    countdown_thread.start()


    for thread in threads:
        thread.join()

    countdown_thread.join()

if __name__ == "__main__":
    main()
