# candau

# repo per la configuracio d'un dispositiu candau per BLE

TMP="$(mktemp -d)" && cd "$TMP"
curl -sL https://github.com/javichi338/candau/archive/refs/heads/main.tar.gz | tar -xz --strip-components=2 candau-main/autoCandado

# CAL AFEGIR EL ENROLL TOKEN PER CADA CANDAU
chmod +x autoConfCandau.sh
sudo ./autoConfCandau.sh "wss://nattech.fib.upc.edu:40571/api/ws/locks" pub.pem server.crt "e6062400f717f3b095288a90681c474fc1d30daf0705434380561ed54debe69d"

cd ~ && rm -rf "$TMP"