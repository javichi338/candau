import sqlite3,sys

LOGS_FILE = "/opt/candado/logs.db"


def registerLog(action, res=None, lockid=None, idUser=None, idReserva=None, clavefirma=None, msg=None):
    try:
        con = sqlite3.connect(LOGS_FILE,timeout=5.0)
        con.execute("PRAGMA synchronous=NORMAL;")
        curr = con.cursor()
        data = [
            action, res, lockid, idUser, idReserva, clavefirma, msg
        ]
        curr.execute("INSERT INTO logsBle (evento, resultado, idLock,idUser, idReserva, clavefirma, msg) VALUES(?,?,?,?,?,?,?)",data)
    
        con.commit()
        return True
    
    except sqlite3.Error as e:
        return False
    finally:
        if con:
            con.close()
    

    
