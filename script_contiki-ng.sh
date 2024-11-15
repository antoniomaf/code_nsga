#!/bin/bash

# Define o tempo de contagem regressiva em segundos
countdown_time=12

# Define opções de memória para o Java
JAVA_OPTS="-Xms4g -Xmx4g"

# Caminho para o arquivo jar Cooja
COOJA_JAR="/home/.../.../contiki-ng/tools/cooja/dist/cooja.jar"

# Define limite de core dump para ilimitado
ulimit -c unlimited

# Caminho para o script de simulação
SIMULATION_SCRIPT="/home/.../.../metrica/cenario_6x6_15min.csc"

# Caminho para o diretório raiz do Contiki-NG
CONTIKI_NG_ROOT="/home/.../.../contiki-ng"

# Arquivo de log de saída para simulação Cooja
COOJA_LOG="/home/.../.../Logs_contiki/cooja_output.log"

# Arquivo de log de saída para tunslip6
TUNSLIP6_LOG="/home/.../.../Logs_contiki/tunslip6_output.log"

# Bloqueio de arquivo para garantir execução única de filtragem de dados
LOCK_FILE="/tmp/data_filtering.lock"

cleanup_function() {
    echo "Executando limpeza..."
    sudo pkill -f 'java -jar /home/.../.../contiki-ng/tools/cooja.jar'
    sleep 5
    COOJA_PID=$(pgrep -f 'cooja.jar')
    if [ -n "$COOJA_PID" ]; then
        echo "Cooja ainda está em execução. Tentando finalizar pelo PID ($COOJA_PID)..."
        sudo kill -9 $COOJA_PID
    fi
    rm -f $LOCK_FILE
    # Outras operações de limpeza necessárias
}

# Captura sinais INT (Ctrl+C) e TERM (comando kill padrão) e executa a função de limpeza
trap 'echo "Interrompido"; cleanup_function; exit' INT TERM

start_data_filtering_and_upload() {
    if [ ! -e "$LOCK_FILE" ]; then
        touch "$LOCK_FILE"
        echo "Iniciando a filtragem de dados e, em seguida, iniciando o upload dos dados para o banco de dados..."        
        /home/.../anaconda3/bin/conda run -n base python3 /home/.../.../scripts/script_filtering_upload.py        
        echo "Filtragem de dados concluída!!!"
        echo "Entrada de dados concluída!!!"
        echo "Script finalizado!"        
        exit 0
    fi
}

check_cooja_status() {
    while true; do
        sleep 60
        if ! pgrep -f 'cooja.jar' > /dev/null; then
            echo "Cooja foi finalizado antes do tempo estabelecido."            
            echo "Encerrando script_socket_layer.py..."
            sudo pkill -f 'script_socket_layer.py'
            echo "script_socket_layer.py foi encerrado antes do tempo estabelecido."
            start_data_filtering_and_upload
            exit 1
        fi
    done
}

while true; do  
    # Iniciar simulação do Cooja em modo headless e redirecionar a saída para um arquivo de log
    echo "Iniciando o Cooja..."
    java $JAVA_OPTS -jar $COOJA_JAR -nogui=$SIMULATION_SCRIPT -contiki=$CONTIKI_NG_ROOT > $COOJA_LOG 2>&1 &    
    
    if [ $? -ne 0 ]; then
        echo "Erro ao iniciar o Cooja. Verifique o caminho do arquivo jar e o script de simulação."
        exit 1
    fi

    # Inicia a contagem regressiva
    echo "Aguardando o Cooja inicializar..."
    local_countdown_time=$countdown_time
    while [ $local_countdown_time -gt 0 ]; do
      echo -ne "$local_countdown_time\033[0K\r"
      sleep 1
      local_countdown_time=$((local_countdown_time - 1))
    done
    echo -ne "\n"

    # Encontra o PID do processo cooja.jar
    COOJA_PID=$(pgrep -f 'cooja.jar')

    # Defina um limite de tempo para a espera
    wait_limit=30 # 30 segundos de limite de tempo

    # Aguarda até que COOJA_PID seja inicializado, com limite de tempo
    while [ -z "$COOJA_PID" ] && [ $wait_limit -gt 0 ]; do
      echo "Aguardando o processo cooja.jar iniciar..."
      sleep 1
      COOJA_PID=$(pgrep -f 'cooja.jar')
      wait_limit=$((wait_limit - 1))
    done

    if [ -z "$COOJA_PID" ]; then
        echo "Processo cooja.jar não iniciado! Encerrando processos antigos e tentando novamente..."
        # Encerrar processos antigos
        sudo pkill -f 'java -jar /home/.../.../contiki-ng/tools/cooja.jar'
        # Tentar novamente
        continue
    else
        echo "cooja.jar (PID = $COOJA_PID) iniciado!!!"
        break  # Sair do loop se o processo for iniciado com sucesso
    fi
