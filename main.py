# -*- coding: utf-8 -*-
"""Instagram profil boti (bitta fayl, faqat Python standart kutubxonasi).

ISHGA TUSHIRISH: IDLE'da oching -> F5. To'xtatish: Ctrl+C.
Ma'lumotlar shu fayl yonidagi instbot_data.json ga saqlanadi.

MA'LUMOT MANBASI (PROVIDER)
Instagram o'zi ochiq API bermaydi, shuning uchun profil, hikoya va postlar
tashqi ma'lumot xizmati (provayder) orqali olinadi. Quyida PROVIDER_URL va
PROVIDER_KEY ni to'ldirmaguncha bot "ma'lumot manbasi sozlanmagan" deydi.
Kutilayotgan so'rovlar (GET, sarlavha: Authorization: Bearer KEY):
  {PROVIDER_URL}/instagram/profile?username=...      -> {username, full_name, bio, avatar_url,
                                                          followers, following, posts, is_private, has_stories}
  {PROVIDER_URL}/instagram/stories|posts|reels|tagged?username=...
                                                      -> {items:[{url|video_url, caption, taken_at,
                                                                  likes, comments, views, link}]}
  {PROVIDER_URL}/instagram/highlights?username=...   -> {items:[{title, items:[...yuqoridagidek...]}]}
  {PROVIDER_URL}/instagram/media?url=<post havolasi> -> {items:[...yuqoridagidek...]}   (post/Reels yuklash)
Provayder bo'lmasa, ommaviy post/Reels havolalari uchun ixtiyoriy ochiq dastur ishlatiladi:
CMD'da `pip install yt-dlp` (Instagram uni ba'zan to'sadi, kafolat yo'q; hikoyalar bu yo'l bilan olinmaydi).
Tanlagan provayderingiz javob shakli boshqacha bo'lsa, faqat map_profile / map_items
funksiyalarini moslang. Yopiq profillar uchun ma'lumot olinmaydi.
"""
import html
import json
import os
import re
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

# Maxfiy qiymatlar hosting sozlamalaridagi "Environment variables" dan olinadi.
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "8741379218"))   # admin (Premium funksiyalar unga doim ochiq)

PROVIDER_URL = os.getenv("PROVIDER_URL", "")          # masalan: "https://api.provider.com/v1"
PROVIDER_KEY = os.getenv("PROVIDER_KEY", "")

FREE_DAILY_LIMIT = 5
PREMIUM_DAILY_LIMIT = 100
TRACK_INTERVAL = 1800          # kuzatuv tekshiruvi (soniya)
TRACK_MAX = 10
PAGE = 5

# Tariflar: kalit -> (nomi, Telegram Stars narxi, kun). Narx va muddatni o'zgartirishingiz mumkin.
PLANS = {
    "premium": ("👑 Premium", 300, 30),
    "standard": ("🚀 Standartli", 200, 14),
    "minimal": ("🌱 Minimal", 100, 7),
}

API = f"https://api.telegram.org/bot{BOT_TOKEN}/"
try:
    BASE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE = os.getcwd()
BASE = os.getenv("DATA_DIR", BASE)
DB_FILE = os.path.join(BASE, "instbot_data.json")

