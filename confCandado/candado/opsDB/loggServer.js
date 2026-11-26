const sqlite3 = require('sqlite3');
const util = require('util');
const LOGS_FILE = "/opt/candado/logs/logs.db";


function registerLog(action, result, lockid = null, clavePublica = null, msg = null) {
  return new Promise((resolve) => {
    const con = new sqlite3.Database(LOGS_FILE, (err) => {
      if (err) {
        console.error('registerLog: no se pudo abrir la BD:', err.message);
        return resolve(false);
      }

      con.configure('busyTimeout', 5000);

      con.serialize(() => {
        con.run('PRAGMA synchronous=NORMAL;');
        con.run(
          `INSERT INTO logsExpress (evento, resultado, idlock, clavePublica, msg)
           VALUES (?, ?, ?, ?, ?)`,
          [action, result, lockid, clavePublica, msg],
          function (err) {
            con.close();
            if (err) {
              console.error('registerLog: error al insertar:', err.message);
              return resolve(false);
            }
            resolve(true);
          }
        );
      });
    });
  });
}

function exportarLogs() {
    return new Promise((resolve, reject) => {
        const con = new sqlite3.Database(LOGS_FILE, async (err) => {
            if (err) {
                console.error(`[ERROR DB SERVER] No se pudo abrir la DB: ${err.message}`);
                return reject(err);
            }

            const run = util.promisify(con.run.bind(con));
            const all = util.promisify(con.all.bind(con));

            try {
                con.configure('busyTimeout', 5000);
                await run('BEGIN IMMEDIATE');

                const logsBLE = await all("DELETE FROM logsBle WHERE fecha > datetime('now', '-1 days') RETURNING *");
                const logsExpress = await all("DELETE FROM logsExpress WHERE fecha > datetime('now', '-1 days') RETURNING *");

                await run('COMMIT');
                resolve({ logsBLE, logsExpress });

            } catch (e) {
                await run('ROLLBACK').catch(() => { });
                resolve("ERROR");

            } finally {
                con.close();
            }
        });
    });
}

module.exports = { registerLog, exportarLogs };
