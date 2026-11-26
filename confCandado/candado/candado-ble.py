import asyncio
import json
import hashlib
from opsDB.loggBle import registerLog
from testCred import validarCredencial
import RPi.GPIO as GPIO

LED_VERMELL = 16
LED_VERD = 18 ## PIN RASBERRY LED

from bless import (
    BlessServer,
    GATTCharacteristicProperties,
    GATTAttributePermissions,
)
CONFIG_FILE = "/opt/candado/etc/configCandau.json"

UUID_CANDADO = ""
UUID_SERVICIO = "076f3d07-7704-4a7c-9128-2ba5ad77de90"

server = None

tarea_led = None

async def secuencia_apertura():
    try:
        GPIO.output(LED_VERMELL, GPIO.LOW)
        GPIO.output(LED_VERD, GPIO.HIGH)
        await asyncio.sleep(5)                   
        for _ in range(5):                       
            GPIO.output(LED_VERD, GPIO.LOW)
            await asyncio.sleep(0.1)
            GPIO.output(LED_VERD, GPIO.HIGH)
            await asyncio.sleep(0.1)
    finally:                                      
        GPIO.output(LED_VERD, GPIO.LOW)
        GPIO.output(LED_VERMELL, GPIO.HIGH)

def resumen(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]

def on_write(characteristic, value, **kwargs):
    
    credencial = bytes(value).decode("utf-8", errors="replace")
    resultado = validarCredencial(credencial)
    
    registerLog(
        "VALIDAR CREDENCIAL", 
        resultado.get("result"), 
        resultado.get("idLock"), 
        resultado.get("idUser"),
        resultado.get("idReserva"), 
        resumen(credencial),     
        resultado.get("message")
    )

    res = {"status": resultado.get("code"), "message": resultado.get("message")}
    characteristic.value = bytearray(json.dumps(res).encode("utf-8"))
    server.update_value(UUID_SERVICIO, UUID_CANDADO)  
    
    # LOGICA FISICA CANDADO 
    global tarea_led
    if resultado.get("code") == 200:
        if tarea_led and not tarea_led.done():
            tarea_led.cancel()                      
        tarea_led = asyncio.get_running_loop().create_task(secuencia_apertura())


async def main():

    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(LED_VERMELL,GPIO.OUT)
    GPIO.setup(LED_VERD,GPIO.OUT)
    GPIO.output(LED_VERMELL,GPIO.HIGH)
    
    global server,UUID_CANDADO
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
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
    
    registerLog('ANUNCIAR DISPOSITIVO BLE', res='permitido', lockid=config['idLock'], clavefirma=resumen(config['publicKey']), msg=message)
    await asyncio.Event().wait()      


    
if __name__ == "__main__":
    asyncio.run(main())
