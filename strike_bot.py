import discord
from discord.ext import commands
from discord.ui import Button, View
from discord import app_commands
import json
import os
import asyncio
import re
from datetime import datetime, timedelta

# Setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

STRIKES_FILE = 'strikes.json'
MAX_STRIKES = 3
KG_ROLE_ID = 1472350053296242698
LOG_CHANNEL_ID = 1500853001999483041

# Load strikes from JSON
def load_strikes():
    if os.path.exists(STRIKES_FILE):
        with open(STRIKES_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_strikes(strikes):
    with open(STRIKES_FILE, 'w') as f:
        json.dump(strikes, f, indent=2)

strikes = load_strikes()

# Role nickname shortforms
ROLE_NICKNAME_MAP = {
    1458476438020952205: "[DG]", 1484975826897469490: "[WM]",
    1462458731856924910: "[DC]", 1462459145281208624: "[SC]",
    1460085557953826878: "[WL]", 1462459672819793952: "[MJ]",
    1464762958965117155: "[SO]", 1480538236391526594: "[WO]",
    1480540429333168279: "[BC]", 1480535505232859359: "[FC]",
    1460083436051234890: "[FS]", 1480535648598495232: "[OL]",
    1480536433113436301: "[TO]", 1480536192087887984: "[SL]",
    1480537567077204008: "[SNR]", 1480537496365568082: "[OP]",
    1480537415192940544: "[JO]", 1480537295047229502: "[TR]",
    1480537224675328090: "[CD]", 1480537109239435328: "[RC]",
    1460246158227144724: "[PR]",
}

ROLE_PRIORITY_ORDER = [1458476438020952205, 1484975826897469490, 1462458731856924910, 1462459145281208624, 1460085557953826878, 1462459672819793952, 1464762958965117155, 1480538236391526594, 1480540429333168279, 1480535505232859359, 1460083436051234890, 1480535648598495232, 1480536433113436301, 1480536192087887984, 1480537567077204008, 1480537496365568082, 1480537415192940544, 1480537295047229502, 1480537224675328090, 1480537109239435328, 1460246158227144724]

ROLE_FORMATS_FILE = 'role_formats.json'

def load_role_formats():
    if os.path.exists(ROLE_FORMATS_FILE):
        try:
            with open(ROLE_FORMATS_FILE, 'r') as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except:
            return ROLE_NICKNAME_MAP.copy()
    return ROLE_NICKNAME_MAP.copy()

def save_role_formats(formats):
    to_save = {str(k): v for k, v in formats.items()}
    with open(ROLE_FORMATS_FILE, 'w') as f:
        json.dump(to_save, f, indent=2)

ROLE_NICKNAME_MAP = load_role_formats()

# Helper functions
def parse_duration(duration_str: str):
    if not duration_str or duration_str.lower() == 'permanent':
        return None
    match = re.match(r'(\d+)([dhms])', duration_str.lower())
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2)
    if unit == 'd': return value * 86400
    elif unit == 'h': return value * 3600
    elif unit == 'm': return value * 60
    elif unit == 's': return value
    return None

def format_duration(seconds: int):
    if not seconds: return "Permanent"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0: parts.append(f"{hours}h")
    if minutes > 0: parts.append(f"{minutes}m")
    if secs > 0 and not parts: parts.append(f"{secs}s")
    return " ".join(parts) if parts else "Permanent"

async def update_nickname_with_roles(member: discord.Member):
    highest_role_shortform = None
    for role_id in ROLE_PRIORITY_ORDER:
        if role_id in ROLE_NICKNAME_MAP:
            for role in member.roles:
                if role.id == role_id:
                    highest_role_shortform = ROLE_NICKNAME_MAP[role_id]
                    break
        if highest_role_shortform:
            break
    current_name = member.display_name
    for shortform in ROLE_NICKNAME_MAP.values():
        if current_name.startswith(shortform + " "):
            current_name = current_name[len(shortform) + 1:]
            break
    if highest_role_shortform:
        new_nickname = f"{highest_role_shortform} {current_name}"
        if len(new_nickname) > 32:
            new_nickname = new_nickname[:32]
        if member.nick != new_nickname:
            try:
                await member.edit(nick=new_nickname)
            except:
                pass
    else:
        if member.nick:
            for shortform in ROLE_NICKNAME_MAP.values():
                if member.nick.startswith(shortform + " "):
                    try:
                        await member.edit(nick=None)
                    except:
                        pass
                    break

