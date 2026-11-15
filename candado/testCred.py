import json
import jwt
import time

CONFIG_FILE = "/opt/candado/etc/configCandau.json"
MARGEN_TIEMPO = 60

def _resultado(code, result, message=None, claims=None):
    r = {"code": code, "result": result}
    if message:
        r["message"] = message
    if claims:
        r["idReserva"] = claims.get("idReserva") if _es_numero(claims.get("idReserva")) else None
        r["lockId"] = claims.get("lockId") if _es_numero(claims.get("lockId")) else None
        r["idUser"] = claims.get("idUser") if _es_numero(claims.get("idUser")) else None
    return r

def _es_numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)

def validarCredencial(credencial_jwt: str) -> dict:
    if not isinstance(credencial_jwt, (str, bytes)):
        return _resultado(400, "FALLO AL VALIDAR: FORMATO_INCORRECTO", "La credencial debe ser una cadena de texto")
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
    except FileNotFoundError:
        return _resultado(503, "FALLO AL VALIDAR: NO_CONFIG", "El candado no esta configurado")
    except json.JSONDecodeError:
        return _resultado(500, "FALLO AL VALIDAR: CONFIG_INVALIDA", "El fichero config no es valido")
    except Exception as err:
        return _resultado(500, "FALLO AL VALIDAR: ERROR_INESPERADO", str(err))

    publicKey = config.get("publicKey")
    lockId = config.get("lockId")
    if not publicKey or not lockId:
        return _resultado(503, "FALLO AL VALIDAR: NO_CONFIG", "El candado no esta configurado")
    if not _es_numero(lockId):
        return _resultado(500, "FALLO AL VALIDAR: CONFIG_INVALIDA", "El fichero config no es valido")

    try:
        credencial = jwt.decode(
            credencial_jwt,
            publicKey,
            algorithms=["RS256"],
            options={
                "verify_exp": False,
                "verify_iat": False,
                "verify_signature": True
            }
        )
    except jwt.InvalidSignatureError:
        return _resultado(401, "FALLO AL VALIDAR: SIGNATURA_INVALIDA", "La credencial no ha sido firmada por el servidor")
    except jwt.DecodeError as err:
        return _resultado(400, "FALLO AL VALIDAR: FORMATO_INVALIDO", str(err))
    except Exception as err:
        return _resultado(500, "FALLO AL VALIDAR: ERROR_INESPERADO", str(err))

    claves_permitidas = {"idReserva", "lockId", "idUser", "iniReserva", "finReserva"}

    if set(credencial.keys()) != claves_permitidas:
        return _resultado(422, "FALLO AL VALIDAR: CAMPOS_NO_PERMITIDOS",
                          f"La credencial solo permite exactamente los campos: {', '.join(claves_permitidas)}", credencial)

    if not _es_numero(credencial.get("idReserva")) or not _es_numero(credencial.get("lockId")) or not _es_numero(credencial.get("idUser")):
        return _resultado(400, "FALLO AL VALIDAR: FORMATO_INCORRECTO", "idReserva, lockId e idUser deben ser numeros", credencial)
    if credencial.get("lockId") != lockId:
        return _resultado(403, "FALLO AL VALIDAR: CANDADO_INCORRECTO", f"La credencial solo sirve para la puerta {lockId}", credencial)

    inicio = credencial["iniReserva"]
    fin = credencial["finReserva"]

    if not _es_numero(inicio) or not _es_numero(fin):
        return _resultado(400, "FALLO AL VALIDAR: FORMATO_INCORRECTO", "iniReserva y finReserva deben ser numeros", credencial)

    if inicio >= fin:
        return _resultado(422, "FALLO AL VALIDAR: VENTANA_INVALIDA", "El fin de la reserva debe ser posterior al inicio", credencial)

    ahora = time.time()

    if ahora < inicio - MARGEN_TIEMPO:
        return _resultado(403, "FALLO AL VALIDAR: ANTES_DE_TIEMPO", "La reserva aun no ha empezado", credencial)
    if ahora >= fin + MARGEN_TIEMPO:
        return _resultado(410, "FALLO AL VALIDAR: RESERVA_FINALIZADA", "La reserva ha terminado", credencial)

    return _resultado(200, "ACCESO PERMITIDO", "La credencial es valida", credencial)