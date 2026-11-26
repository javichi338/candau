# candau

# repo per la configuracio d'un dispositiu candau per BLE

nmap -sn 10.42.0.0/24
ssh pti@ip

TMP="$(mktemp -d)" && cd "$TMP"
curl -sL https://github.com/javichi338/candau/archive/refs/heads/main.tar.gz | tar -xz --strip-components=2 candau-main/autoCandado

# CAL AFEGIR EL ENROLL TOKEN PER CADA CANDAU
chmod +x autoConfCandau.sh
sudo ./autoConfCandau.sh "wss://nattech.fib.upc.edu:40571/api/ws/locks" pub.pem server.crt "11ef98f51f12f0e023891361efb2981a6a1395b11385550beec3d02089c5a306"

cd ~ && rm -rf "$TMP"