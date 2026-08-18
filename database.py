import os
import asyncpg
from dotenv import load_dotenv
load_dotenv()

#fuck it we ball 
class DatabaseError(Exception):
    pass

class Database:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    @classmethod
    async def create(cls):
        dsn = os.getenv("POSTGRESQL") or os.getenv("DATABASE_URL")

        if not dsn:
            raise RuntimeError(
                "Database URL not configured. "
                "Set POSTGRESQL or DATABASE_URL in the environment."
            )

        dsn = dsn.strip()

        pool = await asyncpg.create_pool(
            dsn,
            ssl="require",
            statement_cache_size=0
        )

        return cls(pool)

    async def execute(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetchone(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchall(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def write(self, query: str, *args):
        print(f"Executing query: {query}")
        print(f"Parameters: {args}")

        async with self.pool.acquire() as conn:
            result = await conn.execute(query, *args)

        print("Query executed successfully.")
        return result

    async def change_balance(self, userID, value, reason, time):
        checkif = await self.fetchone(
            "SELECT * FROM econ WHERE UserID = $1",
            userID
        )

        if checkif is None:
            await self.write(
                "INSERT INTO econ (UserID) VALUES ($1)",
                userID
            )

        await self.write(
            "UPDATE econ SET Balance = Balance + $1 WHERE UserID = $2",
            value,
            userID
        )

        new_balance = await self.fetchone(
            "SELECT Balance FROM econ WHERE UserID = $1",
            userID
        )

        await self.write(
            """
            INSERT INTO balancehistory
                (UserID, BalanceChange, BalanceAfter, Timestamp, Reason)
            VALUES ($1, $2, $3, $4, $5)
            """,
            userID,
            value,
            new_balance[0],
            time,
            reason
        )

    async def bank_deposit(
        self,
        userID,
        deposit,
        currenttime,
        bank,
        isRob
    ):
        current_bal = await self.fetchone(
            "SELECT Balance FROM econ WHERE UserID = $1",
            userID
        )

        current_bal = current_bal[0] if current_bal else 0

        current_bank_balance = await self.fetchone(
            """
            SELECT
                ba.Balance,
                ba.LastDepositTime,
                b.MinimumDepositTime,
                b.MinimumDeposit
            FROM banks b
            LEFT JOIN bankaccounts ba
                ON b.ShortName = ba.BankType
                AND ba.UserID = $1
            WHERE b.ShortName = $2
            """,
            userID,
            bank
        )
        #help 
        print(f"Bank {bank} has received request")

        if current_bank_balance is None:
            return DatabaseError("Bank not found.")

        balance = (
            current_bank_balance[0]
            if current_bank_balance[0] is not None
            else 0
        )

        last_deposit = (
            current_bank_balance[1]
            if current_bank_balance[1] is not None
            else 0
        )

        min_cooldown = (
            current_bank_balance[2]
            if current_bank_balance[2] is not None
            else 0
        )

        min_deposit = (
            current_bank_balance[3]
            if current_bank_balance[3] is not None
            else 0
        )

        if (
            deposit < 0
            and currenttime - last_deposit < min_cooldown
            and isRob == 0
        ):
            return DatabaseError(
                "Withdrawal cooldown active. "
                "Please wait before making another withdrawal."
            )

        if min_deposit > deposit > 0:
            return DatabaseError(
                f"Deposit amount is below the minimum allowed (${min_deposit})."
            )

        if (
            balance + deposit < 0
            or (current_bal < deposit and isRob == 0)
        ):
            return DatabaseError(
                "Insufficient funds for this transaction."
            )

        log_msg = (
            f"Deposited to bank {bank}"
            if deposit > 0
            else f"Withdrew from bank {bank}"
        )

        if isRob == 0:
            await self.change_balance(
                userID,
                -deposit,
                log_msg,
                currenttime
            )

        if deposit < 0:
            print("Withdrawal")

            await self.write(
                """
                UPDATE bankaccounts
                SET Balance = Balance + $1
                WHERE UserID = $2
                  AND BankType = $3
                """,
                deposit,
                userID,
                bank
            )

        else:
            print("Deposit")

            await self.write(
                """
                INSERT INTO bankaccounts
                    (UserID, BankType, Balance, LastDepositTime)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (UserID, BankType)
                DO UPDATE SET
                    Balance = bankaccounts.Balance + EXCLUDED.Balance,
                    LastDepositTime = EXCLUDED.LastDepositTime
                """,
                userID,
                bank,
                deposit,
                currenttime
            )

    async def close(self):
        await self.pool.close()

