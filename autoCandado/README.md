## ORDRE OPERACIONS PER CONFIGURAR UN CANDA

curl -sL https://github.com/javichi338/candau/archive/refs/heads/main.tar.gz \
  | tar -xz --strip-components=3 candau-main/confAutoCandado/autoCandado
chmod +x autoConfCandau.sh

AFEGIR ENROLL TOKEN:

sudo ./autoConfCandau.sh "https://nattech.fib.upc.edu:40571/api/ws/locks" pub.pem server.crt "enroll-token"