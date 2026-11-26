const WebSocket = require('ws');
const fs = require('fs');
const crypto = require('crypto');
const path = require('path');
const util = require('util');
const { execFile } = require('child_process');
const { registerLog, exportarLogs } = require('./opsDB/loggServer');
const execFilePromise = util.promisify(execFile);


const CONFIG_FILE = '/opt/candado/etc/configCandau.json';
const CONFIGSOCKET_FILE = '/opt/candado/etc/configSocket.json';
const MASTER_KEY = "PTISERVER";
 
const BACKOFF_MIN_MS = 1000;
const BACKOFF_MAX_MS = 60000;
const BACKOFF_REBUIG_MIN_MS = 60000;  
const BACKOFF_REBUIG_MAX_MS = 300000;

const MAX_MISSATGE = 5 * 1024 * 1024;  
const MAX_CUA = 10;
 
function log(...a) {
  console.log(new Date().toISOString(), ...a);
}
 
let esConfigurable = false;
let temporizador = null;

function resumen(texto) {
  return crypto.createHash('sha256').update(texto, 'utf8').digest('hex').slice(0, 16);
}

function cerrarConfiguracion() {
  esConfigurable = false;
  clearTimeout(temporizador);
}

function denegar(accion, status, message, id = null, hash = null) {
  registerLog(accion, 'denegado', id, hash, message);
  return { status, body: { status: 'error', message } };
}

function validarEstructuraConfig(data) {

  if (!data || typeof data !== 'object') {
    return 'La peticion debe ser un objeto json';
  }

  const clavesPermitidas = ['lockId', 'publicKey', 'secretKey', 'firmaConf'];
  const clavesRecibidas = Object.keys(data);

  if (clavesRecibidas.length !== clavesPermitidas.length || !clavesRecibidas.every(key => clavesPermitidas.includes(key))) {
    return `Estructura invalida: solo se permiten exactamente los campos [${clavesPermitidas.join(', ')}]. Ningun campo extra.`;
  }

  if (!Number.isSafeInteger(data.lockId) || data.lockId <= 0) {
    return 'El campo idLock es obligatorio y debe ser un entero positivo';
  }
  if (!data.publicKey || typeof data.publicKey !== 'string') {
    return 'El campo publicKey es obligatorio y debe ser un string';
  }
  if (typeof data.secretKey !== 'string' || !/^[0-9a-f]{64}$/i.test(data.secretKey) ) {
    return 'El campo secretKey debe ser un string hexadecimal de 64 caracteres (32 bytes)';
  }
  if (typeof data.firmaConf !== 'string' || !data.firmaConf) {
    return 'El campo firmaConf es obligatorio y debe ser un string';
  }
  try {
    const k = crypto.createPublicKey(data.publicKey);
    if (k.asymmetricKeyType !== 'rsa') return 'La publicKey debe ser RSA';
  } catch (err) {
    return 'El formato de publicKey no es valido';
  }
  
  let actual;
  try {
    actual = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8'));
  } catch (err) {
    return 'No se pudo leer la configuracion actual';
  }
  if (!actual.publicKey) {
    return 'La configuracion actual no tiene publicKey con la que verificar';
  }

  const firmado = JSON.stringify({
    lockId: data.lockId,
    publicKey: data.publicKey,
    secretKey: data.secretKey,
  });

  try {
    const ok = crypto.verify(
      'sha256',
      Buffer.from(firmado),
      actual.publicKey,
      Buffer.from(data.firmaConf, 'base64')
    );
    if (!ok) return 'Firma de configuracion invalida';
  } catch (err) {
    return 'Firma de configuracion invalida';
  }

  return null;
}

async function actualitzarNomBluetooth(idLock) {

  const nouNom = `Candado-n${idLock}`;
  try {
    await execFilePromise('hostnamectl', ['set-hostname', nouNom]);
    await execFilePromise('systemctl', ['restart', 'bluetooth']);
    await execFilePromise('systemctl', ['restart', 'candado-ble']);
    return null;

  } catch (error) {
    return `Error al cambiar el hostname: ${error.message}`;
  }
}

// POST /unlock  (body: { masterkey })
function desbloquejar(masterkey) {
  const ACCION = 'DESBLOQUEO CONFIGURACION';
  if (!masterkey || masterkey !== MASTER_KEY) {
    return denegar(ACCION, 400, 'Usuario no autenticado intenta cambiar el estado configuracion');
  }

  esConfigurable = true;
    clearTimeout(temporizador);
    temporizador = setTimeout(() => {
      esConfigurable = false; // 30s per op
    }, 30000);
    registerLog(ACCION, 'permitido', null, null);
   
    return { status: 200, body: { status: 'ok', esConfigurable: true, tiempo_restante: '30s' } };
}

