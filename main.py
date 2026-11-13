# -*- coding: utf-8 -*-
"""Instagram profil / post boti - HAMMA XIZMAT BEPUL, admin boshqaruv paneli bilan.
Bitta fayl, faqat Python standart kutubxonasi (post yuklash uchun ixtiyoriy: pip install yt-dlp).

ISHGA TUSHIRISH: IDLE'da oching -> F5. To'xtatish: Ctrl+C.
Ma'lumotlar shu fayl yonidagi instbot_data.json ga saqlanadi.

ADMIN: ADMIN_IDS dagi foydalanuvchi /admin yozadi yoki pastdagi
"📊 Bot statistikasi" / "⚙️ Tizim sozlamalari" tugmalarini bosadi.

MA'LUMOT MANBASI (PROVIDER). Instagram ochiq API bermaydi, profil/hikoya/postlar tashqi
ma'lumot xizmati orqali olinadi. PROVIDER_URL va PROVIDER_KEY ni to'ldirmaguncha profil
ma'lumotlari chiqmaydi (menyu, admin panel, post havolasidan video yuklash ishlaydi).
Kutilayotgan so'rovlar (GET, Authorization: Bearer KEY):
  {PROVIDER_URL}/instagram/profile?username=...   -> {username, full_name, bio, avatar_url,
                                                       followers, following, posts, is_private, has_stories}
  {PROVIDER_URL}/instagram/stories|posts|reels|tagged?username=...  -> {items:[{url|video_url, caption,
                                                       taken_at, likes, comments, views, link}]}
  {PROVIDER_URL}/instagram/highlights?username=... -> {items:[{title, items:[...]}]}
  {PROVIDER_URL}/instagram/media?url=<post havolasi> -> {items:[...]}
Javob shakli boshqacha bo'lsa, map_profile / map_items funksiyalarini moslang.
Yopiq profillar uchun ma'lumot olinmaydi.
"""
import html
import importlib.util
import json
import os
import re
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

# Maxfiy qiymatlar hosting sozlamalaridagi "Environment variables" dan olinadi.
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "8741379218"))
ADMIN_IDS = {OWNER_ID}          # boshqa adminlar ID'sini shu yerga qo'shing: {OWNER_ID, 123456789}

PROVIDER_URL = os.getenv("PROVIDER_URL", "")   # Eski provayder sozlamasi (Apify ishlatilganda kerak emas).
PROVIDER_KEY = os.getenv("PROVIDER_KEY", "")
APIFY_TOKEN = os.getenv("APIFY_TOKEN", "").strip() or PROVIDER_KEY
APIFY_ACTOR = os.getenv("APIFY_ACTOR", "apify/instagram-scraper").strip()
# Instagram bloklangan bo'lsa: VPN'ni butun kompyuter uchun yoqing yoki VPN proksisini yozing,
# masalan "socks5://127.0.0.1:10808" (faqat yt-dlp uchun).
PROXY = os.getenv("PROXY", "")

TRACK_INTERVAL = 1800          # kuzatuv tekshiruvi (soniya)
TRACK_MAX = 10
PAGE = 5

API = f"https://api.telegram.org/bot{BOT_TOKEN}/"
try:
    BASE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE = os.getcwd()
BASE = os.getenv("DATA_DIR", BASE)
DB_FILE = os.path.join(BASE, "instbot_data.json")


def is_admin(uid):
    return uid in ADMIN_IDS