async def log_strike(user: discord.User, author: discord.User, reason: str, strike_count: int):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if not log_channel:
        return
    if strike_count == 1:
        color = discord.Color.yellow()
        warning = "First strike - Warning"
    elif strike_count == 2:
        color = discord.Color.orange()
        warning = "Second strike - Final warning"
    else:
        color = discord.Color.red()
        warning = "THIRD STRIKE - Action required!"
    log_embed = discord.Embed(title="📝 Strike Logged", description=f"{user.mention} has received a strike.", color=color, timestamp=datetime.now())
    log_embed.add_field(name="User", value=f"{user.name} ({user.id})", inline=True)
    log_embed.add_field(name="Issued By", value=f"{author.name} ({author.id})", inline=True)
    log_embed.add_field(name="Total Strikes", value=f"{strike_count}/{MAX_STRIKES}", inline=True)
    log_embed.add_field(name="Reason", value=reason, inline=False)
    log_embed.add_field(name="Warning Level", value=warning, inline=False)
    if user.avatar:
        log_embed.set_thumbnail(url=user.avatar.url)
    await log_channel.send(embed=log_embed)

# Events
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'{bot.user} is now running!')
    print(f'Slash commands synced!')

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if before.roles != after.roles:
        await update_nickname_with_roles(after)

