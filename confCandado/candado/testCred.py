import json
import jwt
import time

CONFIG_FILE = "/opt/candado/etc/configCandau.json"
MARGEN_TIEMPO = 60

def resultado(code, result, message=None, claims=None):
    r = {"code": code, "result": result}
    if message:
        r["message"] = message
    if claims:
        r["idReserva"] = claims.get("idReserva") if esNumero(claims.get("idReserva")) else None
        r["idLock"] = claims.get("idLock") if esNumero(claims.get("idLock")) else None
        r["idUser"] = claims.get("idUser")[:128] if isinstance(claims.get("idUser"), str) else None
    return r

def esNumero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)

def validarCredencial(credencial_jwt: str) -> dict:
    if not isinstance(credencial_jwt, (str, bytes)):
        return resultado(400, "FALLO AL VALIDAR: FORMATO_INCORRECTO", "La credencial debe ser una cadena de texto")
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
    except FileNotFoundError:
        return resultado(503, "FALLO AL VALIDAR: NO_CONFIG", "El candado no esta configurado")
    except json.JSONDecodeError:
        return resultado(500, "FALLO AL VALIDAR: CONFIG_INVALIDA", "El fichero config no es valido")
    except Exception as err:
        return resultado(500, "FALLO AL VALIDAR: ERROR_INESPERADO", str(err))

    publicKey = config.get("publicKey")
    idLock = config.get("idLock")
    if not publicKey or not idLock:
        return resultado(503, "FALLO AL VALIDAR: NO_CONFIG", "El candado no esta configurado")
    if not esNumero(idLock):
        return resultado(500, "FALLO AL VALIDAR: CONFIG_INVALIDA", "El fichero config no es valido")

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
        return resultado(401, "FALLO AL VALIDAR: SIGNATURA_INVALIDA", "La credencial no ha sido firmada por el servidor")
    except jwt.DecodeError as err:
        return resultado(400, "FALLO AL VALIDAR: FORMATO_INVALIDO", str(err))
    except Exception as err:
        return resultado(500, "FALLO AL VALIDAR: ERROR_INESPERADO", str(err))

    claves_permitidas = {"idReserva", "idLock", "idUser", "ini", "fin"}

    if set(credencial.keys()) != claves_permitidas:
        return resultado(422, "FALLO AL VALIDAR: CAMPOS_NO_PERMITIDOS",
                          f"La credencial solo permite exactamente los campos: {', '.join(claves_permitidas)}", credencial)

    if not esNumero(credencial.get("idReserva")) or not esNumero(credencial.get("idLock")):
        return resultado(400, "FALLO AL VALIDAR: FORMATO_INCORRECTO", "idReserva y idLock deben ser numeros", credencial)
    if not isinstance(credencial.get("idUser"), str) or not credencial.get("idUser") or len(credencial.get("idUser")) > 128:
        return resultado(400, "FALLO AL VALIDAR: FORMATO_INCORRECTO", "idUser tiene que ser un string", credencial)
    if credencial.get("idLock") != idLock:
        return resultado(403, "FALLO AL VALIDAR: CANDADO_INCORRECTO", f"La credencial solo sirve para la puerta {idLock}", credencial)

    ini = credencial["ini"]
    fin = credencial["fin"]

    if not esNumero(ini) or not esNumero(fin):
        return resultado(400, "FALLO AL VALIDAR: FORMATO_INCORRECTO", "ini y fin deben ser numeros", credencial)

    if ini >= fin:
        return resultado(422, "FALLO AL VALIDAR: VENTANA_INVALIDA", "El fin de la reserva debe ser posterior al inicio", credencial)

    ahora = time.time()

    if ahora < ini - MARGEN_TIEMPO:
        return resultado(403, "FALLO AL VALIDAR: ANTES_DE_TIEMPO", "La reserva aun no ha empezado", credencial)
    if ahora >= fin + MARGEN_TIEMPO:
        return resultado(410, "FALLO AL VALIDAR: RESERVA_FINALIZADA", "La reserva ha terminado", credencial)

    return resultado(200, "ACCESO PERMITIDO", "La credencial es valida", credencial)