# ---------------------------------------------------------------- matnlar
T = {
    "uz": {
        "choose_lang": "Assalomu alaykum! Tilni tanlang.\n\nЗдравствуйте! Выберите язык.",
        "start": "Salom!\n\nMen Instagram-dan hikoyalar va postlarni yuklab olishga yordam beraman.\n"
                 "Menga faqat foydalanuvchi nomini yoki Profil havolasini yuboring.\n\n"
                 "Masalan: samoylovaoxana yoki https://www.instagram.com/samoylovaoxana",
        "loading": "⏳ Yuklanmoqda...",
        "bad_input": "❌ Foydalanuvchi nomi yoki profil havolasi noto'g'ri. Masalan: samoylovaoxana",
        "limit": "📛 Bugungi limit tugadi ({used}/{limit}). Ertaga qayta urinib ko'ring.",
        "maintenance": "🛠 Bot vaqtincha to'xtatilgan (texnik ishlar). Keyinroq qayta urinib ko'ring.",
        "not_configured": "⚠️ Ma'lumot manbasi hali sozlanmagan. Administratorga murojaat qiling.",
        "not_found": "🔍 Profil topilmadi.",
        "private": "🔒 Bu profil yopiq yoki ma'lumotlarga ruxsat yo'q. Faqat ommaviy ma'lumotlar ko'rsatiladi.",
        "rate_limit": "⏳ So'rovlar cheklovi. Keyinroq qayta urinib ko'ring.",
        "error": "⚠️ Texnik xatolik yuz berdi. Keyinroq qayta urinib ko'ring.",
        "media_fail": "❌ Postni olib bo'lmadi. Havola noto'g'ri, post yopiq yoki o'chirilgan bo'lishi mumkin.",
        "network": "🌐 Instagram'ga ulanib bo'lmadi. Server tarmog'ida Instagram bloklangan bo'lishi mumkin, VPN'ni tekshiring.",
        "followers": "Obunachilar", "following": "Obunalar", "posts": "Postlar", "stories": "Hikoyalar",
        "choose_action": "@{u} profili uchun amalni tanlang 👇",
        "btn_view": "Profilni ko'rib chiqish", "btn_stories": "Hikoyalar", "btn_posts": "Postlar",
        "btn_highlights": "Dolzarb", "btn_reels": "Reels", "btn_refresh": "Qayta ulanishlar",
        "btn_tagged": "Qayd etilganlar", "btn_track": "Kuzatuv", "btn_analytics": "Tahlillar",
        "empty": "Hech narsa topilmadi.",
        "next": "➡️ Keyingisi ({a}/{b})",
        "hl_title": "Dolzarb to'plamlar — @{u}",
        "track_title": "👁 Kuzatuv ro'yxati (o'chirish uchun ❌ bosing)",
        "track_empty": "Kuzatuv ro'yxati bo'sh. Profil oynasidagi «Kuzatuv» tugmasi bilan qo'shing.",
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
        "confirm_delete": "Barcha ma'lumotlaringiz (tarix, kuzatuv) o'chiriladi. Davom etasizmi?",
        "btn_yes": "Ha, o'chirish", "btn_no": "Bekor qilish",
        "deleted": "Ma'lumotlaringiz o'chirildi. Qayta boshlash uchun /start bosing.",
        "cleared": "Tarix tozalandi.",
        "support_prompt": "Savolingizni yozing, administrator javob beradi.",
        "support_sent": "✅ Xabaringiz yuborildi.",
        "b_track": "👁 Kuzatuv", "b_analytics": "📊 Tahlillar",
        "b_settings": "⚙️ Moslamalar", "b_support": "ℹ️ Qo'llab-quvvatlash",
        "b_admin_stats": "📊 Bot statistikasi", "b_admin_settings": "⚙️ Tizim sozlamalari",
    },
    "ru": {
        "choose_lang": "Assalomu alaykum! Tilni tanlang.\n\nЗдравствуйте! Выберите язык.",
        "start": "Привет!\n\nЯ помогаю смотреть и скачивать истории и посты из Instagram.\n"
                 "Просто отправьте имя пользователя или ссылку на профиль.\n\n"
                 "Например: samoylovaoxana или https://www.instagram.com/samoylovaoxana",
        "loading": "⏳ Загрузка...",
        "bad_input": "❌ Имя пользователя или ссылка неверны. Например: samoylovaoxana",
        "limit": "📛 Дневной лимит исчерпан ({used}/{limit}). Попробуйте завтра.",
        "maintenance": "🛠 Бот временно остановлен (технические работы). Повторите позже.",
        "not_configured": "⚠️ Источник данных ещё не настроен. Обратитесь к администратору.",
        "not_found": "🔍 Профиль не найден.",
        "private": "🔒 Профиль закрыт или доступ к данным ограничен. Показываются только публичные данные.",
        "rate_limit": "⏳ Превышен лимит запросов. Повторите позже.",
        "error": "⚠️ Произошла техническая ошибка. Повторите позже.",
        "media_fail": "❌ Не удалось получить пост. Ссылка неверна, пост закрыт или удалён.",
        "network": "🌐 Не удалось подключиться к Instagram. Возможно, он заблокирован в сети сервера, проверьте VPN.",
        "followers": "Подписчики", "following": "Подписки", "posts": "Публикации", "stories": "Истории",
        "choose_action": "Выберите действие для профиля @{u} 👇",
        "btn_view": "Открыть профиль", "btn_stories": "Истории", "btn_posts": "Посты",
        "btn_highlights": "Актуальное", "btn_reels": "Reels", "btn_refresh": "Обновить",
        "btn_tagged": "Отметки", "btn_track": "Слежение", "btn_analytics": "Аналитика",
        "empty": "Ничего не найдено.",
        "next": "➡️ Далее ({a}/{b})",
        "hl_title": "Актуальное — @{u}",
        "track_title": "👁 Список слежения (❌ — удалить)",
        "track_empty": "Список пуст. Добавьте кнопкой «Слежение» в карточке профиля.",
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
        "confirm_delete": "Все ваши данные (история, слежение) будут удалены. Продолжить?",
        "btn_yes": "Да, удалить", "btn_no": "Отмена",
        "deleted": "Данные удалены. Нажмите /start, чтобы начать заново.",
        "cleared": "История очищена.",
        "support_prompt": "Напишите вопрос, администратор ответит.",
        "support_sent": "✅ Сообщение отправлено.",
        "b_track": "👁 Слежение", "b_analytics": "📊 Аналитика",
        "b_settings": "⚙️ Настройки", "b_support": "ℹ️ Поддержка",
        "b_admin_stats": "📊 Статистика бота", "b_admin_settings": "⚙️ Системные настройки",
    },
}

