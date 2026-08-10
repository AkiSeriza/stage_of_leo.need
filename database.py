import aiosqlite

class Database:
    def __init__(self, conn):
        self.conn = conn

    async def execute(self, query, params=()):
        return await self.conn.execute(query, params)

    async def fetchone(self, query, params=()):
        cursor = await self.conn.execute(query, params)
        row = await cursor.fetchone()
        await cursor.close()
        return row

    async def fetchall(self, query, params=()):
        cursor = await self.conn.execute(query, params)
        rows = await cursor.fetchall()
        await cursor.close()
        return rows

    async def commit(self):
        await self.conn.commit()

    async def write(self, query, params=()):
        print(f"Executing query: {query} with params: {params}")
        await self.conn.execute(query, params)
        print("Query executed successfully.")
        await self.conn.commit()
        print("Query executed and committed successfully.")

    async def change_balance(self, userID, value, reason,time):
        checkif = await self.fetchone("SELECT * FROM econ WHERE UserID = ?",(userID,))
        if checkif == None:
            await self.write("INSERT INTO econ (UserID) VALUES (?)", (userID,))
        await self.write(
            "UPDATE econ SET Balance = Balance + ? WHERE UserID = ?", (value,userID)
        )
        new_balance = (await self.fetchone("SELECT Balance FROM econ WHERE UserID = ?",(userID,)))[0]
        await self.write("INSERT INTO balancehistory (UserID, BalanceChange, BalanceAfter,Timestamp,Reason) VALUES (?,?,?,?,?)",(userID,value,new_balance,time,reason))
         
    async def close(self):
        await self.conn.close()