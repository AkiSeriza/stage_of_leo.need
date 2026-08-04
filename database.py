import aiosqlite

class Database:
    def __init__(self, conn):
        self.conn = conn

    async def execute(self, query, params=()):
        return await self.conn.execute(query, params)

    async def fetchone(self, query, params=()):
        cursor = await self.conn.execute(query, params)
        row = await cursor.fetchone()
        await cursor.close()   # <-- add this too
        return row

    async def fetchall(self, query, params=()):
        cursor = await self.conn.execute(query, params)
        return await cursor.fetchall()

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

    async def bank_deposit(self, userID, deposit, currenttime, bank, isRob):
        current_bal = await self.fetchone("SELECT Balance FROM econ WHERE UserID = ?", (userID,))
        current_bal = current_bal[0] if current_bal else 0
        current_bank_balance = await self.fetchone(
            """
            SELECT ba.Balance, ba.LastDepositTime, b.MinimumDepositTime, b.MinimumDeposit
            FROM banks b
            LEFT JOIN bankaccounts ba ON b.ShortName = ba.BankType AND ba.UserID = ?
            WHERE b.ShortName = ?
            """, 
            (userID, bank)
        )
        print(f"Bank {bank} has recieved request")
        if current_bank_balance is None:
            return aiosqlite.Error("Bank not found.")
        
        balance = current_bank_balance[0] if current_bank_balance[0] is not None else 0
        last_deposit = current_bank_balance[1] if current_bank_balance[1] is not None else 0
        min_cooldown = current_bank_balance[2] if current_bank_balance[2] is not None else 0
        min_deposit = current_bank_balance[3] if current_bank_balance[3] is not None else 0

        if deposit < 0 and (currenttime - last_deposit < min_cooldown) and isRob == 0:
            return aiosqlite.Error("Withdrawal cooldown active. Please wait before making another withdrawal.")
        
        if min_deposit > deposit > 0 :
            return aiosqlite.Error(f"Deposit amount is below the minimum allowed (${min_deposit}).")
        
        if balance + deposit < 0 or (current_bal < deposit  and isRob == 0): 
            return aiosqlite.Error("Insufficient funds for this transaction.")
        log_msg = f"Deposited to bank {bank}" if deposit > 0 else f"Withdrew from bank {bank}"

        if isRob == 0:
            await self.change_balance(userID, -deposit, log_msg, currenttime)
        
        if deposit < 0:
            print("Withdrawal")
            await self.write(
                "UPDATE bankaccounts SET Balance = Balance + ? WHERE UserID = ? AND BankType = ?", 
                (deposit, userID, bank)
            )
        else:
            print("Deposit")
            await self.write(
                """
                INSERT INTO bankaccounts (UserID, BankType, Balance, LastDepositTime) 
                VALUES (?, ?, ?, ?) 
                ON CONFLICT(UserID, BankType) DO UPDATE SET 
                    Balance = Balance + excluded.Balance,
                    LastDepositTime = excluded.LastDepositTime
                """, 
                (userID, bank, deposit, currenttime)
            )
            



    async def close(self):
        await self.conn.close()