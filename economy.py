
import discord
import aiosqlite
from discord.ext import commands
import random
from database import Database
from discord.ext import commands, tasks
from discord import app_commands
import time
import math
import datetime
from humanfriendly import format_timespan

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
            SET Gain = Gain + FLOOR(Balance * (banks.InterestRate -1)), Balance = FLOOR(Balance * (banks.InterestRate))
            FROM banks
            WHERE bankaccounts.BankType = banks.ShortName;
        """)
        print(f"Refreshed Wantedness and Alertness at {datetime.datetime.fromtimestamp(current_time)}")

    """class bankinfoview(discord.ui.View):
        def __init__(self, timeout = 600):
            super().__init__(timeout=timeout)
            @discord.ui.button"""


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        self.sets.add(message.author.id)
        print("recieved")

    @app_commands.command(name="ichirob", description="Rob a user of their IchiCoins")
    async def ichirob(self, interaction: discord.Interaction, target: discord.User):
        current_time = time.time()
        user = interaction.user.id
        targetID = target.id
        if user == targetID:
            await interaction.response.send_message("You cannot rob yourself", ephemeral=True)
            return
        row = await self.db.fetchone("SELECT LastStealTime FROM econ WHERE UserID = ?", (user,))
        laststeal = row[0] if row and row[0] is not None else 0
        if current_time - laststeal < 600:
            await interaction.response.send_message("You can chill out on robbing people, y'know?")
            return
        check = await self.db.fetchone("SELECT Balance FROM econ where UserID= ?", (targetID,))
        check1 = await self.db.fetchone("SELECT Wantedness FROM econ where UserID= ?", (user,)) 
        check1 = check1[0] if check1 else 0
        chance = random.randint(1,7)
        if check == None:
            await interaction.response.send_message(content="The User does not have an open account")
            return
        if check1 >=5 or chance > check1:
            await interaction.response.send_message(content="Oopsie! You got caught ^^")
            await self.db.write("UPDATE econ SET Wantedness = Wantedness + 5 WHERE UserID = ?", (current_time,))
            return
        stealbal = check[0]
        if stealbal <= 0:
            await interaction.response.send_message(content="They're broke, sadly", ephemeral=True)
            return
        stealbal = math.floor(stealbal/25 if stealbal/25 < 10000 else 10000)
        reason1 = f"Balance stolen by {user}"
        reason2 = f"Balance stolen from {targetID}"
        await self.db.change_balance(targetID, -stealbal, reason1, current_time)
        await self.db.change_balance(user, stealbal, reason2, current_time)
        await self.db.write("UPDATE econ SET LastStealTime = ?, Wantedness = Wantedness + 3 WHERE UserID = ?", (current_time,user))
        await interaction.response.send_message(content=f"Stole {stealbal} from {target.name}")

    @app_commands.autocomplete(bank = shared_bank_autocomplete)
    @app_commands.command(name="ichiheist", description="Attempt to rob a bank account for Ichicoins")
    async def ichiheist(self, interaction: discord.Interaction, bank: str, user: discord.User):
        print(f"User {interaction.user.id} is attempting to rob {user.id}'s bank account at {bank}")
        if interaction.user.id == user.id:
            await interaction.response.send_message("You cannot heist yourself", ephemeral=True)
            return
        target = await self.db.fetchone("SELECT u.UserID, ba.Balance, u.Alertness, b.SecurityModifier FROM bankaccounts ba INNER JOIN banks b ON ba.BankType = b.ShortName INNER JOIN econ u ON ba.UserID = u.UserID WHERE u.UserID = ? AND b.ShortName = ?", (user.id, bank))
        print(target)
        robber = await self.db.fetchone("SELECT u.Wantedness, u.LuckModifier FROM econ u WHERE u.UserID = ?", (interaction.user.id,))
        print(robber)   
        assetchance = random.randint(1, 10)
        if robber[0] >= 7 or robber[0] >= assetchance :
            await interaction.response.send_message(content=f"FREEZE! THIS IS AN ASSET Seizure!", ephemeral=True) 
            await self.db.write("DELETE FROM bankaccounts WHERE UserID = ?",(interaction.user.id,))
            await self.db.write("UPDATE econ SET balance = FLOOR(balance/2) WHERE UserID = ?",(interaction.user.id,) )
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
        chance = base_chance - (target_defense * 3) - (robber[0] * 4) + (robber[1] * 2)
        chance = max(5, min(45, chance))
        print(chance)
        roll = random.randint(1, 50)
        if roll <= chance:
            robamount = math.floor(target[1] * random.uniform(0.2, 0.3))
            await self.db.write("UPDATE bankaccounts SET Balance = Balance - ?, Loss = Loss + ? WHERE UserID = ? AND BANKTYPE = ?", (robamount,robamount,user.id, bank))
            await self.db.change_balance(interaction.user.id, robamount, f"Bank Heist from {target[0]}", int(time.time()))
            await interaction.response.send_message(content=f"Successfully robbed {robamount} from {user.name}'s bank account at {bank}!")
            await self.db.write("UPDATE econ SET Wantedness = Wantedness + 1 WHERE UserID = ?", (interaction.user.id,))
            await self.db.write("UPDATE econ SET Alertness = Alertness + 1 WHERE UserID = ?", (user.id,))
        else:
            await interaction.response.send_message(content=f"Failed to rob {user.name}'s bank account at {bank}. Better luck next time!", ephemeral=True)  
            await self.db.write("UPDATE econ SET Wantedness = 7 WHERE UserID = ?", (interaction.user.id,))

    @app_commands.command(name="ichiportfolio", description="Show current your current bank and investment portfolio")
    async def ichiportfolio(self, interaction: discord.Interaction):
        await interaction.response.defer()
        current_time = int(time.time())
        user = interaction.user.id
        balance = await self.db.fetchone(
            "SELECT Balance FROM econ WHERE UserID = ?",
            (user,)
        )
        print(balance)

        current_balance = balance[0] if balance else 0
        print(current_balance)
        embed = discord.Embed(
            title=f"{interaction.user.name}'s Balance",
            description=f"**Current Balance:** {current_balance} coins",
            color=discord.Color.gold()
        )
        print(current_balance) 
        banklist = ""
        sum = 0
        print("Starting bank balance retrieval...")
        banks = ["LNC", "MMS", "RDI", "BWS", "UC25"]
        emoji = ["<:LeoNeed:1484485476151722026>","<:MoreMoreJump:1484485534310076556>","<:VividBadSquad:1484485562525286400>","<:WonderlandsShowtime:1484485593470599218>","<:Nightcord:1484485627494924411>"]
        for j in range(len(banks)):
            i = banks[j]
            balance = await self.db.fetchone(
                "SELECT Balance, Gain, LastDepositTime FROM bankaccounts WHERE UserID = ? AND BankType = ?",
                (user, i)
            )
            bankbalance = 0 if balance is None else balance[0]
            gain = 0 if balance is None else balance[1]
            last_deposit_time = 0 if balance is None else balance[2]
            strings = f"{emoji[j]} **{i}** balance: {bankbalance}"
            if gain > 0:
                min_time = await self.db.fetchone("SELECT WithdrawalFee, MinimumDepositTime FROM banks WHERE ShortName = ?", (i,))
                fee, min_time = min_time if min_time else (0,0)
                if current_time - last_deposit_time <= min_time:
                    strings += f"\nGained {gain} withdrawable in {format_timespan(min_time -(current_time - last_deposit_time))}"
                else:
                    strings += f"\nGained {gain} ready to withdraw with a total withdrawal fee of {int(bankbalance*fee)}"
            banklist = banklist + f"\n{strings}"
            sum += bankbalance
        banklist = banklist + f"\nTotal Balance within Banks: {sum}"
        embed.add_field(name="Current Bank Balances",value=banklist)
        wanted = await self.db.fetchone("SELECT Wantedness FROM econ WHERE UserID = ?", (interaction.user.id,))
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
            WHERE Timestamp >= ? AND UserID = ?
            ORDER BY Timestamp DESC
            LIMIT 100
            """,
            (current_time - 86400, user)
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
            history = history[:1000] 
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
        if 0 >= amount:
            await interaction.response.send_message("You can't deposit a negative amount, you know?",ephemeral=True)
            return
        currentwallet = await self.db.fetchone("SELECT Balance FROM econ WHERE UserID = ?", (interaction.user.id,))
        mindeposit = await self.db.fetchone("SELECT MinimumDeposit FROM banks WHERE ShortName = ?", (bank,))
        mindeposit = mindeposit[0] if mindeposit else 0
        currentwallet = currentwallet[0] if currentwallet else 0
        if currentwallet < amount:
            await interaction.response.send_message("You don't have enough Ichicoins to deposit that much.",ephemeral=True)
            return
        if mindeposit > amount:
            await interaction.response.send_message(f"You need atleast {mindeposit} Ichicoins in a single deposit to continue with your transaction to {bank}" ,ephemeral=True)
            return
        current_time = int(time.time())
        user = interaction.user.id
        values = await self.db.fetchone("SELECT * FROM bankaccounts WHERE BankType = ? AND UserID = ?", (bank, interaction.user.id))
        if not values:
            await self.db.write("INSERT INTO bankaccounts (UserID, Balance, BankType, LastDepositTime) VALUES (?,?,?,?)", (interaction.user.id,amount,bank,current_time ))
        else:
            await self.db.write("UPDATE bankaccounts SET Balance = Balance + ?, LastDepositTime = ? WHERE BankType = ? AND UserID = ?", (amount,current_time,bank,interaction.user.id))
        await self.db.change_balance(interaction.user.id, -amount, f"Deposited into {bank}", current_time)
        await interaction.response.send_message(f"Successfully deposited {amount} to you account in {bank}",ephemeral=True)

    @app_commands.autocomplete(bank = shared_bank_autocomplete)
    @app_commands.command(name="ichiwithdraw", description="Withdraws a select number of Ichicoins from a bank of your choosing")
    async def ichiwithdraw(self, interaction: discord.Interaction, bank: str, amount: int):
        current_time = int(time.time())
        user = interaction.user.id
        if 0 >= amount:
            await interaction.response.send_message("You cannot withdraw a negative amount", ephemeral=True)
        bankdata = await self.db.fetchall("SELECT WithdrawalFee, MinimumDepositTime FROM banks WHERE ShortName = ?", (bank,))
        print(bankdata)
        fee, mintime = bankdata[0] if bankdata else (0,0)
        print("Here?")
        checkif = await self.db.fetchone("SELECT Balance, LastDepositTime FROM bankaccounts WHERE UserID = ? AND BankType = ?", (user, bank))
        print(checkif)
        if not checkif:
            await interaction.response.send_message(f"You do not have an account tied to the bank {bank}", ephemeral=True)
            return
        else:
            bankbalance, lastdeposit = checkif[0], checkif[1]
        print("Here?")
        checkif = await self.db.fetchone("SELECT Balance FROM econ WHERE UserID = ?",(user,))
        print(checkif)
        balance = checkif[0] if checkif else 0
        print(balance)
        if amount > bankbalance: 
            await interaction.response.send_message("You dont have enough money in your bank account to withdraw that much", ephemeral= True)
            return
        if int(amount * fee) > balance:
            await interaction.response.send_message(f"You don't have enough money in your account to pay the withdrawal fee of {int(amount*fee)}", ephemeral=True)
            return
        if current_time - lastdeposit < mintime:
            await interaction.response.send_message(f"Please wait {format_timespan(mintime-current_time + lastdeposit)} to withdraw from {bank}", ephemeral=True)
            return
        await self.db.write("UPDATE bankaccounts SET Balance = Balance - ?, LastDepositTime = ? WHERE BankType = ? AND UserID = ?", (amount,current_time,bank,interaction.user.id))
        await self.db.change_balance(interaction.user.id, +amount, f"Withdrew from {bank}", current_time)
        await self.db.change_balance(interaction.user.id, -(int(amount*fee)), f"Paid fee to {bank}", current_time)
        if amount == bankbalance:
            await self.db.write("DELETE FROM bankaccounts WHERE UserID = ? AND BankType = ?",(user,bank))
        await interaction.response.send_message(f"{bank} would like to thank you for choosing them. {amount} Ichcicoins have been withdrawn from your bank accout with a fee of {amount*fee}.")
        
        
        

    """@app_commands.command(name="ichibankinfo", description="Displays your current Ichicoins balance")
    async def ichibankinfo(self, interaction: discord.Interaction):"""
     
    """@app_commands.command(name="ichiwork", description="Work to earn Ichicoins. Join the Ichiworkforce.")
    async def ichiwork(self, interaction: discord.Interaction):"""

    @app_commands.command(name="ichitransfer", description="Transfers a select number of Ichicoins to a user of your choosing")
    async def ichitransfer(self, interaction: discord.Interaction, user: discord.User, amount: int):
        if amount <= 0:
            await interaction.response.send_message("Transfer amount must be greater than zero.", ephemeral=True)
            return
        current_time = int(time.time())
        current_bal = await self.db.fetchone("SELECT Balance FROM econ WHERE UserID = ?", (interaction.user.id,))
        current_bal = current_bal[0] if current_bal else 0
        if current_bal < amount:
            await interaction.response.send_message("Insufficient funds for this transfer.", ephemeral=True)
            return
        result = await self.db.change_balance(userID=interaction.user.id, value=-amount, reason=f"Transfer to {user.name}", time=current_time)
        if isinstance(result, aiosqlite.Error):
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
            SET Gain = Gain + FLOOR(Balance * (banks.InterestRate -1)), Balance = FLOOR(Balance * (banks.InterestRate))
            FROM banks
            WHERE bankaccounts.BankType = banks.ShortName;
        """)

        print(f"Forced economy tick at {datetime.datetime.fromtimestamp(int(time.time()))}")
        await interaction.response.send_message("Economy tick forced successfully.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Economy(bot))