// POST /config  (body: { idLock, publicKey, secretKey, firmaConf })
async function aplicarConfig(initialConf) {
  const ACCION = 'ESTABLECER CONFIGURACION';
  try {
    if (!esConfigurable) {
      return denegar(ACCION, 400, 'El estado de configuracion esta desactivado');
    }
    const configInvalid = validarEstructuraConfig(initialConf);
    if (configInvalid) {
      return denegar(ACCION, 400, configInvalid);
    }

    const id = initialConf.lockId;
    const infoserver = { id, UUID: crypto.randomUUID(), BLE_NAME: `Candado-n${id}` };

    const config = {
      idLock: initialConf.lockId,
      publicKey: initialConf.publicKey,
      secretKey: initialConf.secretKey,
      UUID: infoserver.UUID,
      nameBLE: infoserver.BLE_NAME
    };
    fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2), { mode: 0o600 });

    const err = await actualitzarNomBluetooth(id);
    if (err) {
      return denegar(ACCION, 500, `Configuracion guardada, pero ${err}`, id, resumen(initialConf.publicKey));
    }

    const message = 'Configuracion aplicada correctamente';
    cerrarConfiguracion();

    registerLog(ACCION, 'permitido', id, resumen(config.publicKey), message);
    return { status: 200, body: { status: 'ok', res: infoserver, message } };

  } catch (error) {
    return denegar(ACCION, 500, error.message);
  }
}

