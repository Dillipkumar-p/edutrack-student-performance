
import mysql.connector

try:
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Dillip@2008",
        database="student_performance_db"
    )

    if connection.is_connected():
        print("MySQL connection successful!")

        cursor = connection.cursor()
        cursor.execute("SHOW TABLES")

        print("\nTables in the database:")
        for table in cursor.fetchall():
            print(table[0])

        cursor.close()
        connection.close()

except mysql.connector.Error as error:
    print("MySQL connection failed!")
    print(error)