# Admin tahrirlay oladigan matnlar va tugmalar: (kalit, admin uchun nomi)
EDIT_TEXTS = [("start", "Start xabari"), ("bad_input", "Noto'g'ri havola"), ("not_found", "Profil topilmadi"),
              ("private", "Yopiq profil"), ("rate_limit", "API cheklovi"), ("error", "Texnik xatolik"),
              ("not_configured", "Manba sozlanmagan"), ("media_fail", "Post olinmadi"),
              ("network", "Ulanish xatosi"), ("empty", "Hech narsa topilmadi"), ("choose_action", "Amal tanlash"),
              ("support_prompt", "Yordam so'rovi"), ("maintenance", "Texnik ishlar"), ("limit", "Limit tugadi")]
EDIT_BTNS = [("b_track", "Kuzatuv (pastki)"), ("b_analytics", "Tahlillar (pastki)"),
             ("b_settings", "Moslamalar (pastki)"), ("b_support", "Qo'llab-quvvatlash (pastki)"),
             ("btn_view", "Profilni ko'rib chiqish"), ("btn_stories", "Hikoyalar"), ("btn_posts", "Postlar"),
             ("btn_highlights", "Dolzarb"), ("btn_reels", "Reels"), ("btn_refresh", "Qayta ulanishlar"),
             ("btn_tagged", "Qayd etilganlar"), ("btn_track", "Kuzatuv (profil)"),
             ("btn_analytics", "Tahlillar (profil)")]
NAMES = dict(EDIT_TEXTS + EDIT_BTNS)
BTN_KEYS = {k for k, _ in EDIT_BTNS}
HINTS = {"choose_action": "{u} — profil nomi o'rniga qo'yiladi.", "limit": "{used} va {limit} — sarflangan va umumiy limit."}

# ---------------------------------------------------------------- baza (JSON)
DEFAULT_CFG = {"enabled": True, "recent": True, "daily_limit": 0}
db = {"users": {}, "history": {}, "tracked": {}, "snapshots": {}, "errors": [], "searches": 0, "downloads": 0,
      "texts": {"uz": {}, "ru": {}}, "buttons_off": [], "cfg": dict(DEFAULT_CFG)}
CACHE = {}
PENDING_BC = {}


def load():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, encoding="utf-8") as f:
                db.update(json.load(f))
        except (OSError, ValueError):
            print("Ogohlantirish: baza fayli o'qilmadi, yangisi yaratiladi.")
    db["cfg"] = {**DEFAULT_CFG, **db.get("cfg", {})}
    for lg in T:
        db["texts"].setdefault(lg, {})


def save():
    tmp = DB_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False)
    os.replace(tmp, DB_FILE)


def user(uid):
    now = time.time()
    return db["users"].setdefault(str(uid), {
        "lang": None, "notif": True, "banned": False, "created": now, "last": now,
        "state": None, "day": "", "count": 0, "username": None})


def text_for(lang, key):
    return db["texts"].get(lang, {}).get(key) or T[lang].get(key) or T["uz"].get(key, key)


def tr(uid, key, **kw):
    s = text_for(user(uid)["lang"] or "uz", key)
    if kw:
        try:
            return s.format(**kw)
        except (KeyError, IndexError, ValueError):
            return s
    return s


def log_error(where, msg):
    db["errors"].append({"t": int(time.time()), "w": where[:100], "m": str(msg)[-1500:]})
    del db["errors"][:-100]
    print(f"[xato] {where}: {str(msg)[-300:]}")


h = html.escape


def num(v):
    return "—" if v is None else f"{v:,}".replace(",", " ")


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
    r = api("sendMessage", **p)
    if not r.get("ok") and r.get("code") == 400 and p.get("parse_mode"):
        p.pop("parse_mode")                      # admin yozgan matnda HTML xato bo'lsa, oddiy matn sifatida yuboramiz
        r = api("sendMessage", **p)
    return r


def ikb(rows):
    return {"inline_keyboard": rows}


def answer(cq, text=None, alert=False):
    p = {"callback_query_id": cq["id"]}
    if text:
        p.update(text=text, show_alert=alert)
    api("answerCallbackQuery", **p)


def edit_or_send(cq, chat, text, markup=None):
    mid = cq.get("message", {}).get("message_id")
    if mid:
        r = api("editMessageText", chat_id=chat, message_id=mid, text=text, parse_mode="HTML",
                disable_web_page_preview=True, reply_markup=markup or ikb([]))
        if r.get("ok"):
            return
    send(chat, text, markup)


def main_kb(uid):
    off = db["buttons_off"]
    rows = []
    if db["cfg"]["recent"]:
        recent = []
        for x in reversed(db["history"].get(str(uid), [])):
            if x not in recent:
                recent.append(x)
            if len(recent) == 4:
                break
        rows += [[{"text": "@" + x} for x in recent[i:i + 2]] for i in range(0, len(recent), 2)]
    for pair in (("b_track", "b_analytics"), ("b_settings", "b_support")):
        row = [{"text": tr(uid, k)} for k in pair if k not in off]
        if row:
            rows.append(row)
    if is_admin(uid):
        rows.append([{"text": tr(uid, "b_admin_stats")}, {"text": tr(uid, "b_admin_settings")}])
    return {"keyboard": rows, "resize_keyboard": True} if rows else {"remove_keyboard": True}


def lang_kb():
    return ikb([[{"text": "🇺🇿 O'zbek tili", "callback_data": "lang:uz"}],
                [{"text": "🇷🇺 Русский язык", "callback_data": "lang:ru"}]])


