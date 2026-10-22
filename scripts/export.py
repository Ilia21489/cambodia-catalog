"""Выгружает каталог Baza Nova из Buildin в data/projects.json и assets/."""
import io
import json
import re
import shutil
from pathlib import Path

import httpx
from PIL import Image

ROOT_PAGE = "16265c88-cfbf-49e7-9d6f-2a401e8073b6"
SKIP_PAGES = {"Чеклист"}
API = "https://buildin.ai/api"
BASE = Path(__file__).resolve().parent.parent
ASSETS = BASE / "assets"
MAX_WIDTH = 1600

T_PAGE, T_TEXT, T_BULLET, T_HEADING, T_DIVIDER, T_COLUMNS, T_COLUMN, T_FILE, T_TABLE, T_ROW = 0, 1, 4, 7, 9, 10, 11, 14, 27, 28

client = httpx.Client(timeout=60, follow_redirects=True)


def blocks(uid: str) -> dict:
    return client.get(f"{API}/docs/{uid}").json()["data"]["blocks"]


def signed_urls(items: list[tuple[str, str]]) -> list[str]:
    urls = []
    for i in range(0, len(items), 40):
        batch = [{"blockId": b, "ossName": o, "isPublic": True} for b, o in items[i:i + 40]]
        urls += [d["url"] for d in client.post(f"{API}/file/create_urls", json={"batch": batch}).json()["data"]]
    return urls