done

# Inicia a função de verificação de status em segundo plano
check_cooja_status &

echo "Tentando conectar o socket..."

cd /home/.../.../contiki-ng/examples/rpl-border-router/
make TARGET=cooja connect-router-cooja > $TUNSLIP6_LOG 2>&1 &
echo "Tunslip6 (nó sink) iniciado!!!"

sleep 5

cd /home/.../.../scripts
echo "Conexão do socket inicial..."
echo "Iniciando a coleta de dados na camada de aplicação..."

# Inicie o script de conexão do soquete em segundo plano
/home/.../anaconda3/bin/conda run -n base python3 /home/.../.../scripts/script_socket_layer.py &
# Salvar o PID do último processo em segundo plano
SOCKET_LAYER_PID=$!

# Defina um tempo de contagem regressiva de 5 minutos (300 segundos)
countdown_time=300
echo "Iniciando conexão de soquete e coleta de dados na camada de aplicação..."

# Comece a contagem regressiva
while [ $countdown_time -gt 0 ]; do
  # Calcular minutos e segundos a partir do countdown_time
  minutes=$((countdown_time / 60))
  seconds=$((countdown_time % 60))
  
  # Exibe a contagem regressiva no formato MM:SS
  echo -ne "Countdown: $(printf "%02d:%02d" $minutes $seconds)\r"
  
  # Sleep por 1 segundo
  sleep 1
  
  # Diminua o countdown_time
  countdown_time=$((countdown_time - 1))
  
  # Verifique se o Cooja ainda está em execução
  if ! pgrep -f 'cooja.jar' > /dev/null; then
    echo -ne "\nCooja foi finalizado antes do tempo estabelecido."
    # 6 motes
    echo "Encerrando script_socket_layer.py..."
    sudo pkill -f 'script_socket_layer.py'
    echo "script_socket_layer.py foi encerrado antes do tempo estabelecido."
    start_data_filtering_and_upload
    exit 1
  fi
done
echo -ne "\n"

# Exibe mensagem de sucesso se a contagem regressiva terminar corretamente
echo "Tempo total da simulação concluído com sucesso!"

# Aguarde a conclusão do script da camada de soquete se ele ainda estiver em execução
wait $SOCKET_LAYER_PID

echo "Socket connection and data collection at the application layer finished."

# Garante que o script de monitoramento Cooja seja encerrado para evitar execução dupla
pkill -f check_cooja_status

# Esse comando irá encerrar todos os processos que correspondem à expressão regular fornecida
sudo pkill -f 'java -jar /home/.../.../contiki-ng/tools/cooja.jar'

# Wait for Cooja to terminate
sleep 5
COOJA_PID=$(pgrep -f 'cooja.jar')
if [ -n "$COOJA_PID" ]; then
    echo "Cooja ainda está em execução. Tentando finalizar pelo PID ($COOJA_PID)..."
    sudo kill -9 $COOJA_PID
fi

while pgrep -f 'cooja.jar' > /dev/null; do
    echo "Aguardando o término do Cooja..."
    sleep 1
done

echo "cooja.jar processo não encontrado. Prosseguindo com os próximos passos."
start_data_filtering_and_upload
# Remove o arquivo de bloqueio ao final do script
rm -f $LOCK_FILE
exit 0