def button_action(text):
    """Pastki tugma matnidan amalni topadi (admin o'zgartirgan nomlar ham hisobga olinadi)."""
    for act, key in (("track", "b_track"), ("analytics", "b_analytics"), ("settings", "b_settings"),
                     ("support", "b_support"), ("astats", "b_admin_stats"), ("asettings", "b_admin_settings")):
        if any(text_for(lg, key) == text for lg in T):
            return act
    return None


# ---------------------------------------------------------------- provayder
class ProviderError(Exception):
    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}")
        self.code = code


def provider_get(kind, value, param="username"):
    """Apify Instagram Scraper'ni ishga tushiradi va natijalarni datasetdan oladi."""
    if not APIFY_TOKEN:
        raise ProviderError("not_configured")
    result_types = {
        "profile": "details", "posts": "posts", "reels": "reels",
        "stories": "stories", "tagged": "mentions", "media": "posts",
    }
    result_type = result_types.get(kind)
    if not result_type:
        raise ProviderError("unsupported", f"{kind} Apify actorida qo'llanmaydi")
    direct_url = value if param == "url" else f"https://www.instagram.com/{value}/"
    actor_id = APIFY_ACTOR.replace("/", "~")
    endpoint = (f"https://api.apify.com/v2/acts/{urllib.parse.quote(actor_id, safe='~')}"
                f"/run-sync-get-dataset-items?token={urllib.parse.quote(APIFY_TOKEN)}&timeout=180")
    payload = {
        "resultsType": result_type,
        "directUrls": [direct_url],
        "resultsLimit": 20 if kind in ("posts", "reels", "stories", "tagged") else 1,
    }
    req = urllib.request.Request(
        endpoint, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=210) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        code = {401: "not_configured", 403: "private", 404: "not_found", 429: "rate_limit"}.get(e.code, "error")
        raise ProviderError(code, f"Apify HTTP {e.code}: {detail}")
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise ProviderError("error", repr(e))
    if isinstance(data, list):
        return {"items": data}
    if isinstance(data, dict):
        if data.get("error"):
            raise ProviderError("error", str(data.get("error"))[:500])
        rows = data.get("items") or data.get("data") or []
        return {"items": rows} if isinstance(rows, list) else rows
    return {"items": []}

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
    return {"username": str(pick(d, "username", "ownerUsername") or username).lower(),
            "full_name": pick(d, "full_name", "fullName", "ownerFullName", "name") or "",
            "bio": pick(d, "bio", "biography") or "",
            "avatar": pick(d, "avatar_url", "profilePicUrlHd", "profilePicUrl", "profile_pic_url_hd", "profile_pic_url"),
            "followers": to_int(pick(d, "followers", "followersCount", "follower_count")),
            "following": to_int(pick(d, "following", "followsCount", "following_count")),
            "posts": to_int(pick(d, "posts", "postsCount", "media_count")),
            "private": bool(pick(d, "is_private", "isPrivate", "private")),
            "stories": bool(pick(d, "has_stories", "hasStories", "has_story"))}


def map_items(d):
    raw = d.get("items") if isinstance(d, dict) else d
    out = []
    for it in raw or []:
        if not isinstance(it, dict):
            continue
        video = pick(it, "video_url", "videoUrl")
        url = video or pick(it, "url", "image_url", "display_url", "displayUrl", "coverUrl", "media_url")
        if not url and isinstance(it.get("images"), list) and it["images"]:
            first = it["images"][0]
            url = first if isinstance(first, str) else pick(first, "url", "src")
        if not url:
            continue
        kind = str(pick(it, "type", "media_type") or "").lower()
        out.append({"url": url, "video": bool(video) or kind in ("video", "reel"),
                    "caption": pick(it, "caption", "text") or "", "taken": pick(it, "taken_at", "takenAt", "timestamp", "takenAtIso"),
                    "likes": to_int(pick(it, "likes", "likesCount", "like_count")),
                    "comments": to_int(pick(it, "comments", "commentsCount", "comment_count")),
                    "views": to_int(pick(it, "views", "videoViewCount", "videoPlayCount", "view_count", "play_count")),
                    "link": pick(it, "link", "permalink", "url")})
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
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "socket_timeout": 20}
    if PROXY:
        opts["proxy"] = PROXY
    try:
        with yt_dlp.YoutubeDL(opts) as y:
            info = y.extract_info(url, download=False)
    except Exception as e:
        s = str(e)
        print("[yt-dlp]", s[:300])
        if any(x in s for x in ("getaddrinfo", "timed out", "Connection", "Errno 110", "Network is unreachable",
                                "ProxyError", "SSL")):
            raise ProviderError("network", s[:200])
        raise ProviderError("not_found", s[:200])
    items = []
    for e in info.get("entries") or [info]:
        link = e.get("url") or (e.get("formats") or [{}])[-1].get("url")
        if not link:
            continue
        video = e.get("vcodec") not in (None, "none") or str(e.get("ext", "")).lower() in ("mp4", "mov", "webm")
        items.append({"url": link, "video": video,
                      "caption": (e.get("description") or info.get("description") or "")[:200],
                      "taken": e.get("timestamp"), "likes": to_int(e.get("like_count")),
                      "comments": to_int(e.get("comment_count")), "views": to_int(e.get("view_count")), "link": None})
    return items