def rich(segments) -> str:
    out = []
    for s in segments or []:
        text = (s.get("text") or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if s.get("enhancer", {}).get("bold"):
            text = f"<b>{text}</b>"
        out.append(text)
    return "".join(out).strip().replace("\n", "<br>")


def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def save_image(data: bytes, path: Path, ext: str) -> tuple[str, int, int]:
    if ext == "svg":
        path = path.with_suffix(".svg")
        path.write_bytes(data)
        return path.name, 0, 0
    img = Image.open(io.BytesIO(data))
    if img.width > MAX_WIDTH:
        img = img.resize((MAX_WIDTH, round(img.height * MAX_WIDTH / img.width)), Image.LANCZOS)
    if img.mode in ("P", "LA") or "transparency" in img.info:
        img = img.convert("RGBA")
    if img.mode == "RGBA" and img.getchannel("A").getextrema()[0] < 250:
        path = path.with_suffix(".webp")
        img.save(path, "WEBP", quality=85)
    else:
        path = path.with_suffix(".jpg")
        img.convert("RGB").save(path, "JPEG", quality=84, optimize=True)
    return path.name, img.width, img.height


def export_project(uid: str, title: str) -> dict:
    B = blocks(uid)
    slug = slugify(title)
    folder = ASSETS / slug
    folder.mkdir(parents=True, exist_ok=True)

    files = [(b["uuid"], b["data"]["ossName"]) for b in B.values() if b["type"] == T_FILE and b["data"].get("ossName")]
    url_of = dict(zip([f[0] for f in files], signed_urls(files)))

    sections = [{"title": "", "blocks": []}]
    counter = 0

    def add(block):
        sections[-1]["blocks"].append(block)

    def walk(node_id):
        nonlocal counter
        b = B.get(node_id)
        if not b:
            return
        t, d = b["type"], b.get("data", {})
        if t == T_HEADING:
            sections.append({"title": rich(d.get("segments")), "blocks": []})
        elif t == T_TEXT:
            html = rich(d.get("segments"))
            if html:
                add({"t": "text", "html": html})
        elif t == T_BULLET:
            html = rich(d.get("segments"))
            if html:
                last = sections[-1]["blocks"][-1] if sections[-1]["blocks"] else None
                if last and last["t"] == "list":
                    last["items"].append(html)
                else:
                    add({"t": "list", "items": [html]})
        elif t == T_FILE and node_id in url_of:
            data = client.get(url_of[node_id]).content
            ext = (d.get("extName") or "").lower()
            counter += 1
            if d.get("display") == "image" or ext in ("png", "jpg", "jpeg", "webp", "svg"):
                name, w, h = save_image(data, folder / f"{counter:03d}", ext)
                add({"t": "image", "src": f"assets/{slug}/{name}", "w": w, "h": h})
            else:
                name = re.sub(r"[^\w.\-]+", "_", rich(d.get("segments")) or f"file.{ext}")
                (folder / name).write_bytes(data)
                add({"t": "file", "name": rich(d.get("segments")), "src": f"assets/{slug}/{name}"})
        elif t == T_TABLE:
            order = d.get("format", {}).get("tableBlockColumnOrder", [])
            rows = []
            for rid in b.get("subNodes", []):
                props = B.get(rid, {}).get("data", {}).get("collectionProperties", {})
                rows.append([rich(props.get(c)) for c in order])
            rows = [r for r in rows if any(r)]
            if rows:
                add({"t": "table", "header": d.get("format", {}).get("tableBlockRowHeader", False), "rows": rows})
            return
        if t in (T_PAGE, T_COLUMNS, T_COLUMN) or t not in (T_TABLE,):
            for child in b.get("subNodes", []):
                walk(child)

    walk(uid)
    sections = [s for s in sections if s["blocks"] or s["title"]]
    return {"id": uid, "slug": slug, "title": title, "sections": sections}


DISTRICTS = [("Туол Корк", r"Toul Kork|Туол Корк"), ("Кох Пич", r"Koh Pich|Кох Пич"),
             ("Чруй Чангвар", r"Chroy Changvar|Чруй Чангвар"), ("Сиануквиль", r"Сиануквил|Sihanoukville"),
             ("Даун Пень", r"Daun Penh|Даун Пень"), ("Тонле Басак", r"Tonle Bassac|Тонле Басак"),
             ("Сен Сок", r"Sen Sok|Сен Сок"), ("Чамкармон", r"Chamkarmon|Чамкармон"), ("Мин Чей", r"Мин Чей|Mean Chey"),
             ("Отрес", r"Отрес|Otres")]


def plain(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).replace("&amp;", "&")


def summarize(p: dict) -> dict:
    titles = [s["title"] for s in p["sections"] if s["title"]]
    blocks_ = [b for s in p["sections"] for b in s["blocks"]]
    images = [b for b in blocks_ if b["t"] == "image" and not b["src"].endswith(".svg")]
    text = " ".join(plain(b.get("html", "")) + " " + " ".join(map(plain, b.get("items", [])))
                    + " " + " ".join(plain(c) for r in b.get("rows", []) for c in r) for b in blocks_)
    loc = next((s for s in p["sections"] if "РАСПОЛОЖЕНИЕ" in s["title"].upper()), None)
    loc_text = " ".join(plain(b.get("html", "")) + " ".join(map(plain, b.get("items", []))) for b in (loc or {}).get("blocks", []))
    city = "Сиануквиль" if any("СИАНУКВИЛ" in t.upper() for t in titles) else "Пномпень"
    bkk = re.search(r"(?:ВКК|BKK)[- ]?(\d)", loc_text) or re.search(r"(?:ВКК|BKK)[- ]?(\d)", plain(" ".join(titles[:3])))
    district = f"ВКК{bkk.group(1)}" if bkk else next((n for n, rx in DISTRICTS if re.search(rx, loc_text)), "")
    highlights = []
    m = re.search(r"рассрочк\w*[^0-9]{0,40}?(\d+[–-]?\d*)\s*мес", text, re.I)
    if m:
        highlights.append(f"Рассрочка {m.group(1)} мес")
    m = re.search(r"доходност\w*[^0-9]{0,30}?(\d+[,.]?\d*\s*[–-]?\s*\d*[,.]?\d*)\s*%", text, re.I)
    if m:
        highlights.append(f"Доходность {m.group(1).replace(' ', '')}%")
    m = re.search(r"взнос\w*[^0-9]{0,20}?(\d+)\s*%", text, re.I)
    if m:
        highlights.append(f"Взнос от {m.group(1)}%")
    p.update({
        "heading": plain(titles[0]).strip() if titles else p["title"],
        "tagline": plain(titles[1]).strip() if len(titles) > 1 else "",
        "cover": next((b["src"] for b in images if b["h"] > b["w"] >= 600), images[0]["src"] if images else ""),
        "city": city,
        "district": district or city,
        "highlights": highlights[:3],
        "pdf": next((b["src"] for b in blocks_ if b["t"] == "file" and b["src"].endswith(".pdf")), ""),
    })
    return p


def main():
    root = blocks(ROOT_PAGE)
    pages = [(u, root[u]["title"]) for u in root[ROOT_PAGE]["subNodes"]
             if u in root and root[u]["type"] == T_PAGE and root[u]["title"] not in SKIP_PAGES]
    if ASSETS.exists():
        shutil.rmtree(ASSETS)
    projects = []
    for uid, title in pages:
        print(f"Выгружаю {title}…")
        projects.append(summarize(export_project(uid, title)))
    (BASE / "data").mkdir(exist_ok=True)
    (BASE / "data" / "projects.json").write_text(json.dumps(projects, ensure_ascii=False, indent=1))
    print(f"Готово: {len(projects)} проектов")


if __name__ == "__main__":
    import sys
    if "--summarize" in sys.argv:
        path = BASE / "data" / "projects.json"
        data = [summarize(p) for p in json.loads(path.read_text())]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    else:
        main()
