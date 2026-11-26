# candau

# repo per la configuracio d'un dispositiu candau per BLE

nmap -sn 10.42.0.0/24
ssh pti@ip

TMP="$(mktemp -d)" && cd "$TMP"
curl -sL https://github.com/javichi338/candau/archive/refs/heads/main.tar.gz | tar -xz --strip-components=2 candau-main/autoCandado

# CAL AFEGIR EL ENROLL TOKEN PER CADA CANDAU
chmod +x autoConfCandau.sh
sudo ./autoConfCandau.sh "wss://nattech.fib.upc.edu:40571/api/ws/locks" pub.pem server.crt "e93d8880a6b9ba5276f5a2c6dce63382efdfa93babd3c509d75984a4a9d9318f"

cd ~ && rm -rf "$TMP"