def fetch_post(url):
    if APIFY_TOKEN:
        try:
            return map_items(cached("media", url, param="url"))
        except ProviderError as e:
            if e.code != "error":
                raise
    items = ytdlp_media(url)
    if items is None:
        raise ProviderError("not_configured")
    return items


def provider_msg(uid, where, e):
    key = {"not_configured": "not_configured", "not_found": "not_found", "private": "private",
           "rate_limit": "rate_limit", "network": "network"}.get(e.code, "error")
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
    off = db["buttons_off"]

    def b(key, cb):
        return None if key in off else {"text": tr(uid, key), "callback_data": cb}

    rows = []
    if "btn_view" not in off:
        rows.append([{"text": "🔳 " + tr(uid, "btn_view"), "url": f"https://www.instagram.com/{name}/"}])
    for pair in ([b("btn_stories", f"ig:st:{name}:0"), b("btn_posts", f"ig:po:{name}:0")],
                 [b("btn_highlights", f"ig:hl:{name}"), b("btn_reels", f"ig:re:{name}:0")],
                 [b("btn_refresh", f"ig:rf:{name}"), b("btn_tagged", f"ig:tg:{name}:0")],
                 [b("btn_track", f"ig:tr:{name}"), b("btn_analytics", f"ig:an:{name}")]):
        row = [x for x in pair if x]
        if row:
            rows.append(row)
    return ikb(rows)


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
    limit = db["cfg"]["daily_limit"]
    today = datetime.now().strftime("%Y-%m-%d")
    if u["day"] != today:
        u["day"], u["count"] = today, 0
    if is_admin(uid) or not limit:
        return True
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
    db["downloads"] += 1
    for it in items[:10]:
        send_item(chat, it)


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
    rows = s[-15:]
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
    send(chat, tr(uid, "analytics_pick"), ikb([[{"text": "@" + n, "callback_data": f"ig:an:{n}"}] for n in recent[:8]]))


def settings_kb(uid, on):
    return ikb([[{"text": tr(uid, "btn_lang"), "callback_data": "set:lang"}],
                [{"text": tr(uid, "btn_notif_on" if on else "btn_notif_off"), "callback_data": "set:notif"}],
                [{"text": tr(uid, "btn_clear"), "callback_data": "set:clear"}],
                [{"text": tr(uid, "btn_delete"), "callback_data": "set:del"}]])


# ---------------------------------------------------------------- admin panel
def stats_panel():
    now = time.time()
    today0 = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    us = list(db["users"].values())
    tracked = len({n for v in db["tracked"].values() for n in v})
    has_ytdlp = importlib.util.find_spec("yt_dlp") is not None
    if not PROVIDER_URL and not has_ytdlp:
        tip = "⚠️ Ma'lumot manbasi ham, yt-dlp ham yo'q: profil va post ma'lumoti olinmaydi."
    elif not PROVIDER_URL:
        tip = "⚠️ Ma'lumot manbasi (PROVIDER_URL) sozlanmagan: profil ma'lumotlari chiqmaydi, post havolasi ishlaydi."
    elif db["errors"] and now - db["errors"][-1]["t"] < 3600:
        tip = "⚠️ So'nggi soatda xatoliklar bo'lgan, \"Xatoliklar\" tugmasini tekshiring."
    else:
        tip = "Botingiz holati a'lo darajada! ✅"
    line = "━━━━━━━━━━━━━━━"
    text = (f"📊 <b>BOT STATISTIKASI:</b>\n{line}\n"
            f"👥 <b>Foydalanuvchilar:</b>\n"
            f"├ Jami: <b>{len(us)}</b> ta\n"
            f"├ Bugun qo'shilgan: <b>{sum(1 for x in us if x['created'] >= today0)}</b> ta\n"
            f"├ Bugun kirganlar (DAU): <b>{sum(1 for x in us if x['last'] >= today0)}</b> ta\n"
            f"├ Haftalik faol: <b>{sum(1 for x in us if now - x['last'] < 7 * 86400)}</b> ta\n"
            f"└ Cheklanganlar: <b>{sum(1 for x in us if x['banned'])}</b> ta\n{line}\n"
            f"🔎 <b>Faoliyat:</b>\n"
            f"├ Profil qidiruvlari: <b>{db['searches']}</b> ta\n"
            f"├ Yuklangan postlar: <b>{db['downloads']}</b> ta\n"
            f"└ Kuzatuvdagi profillar: <b>{tracked}</b> ta\n{line}\n"
            f"⚙️ <b>Tizim:</b>\n"
            f"├ Bot holati: {'🟢 ishlayapti' if db['cfg']['enabled'] else '🔴 to&#39;xtatilgan'}\n"
            f"├ Ma'lumot manbasi: {'✅ ulangan' if PROVIDER_URL else '⚠️ sozlanmagan'}\n"
            f"├ yt-dlp: {'✅ o&#39;rnatilgan' if has_ytdlp else '❌ yo&#39;q'}\n"
            f"└ Xatoliklar: <b>{len(db['errors'])}</b> ta\n{line}\n"
            f"💡 <b>Tavsiya:</b>\n<i>{tip}</i>\n\n"
            f"⏳ Yangilangan vaqt: {datetime.now():%d.%m.%Y %H:%M:%S}")
    kb = ikb([[{"text": "🔄 Yangilash", "callback_data": "adm:stats"}],
              [{"text": "⚙️ Tizim sozlamalari", "callback_data": "adm:settings"}],
              [{"text": "📣 Ommaviy xabar", "callback_data": "adm:bc"},
               {"text": "👤 Foydalanuvchi", "callback_data": "adm:user"}],
              [{"text": "🐞 Xatoliklar", "callback_data": "adm:errors"}]])
    return text, kb


