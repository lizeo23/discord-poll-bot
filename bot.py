import os

# Tu wklej Twój kod b# ---------------------- ODBUDOWA POLLS PO RESECIE ----------------------
async def init_polls_from_channel(channel):
    # Najpierw odbuduj polls na podstawie embedów
    async for message in channel.history(limit=50):
        if message.author == channel.guild.me and message.embeds:
            embed = message.embeds[0]
            # Rozpoznaj czy to embed ankiety po tytule
            if "Mix eafc26" in embed.title:
                # Odtwórz strukturę polls na podstawie embed.description/fields
                hour_votes = {}
                position_votes = {pos: [] for pos in POSITIONS}
                # Godziny z kolumn
                for field in embed.fields[:3]:
                    for line in field.value.split("\n"):
                        if line.strip() and line.strip() != "—" and "`" in line:
                            h = line.split("`",2)[1]
                            users = line.split("`",2)[2].strip()
                            users = users.strip()
                            if users and users != "—":
                                hour_votes[h] = [u.strip() for u in users.split(",")]
                            else:
                                hour_votes[h] = []
                # Pozycje z ostatniego pola
                if len(embed.fields) > 3:
                    for line in embed.fields[3].value.split("\n"):
                        if ":**" in line:
                            pos = line.split("**",2)[1].replace(":","")
                            users = line.split(":**",1)[1].strip()
                            users = users.strip()
                            if users and users != "—":
                                position_votes[pos] = [u.strip() for u in users.split(",")]
                polls[message.id] = {"hour_votes": hour_votes, "position_votes": position_votes}

    # Teraz podpinaj widok do dzisiejszej ankiety
    from datetime import datetime
    dzis = datetime.now()
    dzisiaj_str = dzis.strftime("%Y-%m-%d")
    async for message in channel.history(limit=50):
        if message.author == channel.guild.me and message.embeds:
            embed = message.embeds[0]
            if "Mix eafc26" in embed.title and dzisiaj_str in embed.title:
                poll = polls.get(message.id)
                if poll:
                    hours = list(poll["hour_votes"].keys())
                    view = discord.ui.View(timeout=None)
                    view.add_item(HourSelect(hours, message.id))
                    view.add_item(PositionSelect(POSITIONS, message.id))
                    class ClearVoteButton(discord.ui.Button):
                        def __init__(self, poll_id):
                            super().__init__(label="Wyczyść mój głos", style=discord.ButtonStyle.secondary)
                            self.poll_id = poll_id
                        async def callback(self, interaction: discord.Interaction):
                            user_name = interaction.user.display_name or interaction.user.name
                            poll = polls[self.poll_id]
                            for h in poll["hour_votes"]:
                                if user_name in poll["hour_votes"][h]:
                                    poll["hour_votes"][h].remove(user_name)
                            for p in poll["position_votes"]:
                                if user_name in poll["position_votes"][p]:
                                    poll["position_votes"][p].remove(user_name)
                            await update_poll_message(interaction, poll)
                            try:
                                await interaction.response.send_message("Twój głos został wyczyszczony!", ephemeral=True)
                            except Exception:
                                await interaction.edit_original_response(content="Twój głos został wyczyszczony!")
                    view.add_item(ClearVoteButton(message.id))
                    await message.edit(view=view)
# ---------------------- ZADANIE CODZIENNE ----------------------
from discord.ext import tasks
@tasks.loop(minutes=1)
async def daily_poll_task():
    now = datetime.now()
    if now.hour == 7 and now.minute == 0:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await create_daily_poll(channel)
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta

# ---------------------- KONFIGURACJA ----------------------
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

# Nazwa bota
BOT_NAME = "KillerekBot"

# Lista pozycji piłkarskich
POSITIONS = ["GK", "ŚO", "LP/PP", "ŚP", "ŚPO", "N"]
# -----------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Słownik przechowujący ankiety
# ---------------------- WSPOMAGAJĄCE DO EMBEDA ----------------------

# ---------------------- TESTOWE WYPEŁNIANIE POLLA ----------------------
def chunk(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]

def render_hours_columns(hour_votes):
    hours = list(hour_votes.keys())
    col_size = (len(hours) + 2) // 3
    cols = list(chunk(hours, col_size))
    fields = []
    col_names = ["🕒", "🕘", "🕤"]
    for idx, col in enumerate(cols):
        lines = []
        for h in col:
            users = ", ".join(hour_votes[h]) if hour_votes[h] else "—"
            lines.append(f"`{h}`  {users}")
        fields.append((col_names[idx], "\n".join(lines)))
    while len(fields) < 3:
        fields.append((" ", " "))
    return fields

def build_embed(title, poll):
    import discord
    e = discord.Embed(title=title, color=0x2ecc71)
    e.set_author(name="KillerekBot", icon_url="https://cdn-icons-png.flaticon.com/512/833/833314.png")
    e.description = "**Godziny:**"
    for name, val in render_hours_columns(poll["hour_votes"]):
        e.add_field(name=name, value=val or "—", inline=True)
    pos_lines = []
    for pos, users in poll["position_votes"].items():
        u = ", ".join(users) if users else "—"
        if pos == "GK":
            icon = "🧤"
        elif "ŚO" in pos:
            icon = "🛡️"
        elif "LP/PP" in pos:
            icon = "🛞"
        elif pos == "ŚP":
            icon = "🧭"
        elif "ŚPO" in pos:
            icon = "🧠"
        elif pos == "N":
            icon = "🎯"
        else:
            icon = "🗡️"
        pos_lines.append(f"{icon} **{pos}:** {u}")
    e.add_field(name="\u200b", value="**Pozycje:**\n" + "\n".join(pos_lines), inline=False)
    e.set_footer(text="Kliknij w dropdowny poniżej, aby oddać głos")
    return e
