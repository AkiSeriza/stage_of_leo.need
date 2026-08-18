
import asyncio
import discord
from discord.ext import commands
import random
from database import Database, DatabaseError
from discord.ext import commands, tasks
from discord import app_commands
import time
import math
import datetime

texted_lat_minute = set()
banks = [
    app_commands.Choice(name="Leo/Need and Co.", value="LNC"),
    app_commands.Choice(name="MOA MOA Savings", value="MMS"),
    app_commands.Choice(name="Rad Dogs Investemts", value="RDI"),
    app_commands.Choice(name="Bank of the Wonderful Stage", value="BWS"),
    app_commands.Choice(name="UnionCord at 25", value="UC25")
]

async def shared_bank_autocomplete(interaction: discord.Interaction, current: str):
    return [
    choice for choice in banks 
    if current.lower() in choice.name.lower()
    ][:25]

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db: Database = bot.db
        self.refresh.start()
        self.textcalcs.start()
        self.sets = set()


    @tasks.loop(seconds = 60)
    async def textcalcs(self):
        print(self.sets)
        current_time = int(time.time())
        for i in self.sets:
            await self.db.change_balance(i,150,"Message Sent", current_time)
        self.sets = set()

    @tasks.loop(hours=1)
    async def refresh(self):
        print("HI")
        current_time = int(time.time())
        await self.db.write("UPDATE econ SET Wantedness = Wantedness - 1 WHERE Wantedness > 0")
        await self.db.write("UPDATE econ SET Alertness = Alertness - 1 WHERE Alertness > 0")
        await self.db.write("""
            UPDATE bankaccounts
            SET Balance = FLOOR(Balance * (banks.InterestRate))
            FROM banks
            WHERE bankaccounts.BankType = banks.ShortName;
        """)
        print(f"Refreshed Wantedness and Alertness at {datetime.datetime.fromtimestamp(current_time)}")


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        self.sets.add(message.author.id)
        print("recieved")

    @app_commands.command(name="ichirob", description="Rob a user of their IchiCoins")
    async def ichirob(self, interaction: discord.Interaction, target: discord.User):
        current_time = time.time()
        user = interaction.user.id
        targetID = target.id
        row = await self.db.fetchone("SELECT LastStealTime FROM econ WHERE UserID = $1", user)
        laststeal = row[0] if row and row[0] is not None else 0
        if current_time - laststeal < 60:
            await interaction.response.send_message("You can chill out on robbing people, y'know?")
            return
        check = await self.db.fetchone("SELECT Balance FROM econ where UserID = $1", targetID)
        check1 = await self.db.fetchone("SELECT Wantedness FROM econ where UserID = $1", user)
        check1 = check1[0] if check1 else 0
        if check == None:
            await interaction.response.send_message(content="The User does not have an open account")
            return
        if check1 >=5:
            await interaction.response.send_message(content="Oopsie! You got caught ^^")
            await self.db.write("UPDATE econ SET Wantedness = Wantedness + 5 WHERE UserID = $1", current_time)
            return
        stealbal = check[0]
        if stealbal <= 0:
            await interaction.response.send_message(content="They're broke, sadly", ephemeral=True)
            return
        
        stealbal = math.floor(stealbal/25 if stealbal/25 < 100000 else 100000)
        reason1 = f"Balance stolen by {user}"
        reason2 = f"Balance stolen from {targetID}"
        await self.db.change_balance(targetID, -stealbal, reason1, current_time)
        await self.db.change_balance(user, stealbal, reason2, current_time)
        await self.db.write("UPDATE econ SET LastStealTime = $1, Wantedness = Wantedness + 3 WHERE UserID = $2", current_time, user)
        await interaction.response.send_message(content=f"Stole {stealbal} from {target.name}")



    @app_commands.autocomplete(bank = shared_bank_autocomplete)
    @app_commands.command(name="ichiheist", description="Attempt to rob a bank account for Ichicoins")
    async def ichiheist(self, interaction: discord.Interaction, bank: str, user: discord.User):
        print(f"User {interaction.user.id} is attempting to rob {user.id}'s bank account at {bank}")
        target = await self.db.fetchone("SELECT u.UserID, ba.Balance, u.Alertness, b.SecurityModifier FROM bankaccounts ba INNER JOIN banks b ON ba.BankType = b.ShortName INNER JOIN econ u ON ba.UserID = u.UserID WHERE u.UserID = $1 AND b.ShortName = $2", user.id, bank)
        print(target)
        robber = await self.db.fetchone("SELECT u.Wantedness, u.LuckModifier FROM econ u WHERE u.UserID = $1", interaction.user.id)
        print(robber)   
        assetchance = random.randint(1, 10)
        if robber[0] >= 7 or robber[0] >= assetchance :
            await interaction.response.send_message(content=f"FREEZE! THIS IS AN ASSET FREEZE!", ephemeral=True) 
            await self.db.write("DELETE FROM bankaccounts WHERE UserID = $1", interaction.user.id)
            await self.db.write("UPDATE econ SET balance = FLOOR(balance/2) WHERE UserID = $1", interaction.user.id)
            return
        if target is None:
            await interaction.response.send_message(content="The user does not have an account with that bank.", ephemeral=True)
            return
        """
        target[0] = UserID
        target[1] = Balance 
        robber[1] = LuckModifier 
        target[2] = Alertness 
        robber[0] = Wantedness 
        target[3] = SecurityModifier
        """
        print("Ok it got here")
        base_chance = 25
        target_defense = target[2] + target[3] 
        chance = base_chance - (target_defense * 3) - (robber[0] * 2) + (robber[1] * 4)
        chance = max(5, min(45, chance))
        print(chance)
        roll = random.randint(1, 50)
        if roll <= chance:
            robamount = math.floor(target[1] * random.uniform(0.2, 0.3))
            await self.db.bank_deposit(user.id, -robamount, int(time.time()), bank,1)
            await self.db.change_balance(interaction.user.id, robamount, f"Bank Heist from {target[0]}", int(time.time()))
            await interaction.response.send_message(content=f"Successfully robbed {robamount} from {user.name}'s bank account at {bank}!")
            await self.db.write("UPDATE econ SET Wantedness = Wantedness + 1 WHERE UserID = $1", interaction.user.id)
            await self.db.write("UPDATE econ SET Alertness = Alertness + 1 WHERE UserID = $1", user.id)
        else:
            await interaction.response.send_message(content=f"Failed to rob {user.name}'s bank account at {bank}. Better luck next time!", ephemeral=True)  
            await self.db.write("UPDATE econ SET Wantedness = 7 WHERE UserID = $1", interaction.user.id)

    @app_commands.command(name="ichiportfolio", description="Show current your current bank and investment portfolio")
    async def ichiportfolio(self, interaction: discord.Interaction):
        await interaction.response.defer()
        print("Hi")
        user = interaction.user.id
        balance_row = await self.db.fetchone(
            "SELECT Balance FROM econ WHERE UserID = $1",
            user
        )
        balance = balance_row[0] if balance_row else 0
        print(balance)

        current_balance = balance
        print(current_balance)
        embed = discord.Embed(
            title=f"{interaction.user.name}'s Balance",
            description=f"**Current Balance:** {current_balance} coins",
            color=discord.Color.gold()
        )
        banklist = ""
        sum = 0
        for i in ["LNC", "MMS", "RDI", "BWS", "UC25"]:
            balance = await self.db.fetchone(
                "SELECT Balance FROM bankaccounts WHERE UserID = $1 AND BankType = $2",
                user, i
            )
            balance = 0 if balance is None else balance[0]
            strings = f"**{i}** balance: {balance}"
            banklist = banklist + f"\n{strings}"
            sum += balance
        banklist = banklist + f"\nTotal Balance within Banks: {sum}"
        embed.add_field(name="Current Bank Balances",value=banklist)
        wanted = await self.db.fetchone("SELECT Wantedness FROM econ WHERE UserID = $1", interaction.user.id)
        wanted = 0 if wanted is None else wanted[0]
        stars = "✰Clean Record" if wanted == 0 else "★" * wanted 
        embed.add_field(name="Wanted Level", value=stars)
        print(interaction.user.display_avatar.url)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ichiledger", description="See your own transaction history for the last 24 hours")
    async def ichiledger(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user = interaction.user.id
        current_time = int(time.time())
        ledger = await self.db.fetchall(
            """
            SELECT BalanceChange, BalanceAfter, Timestamp, Reason
            FROM balancehistory
            WHERE Timestamp >= $1 AND UserID = $2
            ORDER BY Timestamp DESC
            LIMIT 100
            """,
            current_time - 86400, user
        )
        print(f"Ledger for user {user}: {ledger}")
        collapsedLedger = []
        runningTotal = 0
        currentTimestamp = 0
        i = 1
        for balChange, balAft, timestamp, reason in ledger:
            if reason != "Message Sent":
                if runningTotal != 0:
                    collapsedLedger.append(
                        (
                            i,
                            runningTotal,
                            currentBalance,
                            currentTimestamp,
                            "Passive Income"
                        )
                    )
                    i += 1
                    runningTotal = 0
                collapsedLedger.append(
                    (
                        i,
                        balChange,
                        balAft,
                        timestamp,
                        reason
                    )
                )
                i += 1
            else:
                runningTotal += balChange
                currentTimestamp = timestamp
                currentBalance = balAft
        if runningTotal != 0:
            collapsedLedger.append(
                (
                    i,
                    runningTotal,
                    currentBalance,
                    currentTimestamp,
                    "Passive Income"
                )
            )
        print(f"Collapsed Ledger for user {user}: {collapsedLedger}")

        embed = discord.Embed(
            title=f"{interaction.user.name}'s Transaction History (Last 24 Hours)",
            color=discord.Color.gold()
        )
        print(embed)

        if not collapsedLedger:
            embed.add_field(
                name="Recent Transactions",
                value="No transactions in the last 24 hours.",
                inline=False
            )
        else:
            history = "```\n"
            history += f"{'#':<3} {'Transaction':<25} {'Change':>10} {'Balance':>12}\n"
            history += "-" * 55 + "\n"

            for index, change, after, timestamp, reason in collapsedLedger:
                sign = "+" if change >= 0 else ""

                history += (
                    f"{index:<3} "
                    f"{reason[:25]:<25} "
                    f"{sign}{change:>9,} "
                    f"{after:>12,}\n"
                )
            history = history[:1000]  # Truncate to fit within Discord's embed field limit
            history += "```"
            embed.add_field(
                name="Recent Transactions",     
                value=history[:1024],
                inline=False
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ichilb", description="Displays the current Leaderboard for liquid Ichicoins")
    async def ichilb(self, interaction: discord.Interaction):
        await interaction.response.defer()
        leaderboard = await self.db.fetchall(
            """
            SELECT UserID, Balance
            FROM econ
            ORDER BY Balance DESC
            LIMIT 10
            """
        )

        embed = discord.Embed(
            title="Ichicoins Leaderboard",
            color=discord.Color.gold()
        )

        if not leaderboard:
            embed.add_field(
                name="Leaderboard",
                value="No users found.",
                inline=False
            )
        else:
            lb_text = "```\n"
            lb_text += f"{'Rank':<5} {'User':<25} {'Balance':>12}\n"
            lb_text += "-" * 45 + "\n"

            for rank, (user_id, balance) in enumerate(leaderboard, start=1):
                print(user_id)
                user = await self.bot.fetch_user(user_id)
                print(user)
                if user is not None:
                    username = user.name
                else:
                    username = "Error"
                #username = user.name if user else f"User ID {user_id}"
                lb_text += f"{rank:<5} {username[:25]:<25} {balance:>12,}\n"

            lb_text += "```"

            embed.add_field(
                name="Leaderboard",
                value=lb_text[:1024],
                inline=False
            )

        await interaction.followup.send(embed=embed)

    @app_commands.autocomplete(bank = shared_bank_autocomplete)
    @app_commands.command(name="ichideposit", description="Deposits a select number of Ichicoins to a bank of your choosing")
    async def ichideposit(self, interaction: discord.Interaction, bank: str, amount: int):
        current_time = int(time.time())
        user = interaction.user.id
        #please work i want to make the logging neater
        try:
            result = await self.db.bank_deposit(userID=user, deposit=amount, currenttime=current_time, bank=bank, isRob=0)
        except DatabaseError as e:
            await interaction.response.send_message(str(e))
        if isinstance(result, DatabaseError):
            await interaction.response.send_message(str(result), ephemeral=True)
            return
        else:
            await interaction.response.send_message(f"Successfully deposited {amount} to {bank}.", ephemeral=True)

    @app_commands.autocomplete(bank = shared_bank_autocomplete)
    @app_commands.command(name="ichiwithdraw", description="Withdraws a select number of Ichicoins from a bank of your choosing")
    async def ichiwithdraw(self, interaction: discord.Interaction, bank: str, amount: int):
        amount = -amount
        current_time = int(time.time())
        user = interaction.user.id
        result = await self.db.bank_deposit(userID=user, deposit=amount, currenttime=current_time, bank=bank, isRob=0)
        if isinstance(result, DatabaseError):
            await interaction.response.send_message(str(result), ephemeral=True)
        else:
            await interaction.response.send_message(f"Successfully deposited {amount} to {bank}.", ephemeral=True)

    @app_commands.command(name="ichitransfer", description="Transfers a select number of Ichicoins to a user of your choosing")
    async def ichitransfer(self, interaction: discord.Interaction, user: discord.User, amount: int):
        if amount <= 0:
            await interaction.response.send_message("Transfer amount must be greater than zero.", ephemeral=True)
            return
        current_time = int(time.time())
        current_bal = await self.db.fetchone("SELECT Balance FROM econ WHERE UserID = $1", interaction.user.id)
        current_bal = current_bal[0] if current_bal else 0
        if current_bal < amount:
            await interaction.response.send_message("Insufficient funds for this transfer.", ephemeral=True)
            return
        result = await self.db.change_balance(userID=interaction.user.id, value=-amount, reason=f"Transfer to {user.name}", time=current_time)
        if isinstance(result, DatabaseError):
            await interaction.response.send_message(str(result), ephemeral=True)
        else:
            await self.db.change_balance(userID=user.id, value=amount, reason=f"Transfer from {interaction.user.name}", time=current_time)
            await interaction.response.send_message(f"Successfully transferred {amount} to {user.name}.", ephemeral=True)

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="ichiinject", description="Injects money to an account of your choosing. Admins only.")
    async def ichiinject(self, interaction: discord.Interaction, user: discord.User, amount: int):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        current_time = int(time.time())
        await self.db.change_balance(userID=user.id, value=amount, reason="Admin Injection", time=current_time)
        await interaction.response.send_message(f"Successfully injected {amount} to {user.name}'s account.", ephemeral=True)

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="ichiforceeconomytick", description="Forces an economy tick. Admins only.")
    async def ichiforceeconomytick(self, interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        print("Forcing economy tick...")
        await self.db.write("UPDATE econ SET Wantedness = Wantedness - 1 WHERE Wantedness > 0")
        await self.db.write("UPDATE econ SET Alertness = Alertness - 1 WHERE Alertness > 0")
        await self.db.write("""
            UPDATE bankaccounts
            SET Balance = FLOOR(Balance * (banks.InterestRate))
            FROM banks
            WHERE bankaccounts.BankType = banks.ShortName;
        """)

        print(f"Forced economy tick at {datetime.datetime.fromtimestamp(int(time.time()))}")
        await interaction.response.send_message("Economy tick forced successfully.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Economy(bot))