def settings_panel():
    c = db["cfg"]
    limit = c["daily_limit"] or "cheksiz"
    state = "🟢 ishlayapti" if c["enabled"] else "🔴 to'xtatilgan"
    text = ("⚙️ <b>Tizim sozlamalari:</b>\n\nBu yerda botning asosiy ishlash holatini, foydalanuvchilarga "
            f"yuboriladigan matnlarni va tugmalarni tahrirlashingiz mumkin.\n\nBot: {state}\nKunlik limit: {limit}")
    kb = ikb([[{"text": "🔴 Botni to'xtatish" if c["enabled"] else "🟢 Botni yoqish", "callback_data": "adm:enabled"}],
              [{"text": ("✅" if c["recent"] else "❌") + " Oxirgi qidiruvlar tugmalari", "callback_data": "adm:recent"}],
              [{"text": f"📛 Kunlik limit: {limit}", "callback_data": "adm:limit"}],
              [{"text": "📄 Matnlar", "callback_data": "adm:texts"}, {"text": "🎛 Tugmalar", "callback_data": "adm:buttons"}],
              [{"text": "⚠️ Matnlarni zavod holatiga qaytarish", "callback_data": "adm:factory"}],
              [{"text": "⬅️ Boshqaruvga qaytish", "callback_data": "adm:stats"}]])
    return text, kb


def list_panel(kind):
    items = EDIT_TEXTS if kind == "texts" else EDIT_BTNS
    btns = []
    for key, name in items:
        mark = "✏️ " if any(db["texts"][lg].get(key) for lg in T) else ""
        if kind == "buttons" and key in db["buttons_off"]:
            mark = "🚫 "
        btns.append({"text": mark + name, "callback_data": f"adm:i:{key}"})
    rows = [btns[i:i + 2] for i in range(0, len(btns), 2)]
    rows.append([{"text": "⬅️ Orqaga", "callback_data": "adm:settings"}])
    title = "📄 <b>Matnlar</b>" if kind == "texts" else "🎛 <b>Tugmalar</b>"
    return title + "\n\nTahrirlash uchun tanlang. ✏️ — o'zgartirilgan" + (", 🚫 — yashirilgan." if kind == "buttons" else "."), ikb(rows)


def item_panel(key):
    is_btn = key in BTN_KEYS
    text = f"<b>{h(NAMES[key])}</b> (<code>{key}</code>)\n\n" + "\n".join(
        f"{lg.upper()}: <code>{h(text_for(lg, key)[:700])}</code>" for lg in T)
    if key in HINTS:
        text += "\n\n" + h(HINTS[key])
    if is_btn and key in db["buttons_off"]:
        text += "\n\n🚫 Hozir yashirilgan."
    rows = [[{"text": "✏️ UZ", "callback_data": f"adm:e:uz:{key}"}, {"text": "✏️ RU", "callback_data": f"adm:e:ru:{key}"}]]
    if is_btn:
        rows.append([{"text": "✅ Ko'rsatish" if key in db["buttons_off"] else "🚫 Yashirish", "callback_data": f"adm:t:{key}"}])
    rows.append([{"text": "♻️ Standart", "callback_data": f"adm:r:{key}"},
                 {"text": "⬅️ Orqaga", "callback_data": "adm:buttons" if is_btn else "adm:texts"}])
    return text, ikb(rows)


def user_panel(uid):
    x = db["users"].get(str(uid))
    if not x:
        return "Foydalanuvchi topilmadi.", None
    text = (f"👤 ID: <code>{uid}</code> @{h(str(x.get('username') or '-'))}\nTil: {x['lang'] or '-'}\n"
            f"Ro'yxatdan: {datetime.fromtimestamp(x['created']):%d.%m.%Y}\n"
            f"Oxirgi faollik: {datetime.fromtimestamp(x['last']):%d.%m.%Y %H:%M}\n"
            f"Bugungi so'rovlar: {x['count']}\nTarix: {len(db['history'].get(str(uid), []))}\n"
            f"Kuzatuv: {len(db['tracked'].get(str(uid), []))}\n"
            f"Holat: {'⛔ cheklangan' if x['banned'] else '✅ faol'}")
    kb = None
    if uid not in ADMIN_IDS:
        kb = ikb([[{"text": "✅ Blokdan chiqarish" if x["banned"] else "⛔ Cheklash", "callback_data": f"adm:b:{uid}"}]])
    return text, kb


def errors_text():
    e = db["errors"][-8:]
    return "🐞 <b>Oxirgi xatoliklar</b>\n\n" + ("\n\n".join(
        f"{datetime.fromtimestamp(x['t']):%d.%m %H:%M} {h(x['w'])}\n<code>{h(x['m'][-250:])}</code>" for x in e)
        or "Xatolik yo'q ✅")