polls = {}

# Generowanie godzin co 30 minut od 15:30 do 22:00
def generate_hours():
    start = datetime.strptime("08:00", "%H:%M")
    mid = datetime.strptime("16:00", "%H:%M")
    end = datetime.strptime("23:00", "%H:%M")
    hours = []
    current = start
    # Od 8:00 do 16:00 co godzinę
    while current < mid:
        hours.append(current.strftime("%H:%M"))
        current += timedelta(hours=1)
    # Od 16:00 do 23:00 co pół godziny
    current = mid
    while current <= end:
        hours.append(current.strftime("%H:%M"))
        current += timedelta(minutes=30)
    return hours

# ---------------------- KLASA DROPDOWN GODZIN ----------------------
class HourSelect(discord.ui.Select):
    def __init__(self, hours, poll_id):
        options = [discord.SelectOption(label=hour) for hour in hours]
        super().__init__(placeholder="Wybierz godzinę", min_values=1, max_values=1, options=options)
        self.poll_id = poll_id


    async def callback(self, interaction: discord.Interaction):
        poll = polls[self.poll_id]
        now = datetime.now().strftime("%H:%M")
        wybrana_godzina = self.values[0]
        if wybrana_godzina < now:
            await interaction.response.send_message(f"Nie możesz zagłosować na godzinę wcześniejszą niż obecna ({now})!", ephemeral=True)
            return
        user_name = interaction.user.display_name or interaction.user.name
        for h in poll["hour_votes"]:
            if user_name in poll["hour_votes"][h]:
                poll["hour_votes"][h].remove(user_name)
        poll["hour_votes"][wybrana_godzina].append(user_name)
        await update_poll_message(interaction, poll)

# ---------------------- KLASA DROPDOWN POZYCJI ----------------------
class PositionSelect(discord.ui.Select):
    def __init__(self, positions, poll_id):
        options = [discord.SelectOption(label=pos) for pos in positions]
        super().__init__(placeholder="Wybierz pozycję", min_values=1, max_values=1, options=options)
        self.poll_id = poll_id

    async def callback(self, interaction: discord.Interaction):
        poll = polls[self.poll_id]
        user_name = interaction.user.display_name or interaction.user.name
        for p in poll["position_votes"]:
            if user_name in poll["position_votes"][p]:
                poll["position_votes"][p].remove(user_name)
        poll["position_votes"][self.values[0]].append(user_name)
        await update_poll_message(interaction, poll)

# ---------------------- AKTUALIZACJA EMBED ----------------------
async def update_poll_message(interaction, poll):
    embed = build_embed(interaction.message.embeds[0].title, poll)
    if interaction.response.is_done():
        await interaction.edit_original_response(embed=embed)
    else:
        await interaction.response.edit_message(embed=embed)

# ---------------------- TWORZENIE ANKIETY ----------------------
async def create_daily_poll(channel):
    # Sprawdź czy ankieta na dzisiaj już istnieje (po tytule embeda)
    async for message in channel.history(limit=50):
        if message.author == channel.guild.me and message.embeds:
            embed = message.embeds[0]
            dni_tygodnia = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]
            dzis = datetime.now()
            dzien_tygodnia = dni_tygodnia[dzis.weekday()]
            dzisiaj_str = dzis.strftime("%Y-%m-%d")
            if dzien_tygodnia in embed.title and dzisiaj_str in embed.title:
                return  # Ankieta na dzisiaj już istnieje

    hours = generate_hours()
    hour_votes = {hour: [] for hour in hours}
    position_votes = {pos: [] for pos in POSITIONS}

    dni_tygodnia = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]
    dzis = datetime.now()
    dzien_tygodnia = dni_tygodnia[dzis.weekday()]
    dzisiaj_str = dzis.strftime("%Y-%m-%d")
    embed = build_embed(f"⚽ {dzien_tygodnia} {dzisiaj_str} - Mix eafc26", {
        "hour_votes": hour_votes,
        "position_votes": position_votes
    })

    view = discord.ui.View(timeout=None)
    poll_message = await channel.send(embed=embed, content="@everyone")

    polls[poll_message.id] = {
        "hour_votes": hour_votes,
        "position_votes": position_votes
    }

    view.add_item(HourSelect(hours, poll_message.id))
    view.add_item(PositionSelect(POSITIONS, poll_message.id))


    class ClearVoteButton(discord.ui.Button):
        def __init__(self, poll_id):
            super().__init__(label="Wyczyść mój głos", style=discord.ButtonStyle.secondary)
            self.poll_id = poll_id
        async def callback(self, interaction: discord.Interaction):
            poll = polls[self.poll_id]
            user_name = interaction.user.display_name or interaction.user.name
            for h in poll["hour_votes"]:
                if user_name in poll["hour_votes"][h]:
                    poll["hour_votes"][h].remove(user_name)
            for p in poll["position_votes"]:
                if user_name in poll["position_votes"][p]:
                    poll["position_votes"][p].remove(user_name)
            await update_poll_message(interaction, poll)
            try:
                await interaction.response.send_message("Twój głos został wyczyszczony!", ephemeral=True)
            except discord.errors.InteractionResponded:
                await interaction.edit_original_response(content="Twój głos został wyczyszczony!")

    view.add_item(ClearVoteButton(poll_message.id))

    await poll_message.edit(view=view)


# ---------------------- START BOTA ----------------------
@bot.event
async def on_ready():
    print(f"{BOT_NAME} jest gotowy! Zalogowano jako {bot.user}")
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await init_polls_from_channel(channel)
    daily_poll_task.start()

bot.run(TOKEN)
ota z pliku discord_bot.py – już jest kompletny