// GET /logs
async function obtenirLogs() {
  const ACCION = 'OBTENER LOGS ANTIGUOS';
  try {
    if (!esConfigurable) {
      return denegar(ACCION, 400, 'El estado de configuracion esta desactivado');
    }

    if (!fs.existsSync(CONFIG_FILE)) {
      return denegar(ACCION, 500, 'Error: no existe el archivo de configuracion ');
    }

    const config = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8'));
    const key = config.secretKey

    if (!key) {
      return denegar(ACCION, 500, 'Error: no se encontro la clave para logs en el fichero de configuracion');
    }

    const logs = await exportarLogs();
    if (logs === "ERROR") {
      return denegar(ACCION, 500, 'Error al obtener logs antiguos');
    }
    const dades = JSON.stringify({
      idLock: config.idLock,
      logs: logs
    });

    const firma = crypto.createHmac('sha256', key)
      .update(dades,'utf8')
      .digest('hex');

    const payload = { dades, firma };

    const nombre = `logs_${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
    const destino = path.join('/opt/candado/etc', nombre);
    fs.writeFileSync(destino, JSON.stringify(payload),{mode: 0o600});
  
    registerLog(ACCION, 'permitido', config.idLock, null, 'Logs antiguos obtenidos correctamente');
    return { status: 200, body: { status: 'ok', logs: payload } };

  } catch (error) {
        return denegar(ACCION, 500, error.message);
  }
}

const RUTES = {
  'POST /unlock': (body) => desbloquejar(body?.masterkey),
  'POST /config': (body) => aplicarConfig(body),
  'GET /logs': () => obtenirLogs(),
};
 

function carregarClientConfig() {
  const cfg = JSON.parse(fs.readFileSync(CONFIGSOCKET_FILE, 'utf8'));
  if (typeof cfg.backendUrl !== 'string' || !cfg.backendUrl) {
    throw new Error('Falta backendUrl a ' + CONFIGSOCKET_FILE);
  }
  if (!cfg.backendUrl.startsWith('wss://') && process.env.ALLOW_INSECURE !== '1') {
    throw new Error('backendUrl ha de ser wss:// (ALLOW_INSECURE=1 només per a proves)');
  }
  return cfg;
}
 
function guardarTokenDispositiu(token) {
  const cfg = JSON.parse(fs.readFileSync(CONFIGSOCKET_FILE, 'utf8'));
  cfg['x-device-token'] = token;
  fs.writeFileSync(CONFIGSOCKET_FILE, JSON.stringify(cfg, null, 2), { mode: 0o600 });
}
 
let backoff = BACKOFF_MIN_MS;
let watchdog = null;
let reconnectAra = false;   
let aturant = false;
let cua = Promise.resolve();
let enCua = 0;
 
function connectar() {
  let cfg;
  try {
    cfg = carregarClientConfig();
  } catch (err) {
    log('Configuració del client invàlida:', err.message);
    process.exit(1);
  }
 
  const tokenDispositiu = cfg['x-device-token'] || null; 
  const headers = {};
  if (tokenDispositiu) {
    headers['x-device-token'] = tokenDispositiu;
  } else if (cfg['x-enroll-token']) {
    headers['x-enroll-token'] = cfg['x-enroll-token'];
  } else {
    log('No hi ha cap token (ni de dispositiu ni d\'enrolament). Aturo.');
    process.exit(1);
  }
 
  log(`Connectant a ${cfg.backendUrl} (${tokenDispositiu ? 'token de dispositiu' : 'enrolament'})`);
  const ws = new WebSocket(cfg.backendUrl, { headers, maxPayload: MAX_MISSATGE });
 
  const reiniciarWatchdog = () => {
    clearTimeout(watchdog);
    watchdog = setTimeout(() => {
      log('Sense senyals del backend, tanco la connexió');
      ws.terminate();
    }, 60000);
  };
 
  ws.on('open', () => {
    log('Connectat al backend');
    backoff = BACKOFF_MIN_MS;
    reiniciarWatchdog();
  });

  ws.on('ping', reiniciarWatchdog); // ws respon amb pong automàticament

  ws.on('message', (raw) => {
    reiniciarWatchdog();
    tractarMissatge(ws, raw.toString());
  });

  ws.on('error', (err) => log('Error de socket:', err.message));

  ws.on('close', (code, reason) => {
    clearTimeout(watchdog);
    if (aturant) return;
 
    let espera;
    if (reconnectAra) {
      reconnectAra = false;
      espera = 500;
    } else if (code === 1008) {

      backoff = Math.max(backoff, BACKOFF_REBUIG_MIN_MS);
      espera = backoff + Math.random() * 5000;
      backoff = Math.min(backoff * 2, BACKOFF_REBUIG_MAX_MS);
      log(`Backend ha rebutjat la connexió (${reason.toString() || 'sense motiu'})`);
    } else {
      espera = backoff + Math.random() * 500;
      backoff = Math.min(backoff * 2, BACKOFF_MAX_MS);
    }
    log(`Desconnectat (${code}), reconnecto en ${Math.round(espera)} ms`);
    setTimeout(connectar, espera);
  });
}
 
function tractarMissatge(ws, raw) {
  let msg;
  try {
    msg = JSON.parse(raw);
  } catch {
    return;
  }
 
  // Enrolament -> rebem token dispositiu
  if (msg.type === 'SET_TOKEN') {
    if (typeof msg.token !== 'string' || !msg.token) return;
    try {
      guardarTokenDispositiu(msg.token);
    } catch (err) {
      log('No s\'ha pogut desar el token de dispositiu:', err.message);
      return ws.terminate();
    }
    log('Token de dispositiu desat. Reconnecto per confirmar l\'enrolament');
    reconnectAra = true;
    return ws.close(1000, 'enrolat');
  }
 
  // Petició del backend: { id, method, path, body }
  if (msg.id && msg.method && msg.path) {
    if (enCua >= MAX_CUA) {
      return respondre(ws, msg.id, 429, { status: 'error', message: 'Candau ocupat' });
    }
    enCua++;
    cua = cua
      .then(() => tractarPeticio(ws, msg))
      .catch((err) => log('Error tractant la petició:', err.message))
      .finally(() => { enCua--; });
  }
}
 
async function tractarPeticio(ws, { id, method, path: ruta, body }) {
  const handler = RUTES[`${method} ${ruta}`];
  if (!handler) {
    return respondre(ws, id, 404, { status: 'error', message: 'Ruta no permesa' });
  }
  let resultat;
  try {
    resultat = await handler(body);
  } catch (err) {
    resultat = { status: 500, body: { status: 'error', message: err.message } };
  }
  respondre(ws, id, resultat.status, resultat.body);
}
 
function respondre(ws, id, status, body) {
  if (ws.readyState !== 1) return;
  let text = JSON.stringify({ id, status, body });
  if (Buffer.byteLength(text) > MAX_MISSATGE - 1024) {
    text = JSON.stringify({ id, status: 413, body: { status: 'error', message: 'Resposta massa gran' } });
  }
  ws.send(text, (err) => {
    if (err) log('No s\'ha pogut enviar la resposta:', err.message);
  });
}
 
process.on('unhandledRejection', (err) => log('Promesa rebutjada sense gestionar:', err));
process.on('SIGTERM', () => { aturant = true; process.exit(0); });
process.on('SIGINT', () => { aturant = true; process.exit(0); });
 
connectar();