# Prefix Commands
@bot.command(name='strike')
async def strike(ctx, user: discord.User, *, reason="No reason provided"):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ You need admin permissions.")
        return
    global strikes
    strikes = load_strikes()
    user_id = str(user.id)
    if user_id == str(ctx.author.id):
        await ctx.send("❌ You cannot strike yourself.")
        return
    if user.id == bot.user.id:
        await ctx.send("❌ You cannot strike the bot.")
        return
    if user_id not in strikes:
        strikes[user_id] = {'username': user.name, 'count': 0, 'history': []}
    strikes[user_id]['count'] += 1
    strikes[user_id]['history'].append({'timestamp': datetime.now().isoformat(), 'given_by': ctx.author.name, 'given_by_id': ctx.author.id, 'reason': reason})
    save_strikes(strikes)
    strike_count = strikes[user_id]['count']
    await log_strike(user, ctx.author, reason, strike_count)
    if strike_count == 1:
        color = discord.Color.yellow()
        warning = "⚠️ First strike - Warning"
        main_message = f"{user.mention} has received a strike."
    elif strike_count == 2:
        color = discord.Color.orange()
        warning = "⚠️⚠️ Second strike - Final warning"
        main_message = f"{user.mention} has received a strike."
    else:
        color = discord.Color.red()
        warning = "❌❌❌ THIRD STRIKE - Action required!"
        main_message = f"{user.mention}, you will be executed."
    embed = discord.Embed(title="⚠️ Strike Issued", description=main_message, color=color)
    embed.add_field(name="Total Strikes", value=f"**{strike_count}/{MAX_STRIKES}**", inline=True)
    embed.add_field(name="Issued By", value=ctx.author.mention, inline=True)
    embed.add_field(name="Reason", value=reason, inline=True)
    embed.add_field(name="Warning Level", value=warning, inline=False)
    embed.set_footer(text=f"User ID: {user.id} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if user.avatar:
        embed.set_thumbnail(url=user.avatar.url)
    await ctx.send(embed=embed)
    if strike_count >= MAX_STRIKES:
        try:
            dm_embed = discord.Embed(title="⚠️ Strike Limit Reached", description=f"You have received **{MAX_STRIKES} strikes** in {ctx.guild.name}.", color=discord.Color.red())
            dm_embed.add_field(name="What this means", value="You will be executed.", inline=False)
            dm_embed.add_field(name="Last Strike Reason", value=reason, inline=False)
            await user.send(embed=dm_embed)
        except:
            pass

class StrikeView(View):
    def __init__(self, user: discord.User, strikes_data: dict):
        super().__init__(timeout=60)
        self.user = user
        self.strikes_data = strikes_data
        self.user_id = str(user.id)
        self.message = None
    
    @discord.ui.button(label="Remove 1 Strike", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def remove_strike_button(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need admin permissions.", ephemeral=True)
            return
        if self.user_id not in self.strikes_data or self.strikes_data[self.user_id]['count'] == 0:
            await interaction.response.send_message(f"{self.user.mention} has **no strikes**.", ephemeral=True)
            button.disabled = True
            await interaction.message.edit(view=self)
            return
        self.strikes_data[self.user_id]['count'] -= 1
        if self.strikes_data[self.user_id]['history']:
            self.strikes_data[self.user_id]['history'].pop()
        save_strikes(self.strikes_data)
        new_count = self.strikes_data[self.user_id]['count']
        if new_count >= 3: color = discord.Color.red()
        elif new_count == 2: color = discord.Color.orange()
        elif new_count == 1: color = discord.Color.yellow()
        else: color = discord.Color.green()
        embed = discord.Embed(title=f"{self.user.name}'s Strikes", description=f"**Total Strikes: {new_count}/{MAX_STRIKES}**", color=color)
        if new_count > 0 and self.strikes_data[self.user_id]['history']:
            history_text = ""
            for i, record in enumerate(self.strikes_data[self.user_id]['history'][-5:], 1):
                timestamp = record['timestamp'][:10]
                given_by = record['given_by']
                reason = record.get('reason', 'No reason')
                history_text += f"{i}. {timestamp} (by {given_by}) - {reason}\n"
            embed.add_field(name="Strike History (last 3)", value=history_text, inline=False)
        else:
            embed.add_field(name="Strike History", value="No strikes remaining!", inline=False)
        if new_count == 0:
            button.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"✅ Removed 1 strike from {self.user.mention}. Total: **{new_count}/{MAX_STRIKES}**", ephemeral=True)
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            removal_embed = discord.Embed(title="📝 Strike Removed", description=f"1 strike removed from {self.user.mention}", color=discord.Color.blue(), timestamp=datetime.now())
            removal_embed.add_field(name="User", value=f"{self.user.name} ({self.user.id})", inline=True)
            removal_embed.add_field(name="Removed By", value=interaction.user.mention, inline=True)
            removal_embed.add_field(name="New Total", value=f"{new_count}/{MAX_STRIKES}", inline=True)
            await log_channel.send(embed=removal_embed)
    
    @discord.ui.button(label="Remove ALL Strikes", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def clear_strikes_button(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need admin permissions.", ephemeral=True)
            return
        if self.user_id not in self.strikes_data or self.strikes_data[self.user_id]['count'] == 0:
            await interaction.response.send_message(f"{self.user.mention} has **no strikes**.", ephemeral=True)
            return
        class ConfirmView(View):
            def __init__(self, parent_view):
                super().__init__(timeout=30)
                self.parent_view = parent_view
            @discord.ui.button(label="Yes, Clear All", style=discord.ButtonStyle.danger)
            async def confirm(self, confirm_interaction: discord.Interaction, confirm_button: Button):
                self.parent_view.strikes_data[self.parent_view.user_id]['count'] = 0
                self.parent_view.strikes_data[self.parent_view.user_id]['history'] = []
                save_strikes(self.parent_view.strikes_data)
                embed = discord.Embed(title=f"{self.parent_view.user.name}'s Strikes", description=f"**Total Strikes: 0/{MAX_STRIKES}**", color=discord.Color.green())
                embed.add_field(name="Strike History", value="All strikes cleared!", inline=False)
                for child in self.parent_view.children:
                    child.disabled = True
                await confirm_interaction.response.edit_message(embed=embed, view=self.parent_view)
                await confirm_interaction.followup.send(f"✅ Removed **ALL strikes** from {self.parent_view.user.mention}", ephemeral=True)
                log_channel = bot.get_channel(LOG_CHANNEL_ID)
                if log_channel:
                    clear_embed = discord.Embed(title="📝 All Strikes Cleared", description=f"All strikes cleared for {self.parent_view.user.mention}", color=discord.Color.purple(), timestamp=datetime.now())
                    clear_embed.add_field(name="User", value=f"{self.parent_view.user.name} ({self.parent_view.user.id})", inline=True)
                    clear_embed.add_field(name="Cleared By", value=confirm_interaction.user.mention, inline=True)
                    await log_channel.send(embed=clear_embed)
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, cancel_interaction: discord.Interaction, cancel_button: Button):
                await cancel_interaction.response.edit_message(content="Cancelled.", view=None)
        confirm_view = ConfirmView(self)
        await interaction.response.send_message(f"⚠️ Are you sure you want to remove **ALL** strikes from {self.user.mention}? This cannot be undone.", view=confirm_view, ephemeral=True)
    
    @discord.ui.button(label="Close", style=discord.ButtonStyle.secondary, emoji="🔒")
    async def close_button(self, interaction: discord.Interaction, button: Button):
        await interaction.message.delete()
    
    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            await self.message.edit(view=self)

@bot.command(name='strikemenu')
async def strikemenu(ctx, user: discord.User):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ You need admin permissions to use this menu.")
        return
    user_id = str(user.id)
    strikes_data = load_strikes()
    if user_id not in strikes_data or strikes_data[user_id]['count'] == 0:
        embed = discord.Embed(title=f"{user.name}'s Strikes", description=f"**Total Strikes: 0/{MAX_STRIKES}**", color=discord.Color.green())
        embed.add_field(name="Strike History", value="No strikes recorded.", inline=False)
        view = StrikeView(user, strikes_data)
        for child in view.children:
            if "Remove" in str(child.label):
                child.disabled = True
        view.message = await ctx.send(embed=embed, view=view)
        return
    strike_count = strikes_data[user_id]['count']
    history = strikes_data[user_id]['history']
    if strike_count >= 3: color = discord.Color.red()
    elif strike_count == 2: color = discord.Color.orange()
    else: color = discord.Color.yellow()
    history_text = ""
    for i, record in enumerate(history[-5:], 1):
        timestamp = record['timestamp'][:10]
        given_by = record['given_by']
        reason = record.get('reason', 'No reason')
        history_text += f"{i}. {timestamp} (by {given_by}) - {reason}\n"
    embed = discord.Embed(title=f"{user.name}'s Strikes", description=f"**Total Strikes: {strike_count}/{MAX_STRIKES}**", color=color)
    embed.add_field(name="Strike History (last 3)", value=history_text or "No history", inline=False)
    view = StrikeView(user, strikes_data)
    view.message = await ctx.send(embed=embed, view=view)

@bot.command(name='mystrikes')
async def mystrikes(ctx):
    user_id = str(ctx.author.id)
    strikes_data = load_strikes()
    if user_id not in strikes_data or strikes_data[user_id]['count'] == 0:
        embed = discord.Embed(title="✅ Your Strikes", description=f"You have **0/{MAX_STRIKES} strikes**.", color=discord.Color.green())
        await ctx.send(embed=embed)
        return
    strike_count = strikes_data[user_id]['count']
    history = strikes_data[user_id]['history']
    if strike_count == 1: color = discord.Color.yellow(); status = "⚠️ Warning"
    elif strike_count == 2: color = discord.Color.orange(); status = "⚠️⚠️ Final Warning"
    else: color = discord.Color.red(); status = "❌❌❌ STRIKE LIMIT REACHED"
    history_text = ""
    for i, record in enumerate(history[-5:], 1):
        timestamp = record['timestamp'][:10]
        given_by = record['given_by']
        reason = record.get('reason', 'No reason')
        history_text += f"{i}. {timestamp} (by {given_by}) - {reason}\n"
    embed = discord.Embed(title="⚠️ Your Strikes", description=f"You have **{strike_count}/{MAX_STRIKES} strikes**.", color=color)
    embed.add_field(name="Status", value=status, inline=False)
    embed.add_field(name="Strike History (last 3)", value=history_text or "No history", inline=False)
    if strike_count >= MAX_STRIKES:
        embed.set_footer(text="⚠️ You will be executed. Contact an admin immediately.")
    await ctx.send(embed=embed)

@bot.command(name='sendall')
async def sendall(ctx, *, message):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ You need admin permissions.")
        return
    guild = ctx.guild
    kg_role = guild.get_role(KG_ROLE_ID)
    if not kg_role:
        await ctx.send(f"❌ Role with ID {KG_ROLE_ID} not found.")
        return
    members_with_role = kg_role.members
    sent = 0
    failed = 0
    for member in members_with_role:
        if member.bot:
            continue
        try:
            await member.send(message)
            sent += 1
        except:
            failed += 1
    await ctx.send(f"✅ Sent to **{sent}** members. Failed: **{failed}**")

@bot.command(name='updatenick')
@commands.has_permissions(administrator=True)
async def updatenick(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author
    await update_nickname_with_roles(member)
    await ctx.send(f"✅ Updated nickname for {member.mention}")

@bot.command(name='updateallnicks')
@commands.has_permissions(administrator=True)
async def updateallnicks(ctx):
    await ctx.send("🔄 Updating all members' nicknames...")
    guild = ctx.guild
    updated = 0
    for member in guild.members:
        if member.bot:
            continue
        has_matching_role = any(role.id in ROLE_NICKNAME_MAP for role in member.roles)
        if not has_matching_role:
            continue
        try:
            await update_nickname_with_roles(member)
            updated += 1
        except:
            pass
        await asyncio.sleep(0.3)
    await ctx.send(f"✅ Updated **{updated}** members.")

@bot.command(name='fixmute')
@commands.has_permissions(administrator=True)
async def fix_mute_role(ctx):
    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not muted_role:
        await ctx.send("❌ Muted role not found. Use `/mute` first to create it.")
        return
    await ctx.send("🔄 Fixing Muted role permissions for all channels...")
    count = 0
    for channel in ctx.guild.channels:
        try:
            await channel.set_permissions(muted_role, send_messages=False, add_reactions=False, speak=False, connect=False)
            count += 1
        except:
            pass
        await asyncio.sleep(0.1)
    await ctx.send(f"✅ Fixed permissions for **{count}** channels.")

@bot.command(name='sync')
@commands.has_permissions(administrator=True)
async def sync_commands(ctx):
    await bot.tree.sync()
    await ctx.send("✅ Slash commands synced!")

# Slash Commands
@bot.tree.command(name="ban", description="Ban a user from the server")
@app_commands.checks.has_permissions(ban_members=True)
@app_commands.describe(user="The user to ban", reason="Reason for the ban", duration="How long - 1d, 12h, 30m")
async def slash_ban(interaction: discord.Interaction, user: discord.User, reason: str = "No reason provided", duration: str = None):
    await interaction.response.defer()
    duration_seconds = parse_duration(duration) if duration else None
    duration_text = format_duration(duration_seconds) if duration_seconds else "Permanent"
    embed = discord.Embed(title="🔨 User Banned", color=discord.Color.red(), timestamp=datetime.now())
    embed.add_field(name="User", value=f"{user.mention}\n`{user.name}`", inline=True)
    embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
    embed.add_field(name="Duration", value=duration_text, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    if user.avatar:
        embed.set_thumbnail(url=user.avatar.url)
    try:
        dm_embed = discord.Embed(title=f"🔨 You have been banned from {interaction.guild.name}", color=discord.Color.red())
        dm_embed.add_field(name="Reason", value=reason, inline=False)
        dm_embed.add_field(name="Duration", value=duration_text, inline=False)
        await user.send(embed=dm_embed)
    except:
        pass
    try:
        await interaction.guild.ban(user, reason=f"{reason} (by {interaction.user})")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(embed=discord.Embed(title="❌ Ban Failed", description=str(e), color=discord.Color.red()))

@bot.tree.command(name="unban", description="Unban a user from the server")
@app_commands.checks.has_permissions(ban_members=True)
@app_commands.describe(user_id="The user ID to unban", reason="Reason for the unban")
async def slash_unban(interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
    await interaction.response.defer()
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user, reason=f"{reason} (by {interaction.user})")
        embed = discord.Embed(title="✅ User Unbanned", description=f"{user.mention} has been unbanned.", color=discord.Color.green(), timestamp=datetime.now())
        embed.add_field(name="User", value=f"{user.name} ({user_id})", inline=True)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(embed=discord.Embed(title="❌ Unban Failed", description=str(e), color=discord.Color.red()))

@bot.tree.command(name="kick", description="Kick a user from the server")
@app_commands.checks.has_permissions(kick_members=True)
@app_commands.describe(user="The user to kick", reason="Reason for the kick")
async def slash_kick(interaction: discord.Interaction, user: discord.User, reason: str = "No reason provided"):
    await interaction.response.defer()
    member = interaction.guild.get_member(user.id)
    if not member:
        await interaction.followup.send(embed=discord.Embed(title="❌ Kick Failed", description="User not in server.", color=discord.Color.red()))
        return
    embed = discord.Embed(title="👢 User Kicked", color=discord.Color.orange(), timestamp=datetime.now())
    embed.add_field(name="User", value=f"{user.mention}\n`{user.name}`", inline=True)
    embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    if user.avatar:
        embed.set_thumbnail(url=user.avatar.url)
    try:
        dm_embed = discord.Embed(title=f"👢 You have been kicked from {interaction.guild.name}", color=discord.Color.orange())
        dm_embed.add_field(name="Reason", value=reason, inline=False)
        await user.send(embed=dm_embed)
    except:
        pass
    try:
        await member.kick(reason=f"{reason} (by {interaction.user})")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(embed=discord.Embed(title="❌ Kick Failed", description=str(e), color=discord.Color.red()))

@bot.tree.command(name="mute", description="Mute a user (give them the Muted role)")
@app_commands.checks.has_permissions(manage_roles=True)
@app_commands.describe(user="The user to mute", reason="Reason for the mute", duration="How long - 1d, 12h, 30m, 10m, 60s")
async def slash_mute(interaction: discord.Interaction, user: discord.User, reason: str = "No reason provided", duration: str = "1h"):
    await interaction.response.defer()
    member = interaction.guild.get_member(user.id)
    if not member:
        await interaction.followup.send(embed=discord.Embed(title="❌ Mute Failed", description="User not in server.", color=discord.Color.red()))
        return
    duration_seconds = parse_duration(duration)
    if not duration_seconds:
        await interaction.followup.send(embed=discord.Embed(title="❌ Invalid Duration", description="Use format: 1d, 12h, 30m, 60s", color=discord.Color.red()))
        return
    duration_text = format_duration(duration_seconds)
    muted_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if not muted_role:
        try:
            muted_role = await interaction.guild.create_role(name="Muted")
            for channel in interaction.guild.channels:
                try:
                    await channel.set_permissions(muted_role, send_messages=False, add_reactions=False, speak=False, connect=False)
                except:
                    pass
        except Exception as e:
            await interaction.followup.send(embed=discord.Embed(title="❌ Failed to create Muted role", description=str(e), color=discord.Color.red()))
            return
    bot_member = interaction.guild.get_member(bot.user.id)
    if bot_member and muted_role.position >= bot_member.top_role.position:
        await interaction.followup.send(embed=discord.Embed(title="❌ Bot role too low", description="Move the bot's role above the Muted role.", color=discord.Color.red()))
        return
    embed = discord.Embed(title="🤐 User Muted", color=discord.Color.yellow(), timestamp=datetime.now())
    embed.add_field(name="User", value=f"{user.mention}\n`{user.name}`", inline=True)
    embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
    embed.add_field(name="Duration", value=duration_text, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    if user.avatar:
        embed.set_thumbnail(url=user.avatar.url)
    try:
        dm_embed = discord.Embed(title=f"🤐 You have been muted in {interaction.guild.name}", color=discord.Color.yellow())
        dm_embed.add_field(name="Duration", value=duration_text, inline=False)
        dm_embed.add_field(name="Reason", value=reason, inline=False)
        await user.send(embed=dm_embed)
    except:
        pass
    try:
        await member.add_roles(muted_role, reason=f"Muted: {reason}")
        await interaction.followup.send(embed=embed)
        async def auto_unmute():
            await asyncio.sleep(duration_seconds)
            if muted_role in member.roles:
                await member.remove_roles(muted_role, reason="Mute duration expired")
        asyncio.create_task(auto_unmute())
    except Exception as e:
        await interaction.followup.send(embed=discord.Embed(title="❌ Mute Failed", description=str(e), color=discord.Color.red()))

@bot.tree.command(name="unmute", description="Unmute a user (remove the Muted role)")
@app_commands.checks.has_permissions(manage_roles=True)
@app_commands.describe(user="The user to unmute", reason="Reason for the unmute")
async def slash_unmute(interaction: discord.Interaction, user: discord.User, reason: str = "No reason provided"):
    await interaction.response.defer()
    member = interaction.guild.get_member(user.id)
    if not member:
        await interaction.followup.send(embed=discord.Embed(title="❌ Unmute Failed", description="User not in server.", color=discord.Color.red()))
        return
    muted_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if not muted_role or muted_role not in member.roles:
        await interaction.followup.send(embed=discord.Embed(title="ℹ️ Not Muted", description=f"{user.mention} is not muted.", color=discord.Color.blue()))
        return
    try:
        await member.remove_roles(muted_role, reason=f"Unmuted: {reason}")
        embed = discord.Embed(title="🔊 User Unmuted", color=discord.Color.green(), timestamp=datetime.now())
        embed.add_field(name="User", value=f"{user.mention}\n`{user.name}`", inline=True)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(embed=discord.Embed(title="❌ Unmute Failed", description=str(e), color=discord.Color.red()))

@bot.tree.command(name="timeout", description="Timeout a user (Discord's native timeout)")
@app_commands.checks.has_permissions(moderate_members=True)
@app_commands.describe(user="The user to timeout", reason="Reason for the timeout", duration="How long - 1d, 12h, 30m, 10m, 60s")
async def slash_timeout(interaction: discord.Interaction, user: discord.User, reason: str = "No reason provided", duration: str = "10m"):
    await interaction.response.defer()
    member = interaction.guild.get_member(user.id)
    if not member:
        await interaction.followup.send(embed=discord.Embed(title="❌ Timeout Failed", description="User not in server.", color=discord.Color.red()))
        return
    duration_seconds = parse_duration(duration)
    if not duration_seconds:
        await interaction.followup.send(embed=discord.Embed(title="❌ Invalid Duration", description="Use format: 1d, 12h, 30m, 60s", color=discord.Color.red()))
        return
    if duration_seconds > 2419200:
        duration_seconds = 2419200
    duration_text = format_duration(duration_seconds)
    until = discord.utils.utcnow() + timedelta(seconds=duration_seconds)
    embed = discord.Embed(title="⏰ User Timed Out", color=discord.Color.orange(), timestamp=datetime.now())
    embed.add_field(name="User", value=f"{user.mention}\n`{user.name}`", inline=True)
    embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
    embed.add_field(name="Duration", value=duration_text, inline=True)
    embed.add_field(name="Expires", value=f"<t:{int(until.timestamp())}:R>", inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    if user.avatar:
        embed.set_thumbnail(url=user.avatar.url)
    try:
        dm_embed = discord.Embed(title=f"⏰ You have been timed out in {interaction.guild.name}", color=discord.Color.orange())
        dm_embed.add_field(name="Duration", value=duration_text, inline=False)
        dm_embed.add_field(name="Expires", value=f"<t:{int(until.timestamp())}:R>", inline=False)
        dm_embed.add_field(name="Reason", value=reason, inline=False)
        await user.send(embed=dm_embed)
    except:
        pass
    try:
        await member.timeout(until, reason=f"{reason} (by {interaction.user})")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(embed=discord.Embed(title="❌ Timeout Failed", description=str(e), color=discord.Color.red()))

# Run the bot
bot.run(os.getenv('DISCORD_TOKEN'))
