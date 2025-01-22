import mysql.connector
from mysql.connector import Error

hostname = "6-1sh.h.filess.io"
database = "tokoku_digluckygo"
port = "3307"
username = "tokoku_digluckygo"
password = "5f59f8e9ac5170f2b1d9ec42397133766b7eb894"

try:
    connection = mysql.connector.connect(host=hostname, database=database, user=username, password=password, port=port)
    if connection.is_connected():
        db_Info = connection.get_server_info()
        print("Connected to MySQL Server version ", db_Info)
        cursor = connection.cursor()
        cursor.execute("select database();")
        record = cursor.fetchone()
        print("You're connected to database: ", record)

except Error as e:
    print("Error while connecting to MySQL", e)
finally:
    if connection.is_connected():
        cursor.close()
        connection.close()
        print("MySQL connection is closed")