# ---------------------------------------------------------------- matnlar
T = {
    "uz": {
        "choose_lang": "Assalomu alaykum! Tilni tanlang.\n\nЗдравствуйте! Выберите язык.",
        "start": "Salom!\n\nMen Instagram-dan hikoyalar va postlarni yuklab olishga yordam beraman.\n"
                 "Menga faqat foydalanuvchi nomini yoki Profil havolasini yuboring.\n\n"
                 "Masalan: samoylovaoxana yoki https://www.instagram.com/samoylovaoxana",
        "loading": "⏳ Yuklanmoqda...",
        "bad_input": "❌ Foydalanuvchi nomi yoki profil havolasi noto'g'ri. Masalan: samoylovaoxana",
        "limit": "📛 Bugungi limit tugadi ({used}/{limit}). Limitni oshirish uchun «Tariflar» bo'limiga o'ting.",
        "not_configured": "⚠️ Ma'lumot manbasi hali sozlanmagan. Administratorga murojaat qiling.",
        "not_found": "🔍 Profil topilmadi.",
        "private": "🔒 Bu profil yopiq yoki ma'lumotlarga ruxsat yo'q. Faqat ommaviy ma'lumotlar ko'rsatiladi.",
        "rate_limit": "⏳ So'rovlar cheklovi. Keyinroq qayta urinib ko'ring.",
        "error": "⚠️ Texnik xatolik yuz berdi. Keyinroq qayta urinib ko'ring.",
        "media_fail": "❌ Postni olib bo'lmadi. Havola noto'g'ri, post yopiq yoki o'chirilgan bo'lishi mumkin.",
        "followers": "Obunachilar", "following": "Obunalar", "posts": "Postlar", "stories": "Hikoyalar",
        "choose_action": "@{u} profili uchun amalni tanlang 👇",
        "btn_view": "Profilni ko'rib chiqish", "btn_stories": "Hikoyalar", "btn_posts": "Postlar",
        "btn_highlights": "Dolzarb", "btn_reels": "Reels", "btn_refresh": "Qayta ulanishlar",
        "btn_tagged": "Qayd etilganlar", "btn_track": "Kuzatuv", "btn_analytics": "Tahlillar",
        "locked": "🔒 Bu funksiya Premium tariflar uchun. «Tariflar» bo'limiga qarang.",
        "empty": "Hech narsa topilmadi.",
        "next": "➡️ Keyingisi ({a}/{b})",
        "hl_title": "Dolzarb to'plamlar — @{u}",
        "tariff": "Tarif: <b>{plan}</b>\nHolat: {status}\nTugash sanasi: <b>{until}</b>",
        "free": "Bepul", "active": "🟢 <b>Faol</b>", "inactive": "🔴 <b>Nofaol</b>",
        "plan_btn": "{name} — {stars} ⭐ / {days} kun",
        "plan_desc": "Premium obuna: {days} kun",
        "pay_ok": "✅ To'lov tasdiqlandi. Premium {until} gacha faol.",
        "pay_fail": "❌ To'lovni tasdiqlab bo'lmadi. Administratorga murojaat qiling.",
        "track_title": "👁 Kuzatuv ro'yxati (o'chirish uchun ❌ bosing)",
        "track_empty": "Kuzatuv ro'yxati bo'sh. Profil oynasidagi «Kuzatuv» tugmasi bilan qo'shing (Premium).",
        "track_added": "✅ @{u} kuzatuvga qo'shildi. Yangi post yoki obunachilar o'zgarganda xabar beraman.",
        "track_exists": "@{u} allaqachon kuzatuvda.",
        "track_full": "Kuzatuv limiti ({n}) to'ldi.",
        "track_removed": "@{u} kuzatuvdan olib tashlandi.",
        "track_note": "🔔 @{u}: {what}",
        "new_post": "yangi post chiqdi ({a} → {b})",
        "followers_changed": "obunachilar {a} → {b}",
        "analytics_title": "📊 Tahlillar — @{u}",
        "analytics_empty": "Hali ma'lumot yo'q. Bot kuzatuvlarni vaqt o'tishi bilan yig'adi.",
        "analytics_pick": "Qaysi profil tahlili kerak? Tanlang:",
        "no_history": "Avval biror profilni tekshiring.",
        "settings_title": "⚙️ Moslamalar",
        "btn_lang": "🌐 Tilni almashtirish", "btn_notif_on": "🔔 Bildirishnomalar: yoqilgan",
        "btn_notif_off": "🔕 Bildirishnomalar: o'chirilgan", "btn_clear": "🗑 Tarixni tozalash",
        "btn_delete": "⚠️ Ma'lumotlarimni o'chirish",
        "confirm_delete": "Barcha ma'lumotlaringiz (tarix, kuzatuv, tarif) o'chiriladi. Davom etasizmi?",
        "btn_yes": "Ha, o'chirish", "btn_no": "Bekor qilish",
        "deleted": "Ma'lumotlaringiz o'chirildi. Qayta boshlash uchun /start bosing.",
        "cleared": "Tarix tozalandi.",
        "support_prompt": "Savolingizni yozing, administrator javob beradi.",
        "support_sent": "✅ Xabaringiz yuborildi.",
        "b_tariff": "🗝 Tariflar", "b_track": "👁 Kuzatuv", "b_analytics": "📊 Tahlillar",
        "b_settings": "⚙️ Moslamalar", "b_support": "ℹ️ Qo'llab-quvvatlash",
    },
    "ru": {
        "choose_lang": "Assalomu alaykum! Tilni tanlang.\n\nЗдравствуйте! Выберите язык.",
        "start": "Привет!\n\nЯ помогаю смотреть и скачивать истории и посты из Instagram.\n"
                 "Просто отправьте имя пользователя или ссылку на профиль.\n\n"
                 "Например: samoylovaoxana или https://www.instagram.com/samoylovaoxana",
        "loading": "⏳ Загрузка...",
        "bad_input": "❌ Имя пользователя или ссылка неверны. Например: samoylovaoxana",
        "limit": "📛 Дневной лимит исчерпан ({used}/{limit}). Чтобы увеличить его, откройте «Тарифы».",
        "not_configured": "⚠️ Источник данных ещё не настроен. Обратитесь к администратору.",
        "not_found": "🔍 Профиль не найден.",
        "private": "🔒 Профиль закрыт или доступ к данным ограничен. Показываются только публичные данные.",
        "rate_limit": "⏳ Превышен лимит запросов. Повторите позже.",
        "error": "⚠️ Произошла техническая ошибка. Повторите позже.",
        "media_fail": "❌ Не удалось получить пост. Ссылка неверна, пост закрыт или удалён.",
        "followers": "Подписчики", "following": "Подписки", "posts": "Публикации", "stories": "Истории",
        "choose_action": "Выберите действие для профиля @{u} 👇",
        "btn_view": "Открыть профиль", "btn_stories": "Истории", "btn_posts": "Посты",
        "btn_highlights": "Актуальное", "btn_reels": "Reels", "btn_refresh": "Обновить",
        "btn_tagged": "Отметки", "btn_track": "Слежение", "btn_analytics": "Аналитика",
        "locked": "🔒 Функция доступна в тарифах Premium. Откройте «Тарифы».",
        "empty": "Ничего не найдено.",
        "next": "➡️ Далее ({a}/{b})",
        "hl_title": "Актуальное — @{u}",
        "tariff": "Тариф: <b>{plan}</b>\nСтатус: {status}\nДействует до: <b>{until}</b>",
        "free": "Бесплатный", "active": "🟢 <b>Активен</b>", "inactive": "🔴 <b>Неактивен</b>",
        "plan_btn": "{name} — {stars} ⭐ / {days} дн.",
        "plan_desc": "Подписка Premium: {days} дн.",
        "pay_ok": "✅ Оплата подтверждена. Premium активен до {until}.",
        "pay_fail": "❌ Не удалось подтвердить оплату. Обратитесь к администратору.",
        "track_title": "👁 Список слежения (❌ — удалить)",
        "track_empty": "Список пуст. Добавьте кнопкой «Слежение» в карточке профиля (Premium).",
        "track_added": "✅ @{u} добавлен. Сообщу о новом посте или изменении подписчиков.",
        "track_exists": "@{u} уже в списке.",
        "track_full": "Лимит слежения ({n}) исчерпан.",
        "track_removed": "@{u} убран из списка.",
        "track_note": "🔔 @{u}: {what}",
        "new_post": "новый пост ({a} → {b})",
        "followers_changed": "подписчики {a} → {b}",
        "analytics_title": "📊 Аналитика — @{u}",
        "analytics_empty": "Данных пока нет. Бот копит наблюдения со временем.",
        "analytics_pick": "Для какого профиля нужна аналитика?",
        "no_history": "Сначала проверьте какой-нибудь профиль.",
        "settings_title": "⚙️ Настройки",
        "btn_lang": "🌐 Сменить язык", "btn_notif_on": "🔔 Уведомления: включены",
        "btn_notif_off": "🔕 Уведомления: выключены", "btn_clear": "🗑 Очистить историю",
        "btn_delete": "⚠️ Удалить мои данные",
        "confirm_delete": "Все ваши данные (история, слежение, тариф) будут удалены. Продолжить?",
        "btn_yes": "Да, удалить", "btn_no": "Отмена",
        "deleted": "Данные удалены. Нажмите /start, чтобы начать заново.",
        "cleared": "История очищена.",
        "support_prompt": "Напишите вопрос, администратор ответит.",
        "support_sent": "✅ Сообщение отправлено.",
        "b_tariff": "🗝 Тарифы", "b_track": "👁 Слежение", "b_analytics": "📊 Аналитика",
        "b_settings": "⚙️ Настройки", "b_support": "ℹ️ Поддержка",
    },
}
BTN = {T[lg]["b_" + a]: a for lg in T for a in ("tariff", "track", "analytics", "settings", "support")}

