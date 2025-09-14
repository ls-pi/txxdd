#!/usr/bin/env python3
import os, asyncio, time
from dotenv import load_dotenv
load_dotenv()
import discord
from discord.ext import commands, tasks

from paypay_vpn import connect_vpn, disconnect_vpn, wrapper_get_uuid, load_uuid_from_file, wrapper_check_payment
from umg_api import order_umg_service
from utils import load_products, find_product, create_order, update_order, add_admin_session, is_admin_session, add_profit_record, get_monthly_profit

TOKEN = os.getenv('DISCORD_TOKEN')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD','azxnm0415')
ADMIN_CHANNEL_ID = int(os.getenv('ADMIN_CHANNEL_ID','0') or 0)
REPORT_CHANNEL_ID = int(os.getenv('REPORT_CHANNEL_ID','0') or 0)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='/', intents=intents)

@bot.command(name='admin_auth')
async def admin_auth(ctx, password: str):
    if password == ADMIN_PASSWORD:
        add_admin_session(ctx.author.id, ttl=86400)
        await ctx.reply('✅ 管理者認証に成功しました。', ephemeral=True)
    else:
        await ctx.reply('❌ パスワードが違います。', ephemeral=True)

@bot.command(name='admin_panel')
async def admin_panel(ctx):
    if not is_admin_session(ctx.author.id):
        await ctx.reply('管理者認証が必要です。 /admin_auth <password>', ephemeral=True)
        return
    prods = load_products()
    embed = discord.Embed(title='自販機パネル', description='ボタンからサービスを選択してください')
    view = ProductsView(prods)
    await ctx.send(embed=embed, view=view)
    await ctx.reply('✅ 自販機パネルを作成しました。', ephemeral=True)

@bot.command(name='products')
async def products_cmd(ctx):
    prods = load_products()
    lines = [f"{p['id']}: {p['name']} - {p['price']:.2f}円" for p in prods]
    await ctx.reply('\n'.join(lines))

@tasks.loop(hours=24)
async def daily_report():
    if REPORT_CHANNEL_ID==0:
        return
    ch = bot.get_channel(REPORT_CHANNEL_ID)
    if not ch: return
    now = time.localtime()
    profit = get_monthly_profit(now.tm_year, now.tm_mon)
    await ch.send(f'📊 今月の売上（差額合計）: {profit:.2f} 円')

@bot.event
async def on_ready():
    print('Bot ready', bot.user)
    daily_report.start()

class ProductsView(discord.ui.View):
    def __init__(self, products):
        super().__init__(timeout=None)
        for p in products:
            self.add_item(ProductButton(p['id'], f"{p['name']} - {p['price']:.2f}円"))

class ProductButton(discord.ui.Button):
    def __init__(self, pid, label):
        super().__init__(label=label, style=discord.ButtonStyle.primary, custom_id=pid)
        self.product_id = pid
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(OrderModal(self.product_id))

class OrderModal(discord.ui.Modal):
    def __init__(self, product_id):
        from utils import find_product
        prod = find_product(product_id)
        title = f"{prod['name']} を購入"
        super().__init__(title=title)
        self.product_id = product_id
        self.add_item(discord.ui.TextInput(label='数量', custom_id='quantity', placeholder='例: 1', required=True))
        self.add_item(discord.ui.TextInput(label='PayPay支払いリンク', custom_id='paylink', placeholder='決済リンクを貼ってください', required=True))
        self.add_item(discord.ui.TextInput(label='PayPayパスワード(任意)', custom_id='paypass', placeholder='必要なら入力', required=False))

    async def callback(self, interaction: discord.Interaction):
        qty_raw = self.children[0].value.strip()
        paylink = self.children[1].value.strip()
        try:
            qty = int(qty_raw)
        except:
            await interaction.response.send_message('数量は整数で入力してください', ephemeral=True)
            return
        prod = find_product(self.product_id)
        amount = round(prod['price'] * qty, 2)
        ch = await create_private_channel(interaction.guild, interaction.user, prod['name'], qty)
        await interaction.response.send_message(f'専用チャンネル {ch.mention} を作成しました。', ephemeral=True)
        order = create_order(interaction.user.id, self.product_id, qty, paylink, amount)
        await ch.send(f'🔔 {interaction.user.mention} さんの注文を受け付けました。\nサービス: **{prod['name']}**\n数量: **{qty}**\n金額: **{amount:.2f} 円**\n決済リンクを検証します...')
        bot.loop.create_task(process_order_flow(ch, interaction.user, order, paylink, amount))

