import json
import os
import time
from typing import Dict, List, Optional

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from config import get_json_setting, get_setting, seed_defaults
from database import get_conn, init_db

load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

intents = discord.Intents.default()
intents.guilds = True

ENABLE_PRIVILEGED_INTENTS = os.getenv('ENABLE_PRIVILEGED_INTENTS', 'false').strip().lower() == 'true'
if ENABLE_PRIVILEGED_INTENTS:
    intents.message_content = True
    intents.members = True
    intents.presences = True

bot = commands.Bot(command_prefix='/', intents=intents)

if ENABLE_PRIVILEGED_INTENTS:
    print('Privileged intents enabled via ENABLE_PRIVILEGED_INTENTS=true')
else:
    print('Privileged intents disabled (default)')

STATUS_COLORS = {
    'pending': discord.Color.from_str('#FFC107'),
    'accepted': discord.Color.from_str('#22C55E'),
    'rejected': discord.Color.from_str('#EF4444'),
}


async def log_action(guild: discord.Guild, message: str):
    channel_id = get_setting('logs_channel_id', '')
    if not channel_id:
        return
    channel = guild.get_channel(int(channel_id))
    if channel:
        await channel.send(message)


def get_form_fields(form_type: str):
    with get_conn() as conn:
        return conn.execute(
            'SELECT * FROM form_fields WHERE form_type = ? ORDER BY sort_order, id',
            (form_type,),
        ).fetchall()