# ---------------------------------------------------------------- baza (JSON)
db = {"users": {}, "history": {}, "tracked": {}, "snapshots": {}, "payments": {}, "errors": [], "searches": 0}
CACHE = {}
PENDING_BC = {}


def load():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, encoding="utf-8") as f:
                db.update(json.load(f))
        except (OSError, ValueError):
            print("Ogohlantirish: baza fayli o'qilmadi, yangisi yaratiladi.")


def save():
    tmp = DB_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False)
    os.replace(tmp, DB_FILE)


def user(uid):
    now = time.time()
    return db["users"].setdefault(str(uid), {
        "lang": None, "notif": True, "banned": False, "premium_until": 0, "plan": None,
        "created": now, "last": now, "state": None, "day": "", "count": 0, "username": None})


def is_premium(uid):
    return uid == OWNER_ID or user(uid)["premium_until"] > time.time()


def tr(uid, key, **kw):
    lang = user(uid)["lang"] or "uz"
    s = T[lang].get(key) or T["uz"][key]
    return s.format(**kw) if kw else s


def log_error(where, msg):
    db["errors"].append({"t": int(time.time()), "w": where[:100], "m": str(msg)[-1500:]})
    del db["errors"][:-100]
    print(f"[xato] {where}: {str(msg)[-300:]}")


h = html.escape


def num(v):
    return "—" if v is None else f"{v:,}".replace(",", " ")


def fmt_date(ts):
    return datetime.fromtimestamp(ts).strftime("%d.%m.%Y")


def fmt_taken(v):
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v).strftime("%d.%m.%Y %H:%M")
    return str(v)[:16].replace("T", " ")