def handle_adm_callback(cq, uid, chat, parts):
    u = user(uid)
    u["state"] = None
    what = parts[1] if len(parts) > 1 else "stats"
    answer(cq)
    c = db["cfg"]
    if what == "stats":
        text, kb = stats_panel()
        edit_or_send(cq, chat, text, kb)
    elif what == "settings":
        edit_or_send(cq, chat, *settings_panel())
    elif what == "enabled":
        c["enabled"] = not c["enabled"]
        edit_or_send(cq, chat, *settings_panel())
    elif what == "recent":
        c["recent"] = not c["recent"]
        edit_or_send(cq, chat, *settings_panel())
        send(chat, "Klaviatura yangilandi.", main_kb(uid))
    elif what == "limit":
        u["state"] = "adm_limit"
        send(chat, "Kunlik limitni raqam bilan yuboring (0 = cheksiz). Bekor qilish: /cancel")
    elif what in ("texts", "buttons"):
        edit_or_send(cq, chat, *list_panel(what))
    elif what == "i" and len(parts) > 2 and parts[2] in NAMES:
        edit_or_send(cq, chat, *item_panel(parts[2]))
    elif what == "e" and len(parts) > 3 and parts[2] in T and parts[3] in NAMES:
        u["state"] = f"adm_edit:{parts[2]}:{parts[3]}"
        extra = ("\n" + h(HINTS[parts[3]])) if parts[3] in HINTS else ""
        send(chat, f"Yangi {'tugma nomini' if parts[3] in BTN_KEYS else 'matnni'} yuboring ({parts[2].upper()})."
                   f"{extra}\nBekor qilish: /cancel")
    elif what == "t" and len(parts) > 2 and parts[2] in BTN_KEYS:
        off = db["buttons_off"]
        off.remove(parts[2]) if parts[2] in off else off.append(parts[2])
        edit_or_send(cq, chat, *item_panel(parts[2]))
    elif what == "r" and len(parts) > 2 and parts[2] in NAMES:
        for lg in T:
            db["texts"][lg].pop(parts[2], None)
        if parts[2] in db["buttons_off"]:
            db["buttons_off"].remove(parts[2])
        edit_or_send(cq, chat, *item_panel(parts[2]))
    elif what == "factory":
        edit_or_send(cq, chat, "⚠️ Barcha o'zgartirilgan matnlar va tugma nomlari standartga qaytariladi, yashirilgan "
                               "tugmalar qayta ko'rinadi. Davom etasizmi?",
                     ikb([[{"text": "Ha, qaytarish", "callback_data": "adm:fyes"},
                           {"text": "Bekor qilish", "callback_data": "adm:settings"}]]))
    elif what == "fyes":
        db["texts"] = {lg: {} for lg in T}
        db["buttons_off"] = []
        edit_or_send(cq, chat, *settings_panel())
        send(chat, "✅ Zavod holatiga qaytarildi.", main_kb(uid))
    elif what == "bc":
        u["state"] = "adm_bc"
        send(chat, "Yuboriladigan xabar matnini yozing. Bekor qilish: /cancel")
    elif what == "user":
        u["state"] = "adm_user"
        send(chat, "Foydalanuvchi Telegram ID'sini yuboring. Bekor qilish: /cancel")
    elif what == "errors":
        edit_or_send(cq, chat, errors_text(), ikb([[{"text": "⬅️ Boshqaruvga qaytish", "callback_data": "adm:stats"}]]))
    elif what == "b" and len(parts) > 2 and parts[2].isdigit() and int(parts[2]) not in ADMIN_IDS:
        t = user(int(parts[2]))
        t["banned"] = not t["banned"]
        edit_or_send(cq, chat, *user_panel(int(parts[2])))


def handle_admin_state(uid, chat, text):
    """True qaytarsa, xabar admin holati sifatida qayta ishlangan."""
    u = user(uid)
    st = u["state"] or ""
    if st == "adm_limit":
        if not text.isdigit() or int(text) > 100000:
            send(chat, "Faqat raqam yuboring (0 = cheksiz).")
            return True
        db["cfg"]["daily_limit"] = int(text)
        u["state"] = None
        send(chat, "✅ Saqlandi.")
        send(chat, *settings_panel())
        return True
    if st.startswith("adm_edit:"):
        _, lang, key = st.split(":", 2)
        val = " ".join(text.split())[:40] if key in BTN_KEYS else text[:3500]
        if not val:
            send(chat, "Bo'sh bo'lmasin.")
            return True
        db["texts"][lang][key] = val
        u["state"] = None
        send(chat, "✅ Saqlandi. Yangi matn darhol kuchga kiradi.")
        send(chat, *item_panel(key))
        return True
    if st == "adm_bc":
        PENDING_BC[uid] = text
        u["state"] = None
        n = sum(1 for x in db["users"].values() if not x["banned"])
        send(chat, f"{h(text)}\n\n— Yuqoridagi matn {n} ta foydalanuvchiga yuboriladi.",
             ikb([[{"text": "✅ Yuborish", "callback_data": "bc:yes"}, {"text": "❌ Bekor", "callback_data": "bc:no"}]]))
        return True
    if st == "adm_user":
        if not text.isdigit():
            send(chat, "Faqat raqamli ID yuboring.")
            return True
        u["state"] = None
        send(chat, *user_panel(int(text)))
        return True
    return False


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