async def create_private_channel(guild, user, service_name, quantity):
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    admin_role = os.getenv('ADMIN_ROLE_ID')
    if admin_role:
        try:
            role = guild.get_role(int(admin_role))
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        except:
            pass
    ch = await guild.create_text_channel(f'注文-{user.name}', overwrites=overwrites)
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(label='閉じる', style=discord.ButtonStyle.danger, custom_id=f'close_{ch.id}'))
    await ch.send(f'🛒 {user.mention} の注文チャンネル\nサービス: {service_name}\n数量: {quantity}', view=view)
    bot.loop.create_task(monitor_channel_inactivity(ch, timeout=600))
    return ch

async def monitor_channel_inactivity(channel, timeout=600):
    last = time.time()
    try:
        while True:
            await asyncio.sleep(5)
            if time.time() - last > timeout:
                try:
                    await channel.send('⏰ 10分間操作がなかったためチャンネルを閉じます。')
                except:
                    pass
                try:
                    await channel.delete()
                except:
                    pass
                return
    except Exception:
        return

async def process_order_flow(channel, user, order, paylink, amount):
    await channel.send('💳 決済確認を開始します（VPN経由）...')
    loop = asyncio.get_event_loop()
    try:
        vpn_proc = await loop.run_in_executor(None, connect_vpn)
        uuid = load_uuid_from_file()
        if not uuid:
            uuid, err = wrapper_get_uuid(os.getenv('PAYPAY_PHONE'), os.getenv('PAYPAY_PASSWORD'))
            if not uuid:
                await channel.send(f'❌ UUID取得に失敗しました: {err}')
                await loop.run_in_executor(None, disconnect_vpn, vpn_proc)
                update_order(order['order_id'], status='failed', fail_reason='uuid_failed')
                return
        paid, details = await loop.run_in_executor(None, wrapper_check_payment, uuid, paylink)
        await loop.run_in_executor(None, disconnect_vpn, vpn_proc)
    except Exception as e:
        await channel.send(f'❌ 決済確認中にエラーが発生しました: {e}')
        update_order(order['order_id'], status='failed', fail_reason=str(e))
        return

    if paid:
        pay_amount = 0.0
        if isinstance(details, dict):
            pay_amount = float(details.get('amount', 0.0) or details.get('price', 0.0) or 0.0)
        if pay_amount == 0.0:
            await channel.send('⚠️ 支払い金額を取得できませんでした。注文は保留されます。')
            update_order(order['order_id'], status='failed', fail_reason='no_amount')
            if ADMIN_CHANNEL_ID:
                admin_ch = bot.get_channel(ADMIN_CHANNEL_ID)
                if admin_ch:
                    await admin_ch.send(f'⚠️ 金額情報なし: ユーザー {user.mention} / 商品 {order['product_id']} / 数量 {order['quantity']}')
            return
        if abs(pay_amount - amount) > 0.01:
            await channel.send(f'⚠️ 支払金額が一致しません: 期待 {amount:.2f} 円, 支払 {pay_amount:.2f} 円')
            update_order(order['order_id'], status='failed', fail_reason='amount_mismatch', paid_amount=pay_amount)
            if ADMIN_CHANNEL_ID:
                admin_ch = bot.get_channel(ADMIN_CHANNEL_ID)
                if admin_ch:
                    await admin_ch.send(f'⚠️ 金額不一致: ユーザー {user.mention} / 商品 {order['product_id']} / 数量 {order['quantity']} / 期待 {amount:.2f} / 支払 {pay_amount:.2f}')
            return
        umg_res = order_umg_service(prod['umg_service_id'], order['quantity'])
        umg_price = float(umg_res.get('price',0) if isinstance(umg_res, dict) else 0.0)
        update_order(order['order_id'], status='completed', umg_order=umg_res, umg_price=umg_price)
        add_profit_record(order['order_id'], amount - umg_price)
        await channel.send('✅ 注文が完了しました！24時間以内に増加が開始されます。')
        if ADMIN_CHANNEL_ID:
            admin_ch = bot.get_channel(ADMIN_CHANNEL_ID)
            if admin_ch:
                await admin_ch.send(f'✅ 注文完了: ユーザー {user.mention} / 商品 {order['product_id']} / 数量 {order['quantity']}')
    else:
        update_order(order['order_id'], status='pending')
        await channel.send('⚠️ 決済が確認できませんでした。管理者が手動で確認できます。')
        if ADMIN_CHANNEL_ID:
            admin_ch = bot.get_channel(ADMIN_CHANNEL_ID)
            if admin_ch:
                await admin_ch.send(f'⚠️ 未完了注文: ユーザー {user.mention} / 商品 {order['product_id']} / 数量 {order['quantity']} / リンク: {paylink} / details: {details}')

if __name__ == '__main__':
    bot.run(TOKEN)