# ---------------------------------------------------------------- Telegram API
def api(method, **params):
    req = urllib.request.Request(API + method, data=json.dumps(params).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        if e.code == 409:
            print("[409] Shu token bilan boshqa nusxa ishlayapti. Eski oynani/dasturni to'xtating.")
        else:
            print(f"[API {method}] HTTP {e.code}: {body[:200]}")
        return {"ok": False, "code": e.code}


def send(chat, text, markup=None, **kw):
    p = {"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if markup:
        p["reply_markup"] = markup
    p.update(kw)
    return api("sendMessage", **p)


def ikb(rows):
    return {"inline_keyboard": rows}


def answer(cq, text=None, alert=False):
    p = {"callback_query_id": cq["id"]}
    if text:
        p.update(text=text, show_alert=alert)
    api("answerCallbackQuery", **p)


def main_kb(uid):
    recent = []
    for x in reversed(db["history"].get(str(uid), [])):
        if x not in recent:
            recent.append(x)
        if len(recent) == 4:
            break
    rows = [[{"text": "@" + x} for x in recent[i:i + 2]] for i in range(0, len(recent), 2)]
    rows += [[{"text": tr(uid, "b_tariff")}],
             [{"text": tr(uid, "b_track")}, {"text": tr(uid, "b_analytics")}],
             [{"text": tr(uid, "b_settings")}, {"text": tr(uid, "b_support")}]]
    return {"keyboard": rows, "resize_keyboard": True}


def lang_kb():
    return ikb([[{"text": "🇺🇿 O'zbek tili", "callback_data": "lang:uz"}],
                [{"text": "🇷🇺 Русский язык", "callback_data": "lang:ru"}]])


# ---------------------------------------------------------------- provayder
class ProviderError(Exception):
    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}")
        self.code = code


def provider_get(kind, value, param="username"):
    if not PROVIDER_URL:
        raise ProviderError("not_configured")
    url = f"{PROVIDER_URL.rstrip('/')}/instagram/{kind}?" + urllib.parse.urlencode({param: value})
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {PROVIDER_KEY}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ProviderError({404: "not_found", 403: "private", 429: "rate_limit"}.get(e.code, "error"), f"HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise ProviderError("error", repr(e))
    if isinstance(data, dict):
        return data.get("data", data)
    return {"items": data} if isinstance(data, list) else {}


def cached(kind, value, refresh=False, ttl=300, param="username"):
    hit = CACHE.get((kind, value))
    if hit and not refresh and time.time() - hit[0] < ttl:
        return hit[1]
    data = provider_get(kind, value, param)
    CACHE[(kind, value)] = (time.time(), data)
    return data


def pick(d, *keys):
    for k in keys:
        if d.get(k) is not None:
            return d[k]
    return None


def to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def map_profile(username, d):
    return {"username": str(pick(d, "username") or username).lower(),
            "full_name": pick(d, "full_name", "name") or "",
            "bio": pick(d, "bio", "biography") or "",
            "avatar": pick(d, "avatar_url", "profile_pic_url_hd", "profile_pic_url"),
            "followers": to_int(pick(d, "followers", "follower_count")),
            "following": to_int(pick(d, "following", "following_count")),
            "posts": to_int(pick(d, "posts", "media_count")),
            "private": bool(pick(d, "is_private", "private")),
            "stories": bool(pick(d, "has_stories", "has_story"))}


def map_items(d):
    raw = d.get("items") if isinstance(d, dict) else d
    out = []
    for it in raw or []:
        if not isinstance(it, dict):
            continue
        video = pick(it, "video_url")
        url = video or pick(it, "url", "image_url", "display_url", "media_url")
        if not url:
            continue
        out.append({"url": url, "video": bool(video) or str(it.get("type", "")).lower() in ("video", "reel"),
                    "caption": pick(it, "caption", "text") or "", "taken": pick(it, "taken_at", "timestamp"),
                    "likes": to_int(pick(it, "likes", "like_count")),
                    "comments": to_int(pick(it, "comments", "comment_count")),
                    "views": to_int(pick(it, "views", "view_count", "play_count")),
                    "link": pick(it, "link", "permalink")})
    return out


def map_highlights(d):
    raw = d.get("items") if isinstance(d, dict) else d
    return [{"title": str(pick(x, "title", "name") or "—"), "items": map_items(x)}
            for x in raw or [] if isinstance(x, dict)]


POST_URL = re.compile(r"(?:https?://)?(?:www\.|m\.)?instagram\.com/(?:[A-Za-z0-9._]+/)?(p|reel|reels|tv)/([A-Za-z0-9_-]+)", re.I)


def ytdlp_media(url):
    """Ixtiyoriy: yt-dlp o'rnatilgan bo'lsa, ommaviy post/Reels uchun to'g'ridan-to'g'ri manzil oladi (login/cookie yo'q)."""
    try:
        import yt_dlp
    except ImportError:
        return None
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as y:
            info = y.extract_info(url, download=False)
    except Exception as e:
        raise ProviderError("not_found", repr(e)[:200])
    items = []
    for e in info.get("entries") or [info]:
        link = e.get("url") or (e.get("formats") or [{}])[-1].get("url")
        if not link:
            continue
        video = e.get("vcodec") not in (None, "none") or str(e.get("ext", "")).lower() in ("mp4", "mov", "webm")
        items.append({"url": link, "video": video, "caption": (e.get("description") or info.get("description") or "")[:200],
                      "taken": e.get("timestamp"), "likes": to_int(e.get("like_count")),
                      "comments": to_int(e.get("comment_count")), "views": to_int(e.get("view_count")), "link": None})
    return items


def fetch_post(url):
    if PROVIDER_URL:
        try:
            return map_items(cached("media", url, param="url"))
        except ProviderError as e:
            if e.code != "error":
                raise
    items = ytdlp_media(url)
    if items is None:
        raise ProviderError("not_configured")
    return items


def handle_post(uid, chat, m):
    if not check_limit(uid, chat):
        return
    kind = "reel" if m.group(1).lower() in ("reel", "reels") else m.group(1).lower()
    url = f"https://www.instagram.com/{kind}/{m.group(2)}/"
    wait = send(chat, tr(uid, "loading"))
    mid = wait.get("result", {}).get("message_id")
    try:
        items = fetch_post(url)
        err = None if items else tr(uid, "media_fail")
    except ProviderError as e:
        err = tr(uid, "media_fail") if e.code == "not_found" else provider_msg(uid, "media", e)
    if err:
        if mid:
            api("editMessageText", chat_id=chat, message_id=mid, text=err)
        else:
            send(chat, err)
        return
    if mid:
        api("deleteMessage", chat_id=chat, message_id=mid)
    user(uid)["count"] += 1
    db["searches"] += 1
    for it in items[:10]:
        send_item(chat, it)


def provider_msg(uid, where, e):
    key = {"not_configured": "not_configured", "not_found": "not_found", "private": "private",
           "rate_limit": "rate_limit"}.get(e.code, "error")
    if key == "error":
        log_error(where, e)
    return tr(uid, key)


# ---------------------------------------------------------------- profil
def snapshot(p):
    s = db["snapshots"].setdefault(p["username"], [])
    rec = {"t": int(time.time()), "f": p["followers"], "g": p["following"], "p": p["posts"]}
    if not s or rec["t"] - s[-1]["t"] > 600 or (s[-1]["f"], s[-1]["g"], s[-1]["p"]) != (rec["f"], rec["g"], rec["p"]):
        s.append(rec)
        del s[:-200]


def action_kb(uid, name):
    lock = "" if is_premium(uid) else "🔒 "
    b = lambda key, cb, locked=False: {"text": (lock if locked else "") + tr(uid, key), "callback_data": cb}
    return ikb([
        [{"text": "🔳 " + tr(uid, "btn_view"), "url": f"https://www.instagram.com/{name}/"}],
        [b("btn_stories", f"ig:st:{name}:0"), b("btn_posts", f"ig:po:{name}:0")],
        [b("btn_highlights", f"ig:hl:{name}", True), b("btn_reels", f"ig:re:{name}:0", True)],
        [b("btn_refresh", f"ig:rf:{name}", True), b("btn_tagged", f"ig:tg:{name}:0", True)],
        [b("btn_track", f"ig:tr:{name}", True), b("btn_analytics", f"ig:an:{name}")],
    ])


def send_card(uid, chat, p):
    bio = p["bio"].strip()
    cap = (f"👤 @{h(p['username'])} | {h(p['full_name'])}\n\n"
           f"• {num(p['followers'])} {tr(uid, 'followers')}\n"
           f"• {num(p['following'])} {tr(uid, 'following')}\n"
           f"• {num(p['posts'])} {tr(uid, 'posts')}\n"
           f"• {tr(uid, 'stories')} {'✅' if p['stories'] else '❌'}")
    if bio:
        cap += f"\n\n<blockquote>{h(bio[:300])}</blockquote>"
    if p["private"]:
        cap += "\n\n" + tr(uid, "private")
    sent = False
    if p["avatar"]:
        r = api("sendPhoto", chat_id=chat, photo=p["avatar"], caption=cap[:1024], parse_mode="HTML",
                reply_markup=main_kb(uid))
        sent = r.get("ok", False)
    if not sent:
        send(chat, cap, main_kb(uid))
    if p["private"]:
        kb = ikb([[{"text": "🔳 " + tr(uid, "btn_view"), "url": f"https://www.instagram.com/{p['username']}/"}]])
    else:
        kb = action_kb(uid, p["username"])
    send(chat, tr(uid, "choose_action", u=h(p["username"])), kb)


def check_limit(uid, chat):
    u = user(uid)
    limit = PREMIUM_DAILY_LIMIT if is_premium(uid) else FREE_DAILY_LIMIT
    today = datetime.now().strftime("%Y-%m-%d")
    if u["day"] != today:
        u["day"], u["count"] = today, 0
    if u["count"] >= limit:
        send(chat, tr(uid, "limit", used=u["count"], limit=limit))
        return False
    return True


def lookup(uid, chat, name, refresh=False):
    u = user(uid)
    if not check_limit(uid, chat):
        return
    wait = send(chat, tr(uid, "loading"))
    mid = wait.get("result", {}).get("message_id")
    try:
        p = map_profile(name, cached("profile", name, refresh, ttl=120))
    except ProviderError as e:
        text = provider_msg(uid, "profile:" + name, e)
        if mid:
            api("editMessageText", chat_id=chat, message_id=mid, text=text)
        else:
            send(chat, text)
        return
    if mid:
        api("deleteMessage", chat_id=chat, message_id=mid)
    u["count"] += 1
    db["searches"] += 1
    hist = db["history"].setdefault(str(uid), [])
    hist.append(p["username"])
    del hist[:-50]
    snapshot(p)
    send_card(uid, chat, p)


def item_caption(it):
    bits = []
    if it["taken"]:
        bits.append("🕒 " + fmt_taken(it["taken"]))
    st = [f"{ic} {num(it[k])}" for ic, k in (("❤️", "likes"), ("💬", "comments"), ("👁", "views")) if it[k] is not None]
    if st:
        bits.append(" · ".join(st))
    if it["caption"]:
        bits.append(h(str(it["caption"])[:200]))
    if it["link"]:
        bits.append(h(str(it["link"])))
    return "\n".join(bits)


def send_item(chat, it):
    cap = item_caption(it)
    method, key = ("sendVideo", "video") if it["video"] else ("sendPhoto", "photo")
    r = api(method, chat_id=chat, **{key: it["url"]}, caption=cap[:1000], parse_mode="HTML")
    if r.get("ok"):
        return
    data = download(it["url"])          # Telegram havolani o'zi ocholmasa, o'zimiz yuklab yuboramiz
    if data:
        r = upload(method, key, "media." + ("mp4" if it["video"] else "jpg"), data,
                   chat_id=chat, caption=cap[:1000], parse_mode="HTML")
        if r.get("ok"):
            return
    send(chat, (cap + "\n" if cap else "") + h(it["url"]))


def download(url, limit=48 * 1024 * 1024):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read(limit + 1)
        return data if len(data) <= limit else None
    except Exception:
        return None


def upload(method, field, filename, data, **fields):
    boundary = "----instbot" + str(int(time.time() * 1000))
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode("utf-8")
             for k, v in fields.items()]
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
                 f'Content-Type: application/octet-stream\r\n\r\n'.encode() + data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(API + method, data=b"".join(parts),
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError):
        return {"ok": False}


def send_items(uid, chat, kind, name, page):
    try:
        items = map_items(cached(kind, name))
    except ProviderError as e:
        send(chat, provider_msg(uid, f"{kind}:{name}", e))
        return
    if not items:
        send(chat, tr(uid, "empty"))
        return
    code = {"stories": "st", "posts": "po", "reels": "re", "tagged": "tg"}[kind]
    chunk = items[page * PAGE:(page + 1) * PAGE]
    for it in chunk:
        send_item(chat, it)
    shown = page * PAGE + len(chunk)
    if shown < len(items):
        send(chat, f"{shown}/{len(items)}", ikb([[{"text": tr(uid, "next", a=shown, b=len(items)),
                                                   "callback_data": f"ig:{code}:{name}:{page + 1}"}]]))


def send_highlights(uid, chat, name):
    try:
        hl = map_highlights(cached("highlights", name))
    except ProviderError as e:
        send(chat, provider_msg(uid, "highlights:" + name, e))
        return
    if not hl:
        send(chat, tr(uid, "empty"))
        return
    btns = [{"text": x["title"][:30], "callback_data": f"ig:hs:{name}:{i}"} for i, x in enumerate(hl[:20])]
    send(chat, tr(uid, "hl_title", u=h(name)), ikb([btns[i:i + 2] for i in range(0, len(btns), 2)]))


def analytics_text(uid, name):
    s = db["snapshots"].get(name, [])
    if not s:
        return tr(uid, "analytics_empty")
    rows = s[-(15 if is_premium(uid) else 3):]
    lines, prev = [], None
    for r in rows:
        d = f" ({r['f'] - prev['f']:+d})" if prev and r["f"] is not None and prev["f"] is not None else ""
        lines.append(f"{datetime.fromtimestamp(r['t']):%d.%m %H:%M} · 👥 {num(r['f'])}{d} · ➕ {num(r['g'])} · 🖼 {num(r['p'])}")
        prev = r
    vals = [r["f"] for r in rows if r["f"] is not None]
    spark = ""
    if len(vals) > 1:
        lo, hi = min(vals), max(vals)
        spark = "\n\n" + "".join("▁▂▃▄▅▆▇█"[0 if hi == lo else int((v - lo) / (hi - lo) * 7)] for v in vals)
    return f"<b>{tr(uid, 'analytics_title', u=h(name))}</b>\n\n" + "\n".join(lines) + spark


def tariff_text(uid):
    u = user(uid)
    if uid == OWNER_ID:
        return tr(uid, "tariff", plan="Admin", status=tr(uid, "active"), until="∞")
    active = is_premium(uid)
    plan = PLANS[u["plan"]][0] if u["plan"] in PLANS else tr(uid, "free")
    until = fmt_date(u["premium_until"]) if u["premium_until"] else "—"
    return tr(uid, "tariff", plan=h(plan if active else tr(uid, "free")),
              status=tr(uid, "active" if active else "inactive"), until=until)


def show_tariffs(uid, chat):
    rows = [[{"text": tr(uid, "plan_btn", name=n, stars=s, days=d), "callback_data": "buy:" + k}]
            for k, (n, s, d) in PLANS.items()]
    send(chat, tariff_text(uid), ikb(rows))


def show_tracked(uid, chat):
    lst = db["tracked"].get(str(uid), [])
    if not lst:
        send(chat, tr(uid, "track_empty"))
        return
    rows = [[{"text": "@" + n, "callback_data": f"ig:op:{n}"}, {"text": "❌", "callback_data": f"trk:{n}"}] for n in lst]
    send(chat, tr(uid, "track_title"), ikb(rows))


def show_analytics_pick(uid, chat):
    recent = []
    for x in reversed(db["history"].get(str(uid), [])):
        if x not in recent:
            recent.append(x)
    if not recent:
        send(chat, tr(uid, "no_history"))
        return
    rows = [[{"text": "@" + n, "callback_data": f"ig:an:{n}"}] for n in recent[:8]]
    send(chat, tr(uid, "analytics_pick"), ikb(rows))


def show_settings(uid, chat):
    on = user(uid)["notif"]
    send(chat, tr(uid, "settings_title"), settings_kb(uid, on))


def settings_kb(uid, on):
    return ikb([[{"text": tr(uid, "btn_lang"), "callback_data": "set:lang"}],
                [{"text": tr(uid, "btn_notif_on" if on else "btn_notif_off"), "callback_data": "set:notif"}],
                [{"text": tr(uid, "btn_clear"), "callback_data": "set:clear"}],
                [{"text": tr(uid, "btn_delete"), "callback_data": "set:del"}]])


# ---------------------------------------------------------------- to'lov
def valid_payment(uid, payload, currency, amount):
    try:
        kind, key, owner = payload.split(":")
        return kind == "plan" and key in PLANS and int(owner) == uid and currency == "XTR" and amount == PLANS[key][1]
    except ValueError:
        return False


def grant(uid, days, plan=None):
    u = user(uid)
    u["premium_until"] = max(time.time(), u["premium_until"]) + days * 86400
    if plan:
        u["plan"] = plan
    return u["premium_until"]


def handle_payment(m):
    uid, chat = m["from"]["id"], m["chat"]["id"]
    sp = m["successful_payment"]
    charge = sp["telegram_payment_charge_id"]
    if charge in db["payments"]:
        send(chat, tr(uid, "pay_ok", until=fmt_date(user(uid)["premium_until"])))
        return
    if not valid_payment(uid, sp["invoice_payload"], sp["currency"], sp["total_amount"]):
        log_error("payment", f"mismatch charge={charge} payload={sp['invoice_payload']}")
        send(chat, tr(uid, "pay_fail"))
        return
    key = sp["invoice_payload"].split(":")[1]
    until = grant(uid, PLANS[key][2], key)
    db["payments"][charge] = {"uid": uid, "plan": key, "amount": sp["total_amount"], "t": int(time.time())}
    send(chat, tr(uid, "pay_ok", until=fmt_date(until)))


# ---------------------------------------------------------------- xabarlar
USERNAME = re.compile(r"^[A-Za-z0-9._]{1,30}$")
IG_URL = re.compile(r"^(?:https?://)?(?:www\.|m\.)?instagram\.com/([A-Za-z0-9._]{1,30})/?(?:\?.*)?$", re.I)
RESERVED = {"p", "reel", "reels", "stories", "explore", "accounts", "tv", "direct", "about", "web"}


def parse_username(text):
    text = text.strip()
    m = IG_URL.match(text)
    if m:
        n = m.group(1).lower()
        return None if n in RESERVED else n
    t = text.lstrip("@")
    return t.lower() if USERNAME.match(t) else None


def show_start(uid, chat):
    send(chat, tr(uid, "start"), main_kb(uid))


def handle_admin(uid, chat, cmd, arg):
    now = time.time()
    users = db["users"]
    if cmd == "/admin":
        st = (f"🛠 <b>Admin</b>\n\nFoydalanuvchilar: {len(users)}\n"
              f"Faol (24 soat): {sum(1 for x in users.values() if now - x['last'] < 86400)}\n"
              f"Premium: {sum(1 for x in users.values() if x['premium_until'] > now)}\n"
              f"Qidiruvlar: {db['searches']}\nTo'lovlar: {len(db['payments'])}\n"
              f"Kuzatuvdagi profillar: {len({n for v in db['tracked'].values() for n in v})}\n"
              f"Xatoliklar: {len(db['errors'])}\n"
              f"Ma'lumot manbasi: {'✅' if PROVIDER_URL else '⚠️ sozlanmagan'}\n\n"
              "/user ID · /grant ID kun · /revoke ID · /ban ID · /unban ID\n"
              "/broadcast matn · /reply ID matn · /errors")
        send(chat, st)
        return
    parts = arg.split(None, 1)
    target = int(parts[0]) if parts and parts[0].isdigit() else None
    if cmd == "/errors":
        e = db["errors"][-8:]
        send(chat, "\n\n".join(f"{datetime.fromtimestamp(x['t']):%d.%m %H:%M} {h(x['w'])}\n<code>{h(x['m'][-250:])}</code>"
                                for x in e) or "Xatolik yo'q ✅")
    elif cmd == "/broadcast":
        if not arg:
            send(chat, "Format: /broadcast matn")
            return
        PENDING_BC[uid] = arg
        n = sum(1 for x in users.values() if not x["banned"])
        send(chat, f"{h(arg)}\n\n— Yuqoridagi matn {n} ta foydalanuvchiga yuboriladi.",
             ikb([[{"text": "✅ Yuborish", "callback_data": "bc:yes"}, {"text": "❌ Bekor", "callback_data": "bc:no"}]]))
    elif target is None:
        send(chat, "Format: " + cmd + " ID ...")
    elif cmd == "/user":
        x = users.get(str(target))
        if not x:
            send(chat, "Topilmadi.")
            return
        send(chat, f"ID: <code>{target}</code> @{h(str(x.get('username') or '-'))}\nTil: {x['lang']}\n"
                   f"Premium: {fmt_date(x['premium_until']) if x['premium_until'] > now else '—'}\n"
                   f"Holat: {'⛔ cheklangan' if x['banned'] else '✅ faol'}\nBugungi qidiruv: {x['count']}")
    elif cmd == "/grant":
        days = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        if not 0 < days <= 3650:
            send(chat, "Format: /grant ID kun (1..3650)")
            return
        until = grant(target, days)
        send(chat, f"✅ Premium {fmt_date(until)} gacha berildi.")
        send(target, tr(target, "pay_ok", until=fmt_date(until)))
    elif cmd == "/revoke":
        user(target)["premium_until"] = 0
        send(chat, "✅ Premium bekor qilindi.")
    elif cmd in ("/ban", "/unban"):
        if target == OWNER_ID:
            send(chat, "Egani cheklab bo'lmaydi.")
            return
        user(target)["banned"] = cmd == "/ban"
        send(chat, "✅ Bajarildi.")
    elif cmd == "/reply" and len(parts) > 1:
        send(target, "💬 " + h(parts[1]))
        send(chat, "✅ Yuborildi.")


def handle_message(m):
    if m["chat"]["type"] != "private":
        return
    uid, chat = m["from"]["id"], m["chat"]["id"]
    u = user(uid)
    u["last"] = time.time()
    u["username"] = m["from"].get("username")
    if u["banned"] and uid != OWNER_ID:
        return
    if "successful_payment" in m:
        handle_payment(m)
        return
    text = (m.get("text") or "").strip()
    if not text:
        return
    cmd = text.split()[0].split("@")[0].lower() if text.startswith("/") else ""
    if cmd in ("/admin", "/user", "/grant", "/revoke", "/ban", "/unban", "/broadcast", "/reply", "/errors"):
        if uid == OWNER_ID:
            handle_admin(uid, chat, cmd, text[len(text.split()[0]):].strip())
        return
    if not u["lang"]:
        send(chat, T["uz"]["choose_lang"], lang_kb())
        return
    if cmd in ("/start", "/help"):
        u["state"] = None
        show_start(uid, chat)
        return
    act = BTN.get(text)
    if act:
        u["state"] = None
        if act == "tariff":
            show_tariffs(uid, chat)
        elif act == "track":
            show_tracked(uid, chat)
        elif act == "analytics":
            show_analytics_pick(uid, chat)
        elif act == "settings":
            show_settings(uid, chat)
        elif act == "support":
            u["state"] = "support"
            send(chat, tr(uid, "support_prompt"))
        return
    if u["state"] == "support":
        u["state"] = None
        who = f"@{u['username']}" if u["username"] else m["from"].get("first_name", "")
        send(OWNER_ID, f"📩 Support\nID: <code>{uid}</code> {h(who)}\n\n{h(text)}\n\n/reply {uid} javob")
        send(chat, tr(uid, "support_sent"))
        return
    pm = POST_URL.search(text)
    if pm:
        handle_post(uid, chat, pm)
        return
    name = parse_username(text)
    if not name:
        send(chat, tr(uid, "bad_input"))
        return
    lookup(uid, chat, name)


def handle_callback(cq):
    uid = cq["from"]["id"]
    chat = cq.get("message", {}).get("chat", {}).get("id", uid)
    u = user(uid)
    if u["banned"] and uid != OWNER_ID:
        answer(cq)
        return
    parts = cq.get("data", "").split(":")
    head = parts[0]
    if head == "lang" and len(parts) > 1 and parts[1] in T:
        u["lang"] = parts[1]
        answer(cq)
        show_start(uid, chat)
        return
    if not u["lang"]:
        answer(cq)
        send(chat, T["uz"]["choose_lang"], lang_kb())
        return
    if head == "ig" and len(parts) > 2 and USERNAME.match(parts[2]):
        code, name = parts[1], parts[2]
        arg = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
        if code in ("hl", "hs", "re", "rf", "tg", "tr") and not is_premium(uid):
            answer(cq, tr(uid, "locked"), True)
            return
        answer(cq)
        if code == "st":
            send_items(uid, chat, "stories", name, arg)
        elif code == "po":
            send_items(uid, chat, "posts", name, arg)
        elif code == "re":
            send_items(uid, chat, "reels", name, arg)
        elif code == "tg":
            send_items(uid, chat, "tagged", name, arg)
        elif code == "hl":
            send_highlights(uid, chat, name)
        elif code == "hs":
            try:
                hl = map_highlights(cached("highlights", name))
                items = hl[arg]["items"][:10] if arg < len(hl) else []
            except ProviderError as e:
                send(chat, provider_msg(uid, "highlights:" + name, e))
                return
            for it in items:
                send_item(chat, it)
            if not items:
                send(chat, tr(uid, "empty"))
        elif code == "rf":
            lookup(uid, chat, name, refresh=True)
        elif code == "op":
            lookup(uid, chat, name)
        elif code == "an":
            send(chat, analytics_text(uid, name))
        elif code == "tr":
            lst = db["tracked"].setdefault(str(uid), [])
            if name in lst:
                send(chat, tr(uid, "track_exists", u=h(name)))
            elif len(lst) >= TRACK_MAX:
                send(chat, tr(uid, "track_full", n=TRACK_MAX))
            else:
                lst.append(name)
                send(chat, tr(uid, "track_added", u=h(name)))
    elif head == "trk" and len(parts) > 1:
        lst = db["tracked"].get(str(uid), [])
        if parts[1] in lst:
            lst.remove(parts[1])
        answer(cq)
        send(chat, tr(uid, "track_removed", u=h(parts[1])))
    elif head == "buy" and len(parts) > 1 and parts[1] in PLANS:
        name, stars, days = PLANS[parts[1]]
        answer(cq)
        api("sendInvoice", chat_id=chat, title=name[:32], description=tr(uid, "plan_desc", days=days),
            payload=f"plan:{parts[1]}:{uid}", provider_token="", currency="XTR",
            prices=[{"label": name[:32], "amount": stars}])
    elif head == "set" and len(parts) > 1:
        what = parts[1]
        answer(cq)
        if what == "lang":
            send(chat, T["uz"]["choose_lang"], lang_kb())
        elif what == "notif":
            u["notif"] = not u["notif"]
            api("editMessageReplyMarkup", chat_id=chat, message_id=cq["message"]["message_id"],
                reply_markup=settings_kb(uid, u["notif"]))
        elif what == "clear":
            db["history"].pop(str(uid), None)
            send(chat, tr(uid, "cleared"), main_kb(uid))
        elif what == "del":
            send(chat, tr(uid, "confirm_delete"), ikb([[{"text": tr(uid, "btn_yes"), "callback_data": "set:delyes"},
                                                        {"text": tr(uid, "btn_no"), "callback_data": "set:no"}]]))
        elif what == "delyes":
            text = tr(uid, "deleted")
            for k in ("users", "history", "tracked"):
                db[k].pop(str(uid), None)
            send(chat, text, {"remove_keyboard": True})
    elif head == "bc" and uid == OWNER_ID:
        answer(cq)
        text = PENDING_BC.pop(uid, None)
        if parts[1] == "yes" and text:
            ok = fail = 0
            for k, x in list(db["users"].items()):
                if x["banned"]:
                    continue
                r = send(int(k), h(text))
                ok, fail = (ok + 1, fail) if r.get("ok") else (ok, fail + 1)
                time.sleep(0.05)
            send(chat, f"📣 Tugadi. Yuborildi: {ok}, xato: {fail}")
    else:
        answer(cq)


def handle_precheckout(q):
    ok = valid_payment(q["from"]["id"], q["invoice_payload"], q["currency"], q["total_amount"])
    p = {"pre_checkout_query_id": q["id"], "ok": ok}
    if not ok:
        p["error_message"] = "Tarif mavjud emas"
    api("answerPreCheckoutQuery", **p)


def handle_update(upd):
    if "message" in upd and "from" in upd["message"]:
        handle_message(upd["message"])
    elif "callback_query" in upd:
        handle_callback(upd["callback_query"])
    elif "pre_checkout_query" in upd:
        handle_precheckout(upd["pre_checkout_query"])


# ---------------------------------------------------------------- kuzatuv
def check_tracked():
    watch = {}
    for uid, names in db["tracked"].items():
        for n in names:
            watch.setdefault(n, []).append(int(uid))
    for name, uids in watch.items():
        try:
            p = map_profile(name, cached("profile", name, refresh=True))
        except ProviderError:
            continue
        s = db["snapshots"].get(name, [])
        old = s[-1] if s else None
        snapshot(p)
        what = None
        if old and None not in (old["p"], p["posts"]) and p["posts"] > old["p"]:
            what = ("new_post", dict(a=old["p"], b=p["posts"]))
        elif old and None not in (old["f"], p["followers"]) and p["followers"] != old["f"]:
            what = ("followers_changed", dict(a=old["f"], b=p["followers"]))
        if what:
            for uid in uids:
                if user(uid)["notif"] and is_premium(uid):
                    send(uid, tr(uid, "track_note", u=h(name), what=tr(uid, what[0], **what[1])))
        time.sleep(1)
    save()


def main():
    try:
        sys.stdout.reconfigure(line_buffering=True)   # hosting loglarida chiqishlar darrov ko'rinsin
    except Exception:
        pass
    if not BOT_TOKEN:
        print("XATO: BOT_TOKEN topilmadi. Hosting sozlamalarida BOT_TOKEN o'zgaruvchisini kiriting.")
        return
    load()
    me = api("getMe")
    if not me.get("ok"):
        print("Token noto'g'ri yoki Telegram'ga ulanib bo'lmadi:", me)
        return
    api("setMyCommands", commands=[{"command": "start", "description": "Boshlash"}])
    print("Bot ishga tushdi: @" + me["result"]["username"])
    if not PROVIDER_URL:
        print("Eslatma: PROVIDER_URL bo'sh, profil ma'lumotlari olinmaydi (menyu va boshqalar ishlaydi).")
    print("Telegram'da botga /start yuboring. To'xtatish: Ctrl+C")
    offset, last_track = 0, time.time()
    while True:
        try:
            res = api("getUpdates", offset=offset, timeout=30,
                      allowed_updates=["message", "callback_query", "pre_checkout_query"])
            for upd in res.get("result", []):
                offset = upd["update_id"] + 1
                try:
                    handle_update(upd)
                except Exception:
                    log_error("update", traceback.format_exc())
                save()
            if not res.get("ok"):
                time.sleep(3)
            if time.time() - last_track > TRACK_INTERVAL:
                last_track = time.time()
                check_tracked()
        except KeyboardInterrupt:
            save()
            print("To'xtatildi.")
            return
        except Exception as e:
            print("Ulanish xatosi:", repr(e), "- 5 soniyadan keyin qayta uriniladi")
            time.sleep(5)


if __name__ == "__main__":
    main()