def handle_message(m):
    if m["chat"]["type"] != "private":
        return
    uid, chat = m["from"]["id"], m["chat"]["id"]
    u = user(uid)
    u["last"] = time.time()
    u["username"] = m["from"].get("username")
    admin = is_admin(uid)
    if u["banned"] and not admin:
        return
    text = (m.get("text") or "").strip()
    if not text:
        return
    if not db["cfg"]["enabled"] and not admin:
        send(chat, tr(uid, "maintenance"))
        return
    cmd = text.split()[0].split("@")[0].lower() if text.startswith("/") else ""
    if admin and cmd in ("/admin", "/cancel", "/reply", "/ban", "/unban"):
        arg = text[len(text.split()[0]):].strip()
        if cmd == "/admin":
            u["state"] = None
            send(chat, *stats_panel())
        elif cmd == "/cancel":
            u["state"] = None
            send(chat, "Bekor qilindi.")
        else:
            parts = arg.split(None, 1)
            target = int(parts[0]) if parts and parts[0].isdigit() else None
            if target is None:
                send(chat, f"Format: {cmd} ID" + (" matn" if cmd == "/reply" else ""))
            elif cmd == "/reply" and len(parts) > 1:
                send(target, "💬 " + h(parts[1]))
                send(chat, "✅ Yuborildi.")
            elif cmd in ("/ban", "/unban") and target not in ADMIN_IDS:
                user(target)["banned"] = cmd == "/ban"
                send(chat, "✅ Bajarildi.")
        return
    if not u["lang"]:
        send(chat, T["uz"]["choose_lang"], lang_kb())
        return
    if cmd in ("/start", "/help"):
        u["state"] = None
        show_start(uid, chat)
        return
    act = button_action(text)
    if act and (admin or act not in ("astats", "asettings")):
        u["state"] = None
        if act == "track":
            show_tracked(uid, chat)
        elif act == "analytics":
            show_analytics_pick(uid, chat)
        elif act == "settings":
            send(chat, tr(uid, "settings_title"), settings_kb(uid, u["notif"]))
        elif act == "support":
            u["state"] = "support"
            send(chat, tr(uid, "support_prompt"))
        elif act == "astats":
            send(chat, *stats_panel())
        elif act == "asettings":
            send(chat, *settings_panel())
        return
    if admin and handle_admin_state(uid, chat, text):
        return
    if u["state"] == "support":
        u["state"] = None
        who = f"@{u['username']}" if u["username"] else m["from"].get("first_name", "")
        for a in ADMIN_IDS:
            send(a, f"📩 Support\nID: <code>{uid}</code> {h(who)}\n\n{h(text)}\n\n/reply {uid} javob")
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
    admin = is_admin(uid)
    if u["banned"] and not admin:
        answer(cq)
        return
    parts = cq.get("data", "").split(":")
    head = parts[0]
    if head == "adm":
        if admin:
            handle_adm_callback(cq, uid, chat, parts)
        else:
            answer(cq, "Ruxsat yo'q", True)
        return
    if head == "bc":
        answer(cq)
        text = PENDING_BC.pop(uid, None) if admin else None
        if parts[1:2] == ["yes"] and text:
            ok = fail = 0
            for k, x in list(db["users"].items()):
                if x["banned"]:
                    continue
                r = send(int(k), h(text))
                ok, fail = (ok + 1, fail) if r.get("ok") else (ok, fail + 1)
                time.sleep(0.05)
            send(chat, f"📣 Tugadi. Yuborildi: {ok}, xato: {fail}")
        return
    if head == "lang" and len(parts) > 1 and parts[1] in T:
        u["lang"] = parts[1]
        answer(cq)
        show_start(uid, chat)
        return
    if not db["cfg"]["enabled"] and not admin:
        answer(cq, tr(uid, "maintenance"), True)
        return
    if not u["lang"]:
        answer(cq)
        send(chat, T["uz"]["choose_lang"], lang_kb())
        return
    if head == "ig" and len(parts) > 2 and USERNAME.match(parts[2]):
        code, name = parts[1], parts[2]
        arg = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
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
    else:
        answer(cq)


def handle_update(upd):
    if "message" in upd and "from" in upd["message"]:
        handle_message(upd["message"])
    elif "callback_query" in upd:
        handle_callback(upd["callback_query"])


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
                if user(uid)["notif"] and not user(uid)["banned"]:
                    send(uid, tr(uid, "track_note", u=h(name), what=tr(uid, what[0], **what[1])))
        time.sleep(1)
    save()


def main():
    try:
        import sys
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
    if not APIFY_TOKEN:
        print("Eslatma: APIFY_TOKEN topilmadi, Instagram ma'lumotlari olinmaydi.")
    print("Telegram'da botga /start yuboring. Admin panel: /admin. To'xtatish: Ctrl+C")
    offset, last_track = 0, time.time()
    while True:
        try:
            res = api("getUpdates", offset=offset, timeout=30, allowed_updates=["message", "callback_query"])
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