def has_pending_application(user_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM applications WHERE user_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    return row is not None


def get_active_cooldown(user_id: int) -> Optional[int]:
    now = int(time.time())
    with get_conn() as conn:
        row = conn.execute(
            'SELECT cooldown_until FROM applications WHERE user_id = ? AND cooldown_until IS NOT NULL ORDER BY id DESC LIMIT 1',
            (user_id,),
        ).fetchone()
    if row and row['cooldown_until'] and row['cooldown_until'] > now:
        return row['cooldown_until']
    return None


async def fetch_member_safe(guild: Optional[discord.Guild], user_id: int) -> Optional[discord.Member]:
    if guild is None:
        return None

    member = guild.get_member(user_id)
    if member is not None:
        return member

    try:
        return await guild.fetch_member(user_id)
    except discord.NotFound:
        return None
    except discord.Forbidden:
        return None
    except discord.HTTPException:
        return None


class DynamicFormModal(discord.ui.Modal):
    def __init__(self, form_type: str, title: str):
        super().__init__(title=title)
        self.form_type = form_type
        self.field_defs = get_form_fields(form_type)[:5]

        for field in self.field_defs:
            self.add_item(
                discord.ui.TextInput(
                    label=field['label'][:45],
                    custom_id=field['field_key'],
                    required=bool(field['required']),
                    max_length=field['max_length'],
                    style=discord.TextStyle.short if field['max_length'] <= 120 else discord.TextStyle.paragraph,
                )
            )

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.bot:
            return

        data = {item.custom_id: item.value for item in self.children if isinstance(item, discord.ui.TextInput)}

        if self.form_type == 'application':
            cooldown_until = get_active_cooldown(interaction.user.id)
            if cooldown_until:
                await interaction.response.send_message(
                    f'Вы на кулдауне до <t:{cooldown_until}:F>.', ephemeral=True
                )
                return
            if has_pending_application(interaction.user.id):
                await interaction.response.send_message('У вас уже есть активная заявка.', ephemeral=True)
                return

            await create_application(interaction, data)
        else:
            await create_report(interaction, data)


class ApplicationActionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _is_allowed(self, interaction: discord.Interaction) -> bool:
        recruiter_role_id = int(get_setting('applications_recruiter_role_id', '0') or 0)
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if not member:
            await interaction.response.send_message('Только участники сервера.', ephemeral=True)
            return False
        has_recruiter = any(r.id == recruiter_role_id for r in member.roles) if recruiter_role_id else False
        if not (has_recruiter or member.guild_permissions.administrator):
            await interaction.response.send_message('Недостаточно прав.', ephemeral=True)
            return False
        return True

    @discord.ui.button(label='✅ Принять', style=discord.ButtonStyle.success, custom_id='app_accept')
    async def accept(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._is_allowed(interaction):
            return
        app_id = int(interaction.message.embeds[0].footer.text.split('|')[1].strip().replace('Application ID: ', ''))
        with get_conn() as conn:
            row = conn.execute('SELECT * FROM applications WHERE id = ?', (app_id,)).fetchone()
            if not row or row['status'] != 'pending':
                await interaction.response.send_message('Заявка уже обработана.', ephemeral=True)
                return
            conn.execute(
                "UPDATE applications SET status='accepted', reviewed_at=?, reviewer_id=? WHERE id=?",
                (int(time.time()), interaction.user.id, app_id),
            )

        embed = interaction.message.embeds[0]
        embed.color = STATUS_COLORS['accepted']
        embed.add_field(name='Статус', value=f'Принял: {interaction.user.mention}', inline=False)
        await interaction.message.edit(embed=embed, view=DisabledView())

        guild = interaction.guild
        if guild:
            newbie_role_id = int(get_setting('applications_newbie_role_id', '0') or 0)
            member = await fetch_member_safe(guild, row['user_id'])
            if member and newbie_role_id:
                role = guild.get_role(newbie_role_id)
                if role:
                    await member.add_roles(role, reason='Заявка одобрена')
            if member:
                await member.send(f'Ваша заявка одобрена! Свяжитесь с рекрутёром {interaction.user.mention}')
            await log_action(guild, f'✅ {interaction.user.mention} одобрил заявку #{app_id}')

        await interaction.response.send_message('Заявка принята.', ephemeral=True)

    @discord.ui.button(label='❌ Отклонить', style=discord.ButtonStyle.danger, custom_id='app_reject')
    async def reject(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._is_allowed(interaction):
            return
        app_id = int(interaction.message.embeds[0].footer.text.split('|')[1].strip().replace('Application ID: ', ''))
        await interaction.response.send_modal(RejectModal(app_id))

    @discord.ui.button(label='📞 Обзвон', style=discord.ButtonStyle.secondary, custom_id='app_call')
    async def call(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._is_allowed(interaction):
            return

        recruiter_role_id = int(get_setting('applications_recruiter_role_id', '0') or 0)
        voice_ids = get_json_setting('applications_call_voice_channel_ids', [])
        mentions = []
        guild = interaction.guild

        if guild and recruiter_role_id:
            allowed_vc = {int(v) for v in voice_ids if str(v).isdigit()}
            seen_member_ids = set()
            for voice_channel_id in allowed_vc:
                channel = guild.get_channel(voice_channel_id)
                if not isinstance(channel, discord.VoiceChannel):
                    continue
                for member in channel.members:
                    if member.id in seen_member_ids:
                        continue
                    seen_member_ids.add(member.id)
                    if any(role.id == recruiter_role_id for role in member.roles):
                        mentions.append(member.mention)

        text = ' '.join(mentions) if mentions else f'<@&{recruiter_role_id}>'
        await interaction.channel.send(f'{text}, нужен обзвон по заявке.')
        await interaction.response.send_message('Обзвон отправлен.', ephemeral=True)


class ReportActionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _is_allowed(self, interaction: discord.Interaction) -> bool:
        role_id = int(get_setting('reports_reviewer_role_id', '0') or 0)
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if not member:
            return False
        return member.guild_permissions.administrator or any(r.id == role_id for r in member.roles)

    @discord.ui.button(label='✅ Принять', style=discord.ButtonStyle.success, custom_id='rep_accept')
    async def accept(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._is_allowed(interaction):
            await interaction.response.send_message('Недостаточно прав.', ephemeral=True)
            return
        report_id = int(interaction.message.embeds[0].footer.text.replace('Report ID: ', ''))
        with get_conn() as conn:
            row = conn.execute('SELECT * FROM promotion_reports WHERE id = ?', (report_id,)).fetchone()
            conn.execute(
                "UPDATE promotion_reports SET status='accepted', reviewed_at=?, reviewer_id=? WHERE id=?",
                (int(time.time()), interaction.user.id, report_id),
            )
        embed = interaction.message.embeds[0]
        embed.color = STATUS_COLORS['accepted']
        embed.add_field(name='Статус', value=f'Принял: {interaction.user.mention}', inline=False)
        await interaction.message.edit(embed=embed, view=DisabledView())
        member = await fetch_member_safe(interaction.guild, row['user_id'])
        if member:
            await member.send('Ваш отчёт на повышение одобрен!')
        await interaction.response.send_message('Отчёт принят.', ephemeral=True)

    @discord.ui.button(label='❌ Отклонить', style=discord.ButtonStyle.danger, custom_id='rep_reject')
    async def reject(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._is_allowed(interaction):
            await interaction.response.send_message('Недостаточно прав.', ephemeral=True)
            return
        report_id = int(interaction.message.embeds[0].footer.text.replace('Report ID: ', ''))
        await interaction.response.send_modal(ReportRejectModal(report_id))


class DisabledView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label='Обработано', style=discord.ButtonStyle.secondary, disabled=True))


class RejectModal(discord.ui.Modal, title='Причина отказа'):
    reason = discord.ui.TextInput(label='Причина отказа', max_length=300, required=True, style=discord.TextStyle.paragraph)

    def __init__(self, app_id: int):
        super().__init__()
        self.app_id = app_id

    async def on_submit(self, interaction: discord.Interaction):
        cooldown_hours = int(get_setting('applications_cooldown_hours', '24') or 24)
        cooldown_until = int(time.time()) + cooldown_hours * 3600 if cooldown_hours > 0 else None
        with get_conn() as conn:
            row = conn.execute('SELECT * FROM applications WHERE id = ?', (self.app_id,)).fetchone()
            conn.execute(
                "UPDATE applications SET status='rejected', reviewed_at=?, reviewer_id=?, reject_reason=?, cooldown_until=? WHERE id=?",
                (int(time.time()), interaction.user.id, self.reason.value, cooldown_until, self.app_id),
            )

        embed = interaction.message.embeds[0]
        embed.color = STATUS_COLORS['rejected']
        embed.add_field(name='Статус', value=f'Отклонил: {interaction.user.mention} | Причина: {self.reason.value}', inline=False)
        await interaction.message.edit(embed=embed, view=DisabledView())

        member = await fetch_member_safe(interaction.guild, row['user_id'])
        if member:
            await member.send(
                f'Ваша заявка отклонена. Причина: {self.reason.value}. Вы можете подать повторную заявку через {cooldown_hours} ч.'
            )
        await interaction.response.send_message('Заявка отклонена.', ephemeral=True)


class ReportRejectModal(discord.ui.Modal, title='Причина отклонения отчёта'):
    reason = discord.ui.TextInput(label='Причина отказа', max_length=300, required=True)

    def __init__(self, report_id: int):
        super().__init__()
        self.report_id = report_id

    async def on_submit(self, interaction: discord.Interaction):
        with get_conn() as conn:
            row = conn.execute('SELECT * FROM promotion_reports WHERE id = ?', (self.report_id,)).fetchone()
            conn.execute(
                "UPDATE promotion_reports SET status='rejected', reviewed_at=?, reviewer_id=?, reject_reason=? WHERE id=?",
                (int(time.time()), interaction.user.id, self.reason.value, self.report_id),
            )
        embed = interaction.message.embeds[0]
        embed.color = STATUS_COLORS['rejected']
        embed.add_field(name='Статус', value=f'Отклонил: {interaction.user.mention} | Причина: {self.reason.value}', inline=False)
        await interaction.message.edit(embed=embed, view=DisabledView())
        member = await fetch_member_safe(interaction.guild, row['user_id'])
        if member:
            await member.send(f'Ваш отчёт на повышение отклонён. Причина: {self.reason.value}')
        await interaction.response.send_message('Отчёт отклонён.', ephemeral=True)


class OpenFormView(discord.ui.View):
    def __init__(self, form_type: str, label: str):
        super().__init__(timeout=None)
        self.form_type = form_type
        self.label = label

    @discord.ui.button(label='Открыть форму', style=discord.ButtonStyle.primary, custom_id='open_form')
    async def open(self, interaction: discord.Interaction, _: discord.ui.Button):
        title = 'Заявка на вступление' if self.form_type == 'application' else 'Отчёт на повышение'
        await interaction.response.send_modal(DynamicFormModal(self.form_type, title))


async def create_application(interaction: discord.Interaction, data: Dict[str, str]):
    recruiter_role_id = int(get_setting('applications_recruiter_role_id', '0') or 0)
    review_channel_id = int(get_setting('applications_review_channel_id', '0') or 0)

    with get_conn() as conn:
        cur = conn.execute(
            'INSERT INTO applications(user_id, submitted_at, data_json) VALUES(?, ?, ?)',
            (interaction.user.id, int(time.time()), json.dumps(data, ensure_ascii=False)),
        )
        app_id = cur.lastrowid

    embed = discord.Embed(
        title=f'Заявка на вступление — {interaction.user.mention}',
        color=STATUS_COLORS['pending'],
    )
    for key, val in data.items():
        embed.add_field(name=key, value=val, inline=False)
    embed.set_footer(text=f'Discord ID: {interaction.user.id} | Application ID: {app_id}')

    review_channel = interaction.guild.get_channel(review_channel_id)
    if review_channel:
        msg = await review_channel.send(
            content=f'<@&{recruiter_role_id}>' if recruiter_role_id else None,
            embed=embed,
            view=ApplicationActionView(),
        )
        with get_conn() as conn:
            conn.execute('UPDATE applications SET message_id = ? WHERE id = ?', (msg.id, app_id))

    await interaction.response.send_message('Ваша заявка принята и передана на рассмотрение.', ephemeral=True)


async def create_report(interaction: discord.Interaction, data: Dict[str, str]):
    review_role_id = int(get_setting('reports_reviewer_role_id', '0') or 0)
    review_channel_id = int(get_setting('reports_review_channel_id', '0') or 0)

    with get_conn() as conn:
        cur = conn.execute(
            'INSERT INTO promotion_reports(user_id, submitted_at, data_json, target_rank) VALUES(?, ?, ?, ?)',
            (interaction.user.id, int(time.time()), json.dumps(data, ensure_ascii=False), data.get('rank_path', '')),
        )
        report_id = cur.lastrowid

    embed = discord.Embed(
        title=f'Отчёт на повышение — {interaction.user.mention}',
        color=STATUS_COLORS['pending'],
    )
    for key, val in data.items():
        embed.add_field(name=key, value=val, inline=False)
    embed.set_footer(text=f'Report ID: {report_id}')

    review_channel = interaction.guild.get_channel(review_channel_id)
    if review_channel:
        await review_channel.send(
            content=f'<@&{review_role_id}>' if review_role_id else None,
            embed=embed,
            view=ReportActionView(),
        )

    await interaction.response.send_message('Ваш отчёт отправлен на рассмотрение.', ephemeral=True)


@bot.event
async def on_ready():
    bot.add_view(ApplicationActionView())
    bot.add_view(ReportActionView())
    bot.add_view(OpenFormView('application', 'Подать заявку'))
    bot.add_view(OpenFormView('report', 'Подать отчёт'))
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} commands')
    except Exception as err:
        print(f'Command sync error: {err}')
    print(f'Bot connected as {bot.user}')


async def admin_only(interaction: discord.Interaction) -> bool:
    member = interaction.user if isinstance(interaction.user, discord.Member) else None
    return bool(member and member.guild_permissions.administrator)


@bot.tree.command(name='setup', description='Публикация embed с кнопками в каналах')
async def setup_cmd(interaction: discord.Interaction):
    if not await admin_only(interaction):
        await interaction.response.send_message('Только админ.', ephemeral=True)
        return

    app_submit_id = int(get_setting('applications_submit_channel_id', '0') or 0)
    report_submit_id = int(get_setting('reports_submit_channel_id', '0') or 0)

    app_channel = interaction.guild.get_channel(app_submit_id)
    report_channel = interaction.guild.get_channel(report_submit_id)

    if app_channel:
        embed = discord.Embed(title='Подача заявки', description='Нажмите кнопку ниже для подачи заявки.')
        await app_channel.send(embed=embed, view=OpenFormView('application', 'Подать заявку'))

    if report_channel:
        embed = discord.Embed(title='Подача отчёта', description='Нажмите кнопку ниже для подачи отчёта.')
        await report_channel.send(embed=embed, view=OpenFormView('report', 'Подать отчёт'))

    await interaction.response.send_message('Setup выполнен.', ephemeral=True)


@bot.tree.command(name='ping', description='Проверка работоспособности')
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message('Pong! Бот работает.')


@app_commands.command(name='заявки_список', description='Список активных заявок')
async def apps_list(interaction: discord.Interaction):
    if not await admin_only(interaction):
        await interaction.response.send_message('Только админ.', ephemeral=True)
        return
    with get_conn() as conn:
        rows = conn.execute("SELECT id, user_id, submitted_at FROM applications WHERE status='pending' ORDER BY id DESC LIMIT 20").fetchall()
    if not rows:
        await interaction.response.send_message('Активных заявок нет.', ephemeral=True)
        return
    text = '\n'.join([f"#{r['id']} user={r['user_id']} submitted=<t:{r['submitted_at']}:R>" for r in rows])
    await interaction.response.send_message(text, ephemeral=True)


@bot.tree.command(name='кулдаун_снять', description='Снять кулдаун пользователю')
@app_commands.describe(user='Пользователь')
async def cooldown_remove(interaction: discord.Interaction, user: discord.Member):
    if not await admin_only(interaction):
        await interaction.response.send_message('Только админ.', ephemeral=True)
        return
    with get_conn() as conn:
        conn.execute('UPDATE applications SET cooldown_until = NULL WHERE user_id = ?', (user.id,))
    await interaction.response.send_message(f'Кулдаун для {user.mention} снят.', ephemeral=True)


bot.tree.add_command(apps_list)


def ensure_default_fields():
    defaults: List[Dict] = [
        {'form_type': 'application', 'field_key': 'nickname', 'label': 'Ник (игровой)', 'field_type': 'text', 'required': 1, 'max_length': 50, 'sort_order': 1},
        {'form_type': 'application', 'field_key': 'static', 'label': 'Статик', 'field_type': 'text', 'required': 1, 'max_length': 20, 'sort_order': 2},
        {'form_type': 'application', 'field_key': 'age', 'label': 'Реальный возраст', 'field_type': 'number', 'required': 1, 'max_length': 2, 'sort_order': 3},
        {'form_type': 'application', 'field_key': 'fraction', 'label': 'Фракция (если есть)', 'field_type': 'text', 'required': 0, 'max_length': 60, 'sort_order': 4},
        {'form_type': 'application', 'field_key': 'about', 'label': 'Как узнал о нас', 'field_type': 'text', 'required': 1, 'max_length': 200, 'sort_order': 5},
        {'form_type': 'report', 'field_key': 'nickname', 'label': 'Ник (игровой)', 'field_type': 'text', 'required': 1, 'max_length': 50, 'sort_order': 1},
        {'form_type': 'report', 'field_key': 'static', 'label': 'Статик', 'field_type': 'text', 'required': 1, 'max_length': 20, 'sort_order': 2},
        {'form_type': 'report', 'field_key': 'rank_path', 'label': 'С какого ранга на какой', 'field_type': 'text', 'required': 1, 'max_length': 60, 'sort_order': 3},
        {'form_type': 'report', 'field_key': 'reason', 'label': 'Причина / заслуги', 'field_type': 'text', 'required': 1, 'max_length': 500, 'sort_order': 4},
    ]
    with get_conn() as conn:
        for item in defaults:
            exists = conn.execute(
                'SELECT id FROM form_fields WHERE form_type = ? AND field_key = ?',
                (item['form_type'], item['field_key']),
            ).fetchone()
            if not exists:
                conn.execute(
                    '''
                    INSERT INTO form_fields(form_type, field_key, label, field_type, required, max_length, sort_order)
                    VALUES(:form_type, :field_key, :label, :field_type, :required, :max_length, :sort_order)
                    ''',
                    item,
                )


if __name__ == '__main__':
    init_db()
    seed_defaults()
    ensure_default_fields()
    if not TOKEN:
        raise RuntimeError('DISCORD_BOT_TOKEN не задан')
    bot.run(TOKEN)
