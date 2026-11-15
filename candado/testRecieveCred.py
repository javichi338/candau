import asyncio
import json
import hashlib
from opsDB.loggBle import registerLog
from testCred import validarCredencial

from bless import (
    BlessServer,
    GATTCharacteristicProperties,
    GATTAttributePermissions,
)
CONFIG_FILE = "/opt/candado/etc/configCandau.json"

UUID_CANDADO = ""
UUID_SERVICIO = "076f3d07-7704-4a7c-9128-2ba5ad77de90"

server = None

def resumen(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]

def on_write(characteristic, value, **kwargs):
    
    credencial = bytes(value).decode("utf-8", errors="replace")
    
    resultado = validarCredencial(credencial)
    
    registerLog(
        "VALIDAR CREDENCIAL", 
        resultado.get("result"), 
        resultado.get("lockId"), 
        resultado.get("idUser"),
        resultado.get("idReserva"), 
        resumen(credencial),     
        resultado.get("message")
    )

    res = {"code": resultado.get("code"), "status": resultado.get("result"), "message": resultado.get("message")}
    characteristic.value = bytearray(json.dumps(res).encode("utf-8"))
    server.update_value(UUID_SERVICIO, UUID_CANDADO)  
    
    # LOGICA FISICA CANDADO encender led ns

async def main():
    
    global server,UUID_CANDADO
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f); 
            name_ble = config['nameBLE']
            UUID_CANDADO = config['UUID']
            message = f"Anunciando dispositivo BLE ({name_ble})"

    except Exception as err:
            message = 'No se puede anunciar el dispositivo BLE sin el candado configurado'
            registerLog('ANUNCIAR DISPOSITIVO BLE', res='denegado', msg=message)
            return
    
    
    loop = asyncio.get_running_loop()
    server = BlessServer(name=name_ble, loop=loop)

    await server.add_new_service(UUID_SERVICIO)
    await server.add_new_characteristic(
        UUID_SERVICIO, UUID_CANDADO,
        GATTCharacteristicProperties.read
        | GATTCharacteristicProperties.write
        | GATTCharacteristicProperties.notify,
        None,
        GATTAttributePermissions.readable | GATTAttributePermissions.writeable)
    
    server.write_request_func = on_write

    await server.start()
    
    registerLog('ANUNCIAR DISPOSITIVO BLE', res='permitido', lockid=config['lockId'], clavefirma=resumen(config['publicKey']), msg=message)
    await asyncio.Event().wait()      


    
if __name__ == "__main__":
    asyncio.run(main())
