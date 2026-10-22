const CONTACT = "ilya_e88";
const tg = window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData !== undefined
  ? window.Telegram.WebApp : null;
const inTelegram = Boolean(tg && tg.platform && tg.platform !== "unknown");
const app = document.getElementById("app");
const cta = document.getElementById("cta");
const lightbox = document.getElementById("lightbox");
let projects = [];
let filter = "Все";

if (inTelegram) {
  tg.ready();
  tg.expand();
}

const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
};
const plain = (html) => html.replace(/<[^>]+>/g, " ").replace(/&amp;/g, "&").replace(/\s+/g, " ").trim();
const absolute = (path) => new URL(path, location.href).href;

function contactLink(project) {
  const text = project
    ? `Здравствуйте! Интересует ${project.title}. Подскажите, пожалуйста, актуальные цены и наличие.`
    : "Здравствуйте! Хочу подобрать недвижимость в Камбодже.";
  return `https://t.me/${CONTACT}?text=${encodeURIComponent(text)}`;
}

function openLink(url) {
  if (!inTelegram) return window.open(url, "_blank", "noopener");
  if (url.startsWith("https://t.me/")) tg.openTelegramLink(url);
  else tg.openLink(url);
}

function setCta(project) {
  const label = project ? "Узнать цены и наличие" : "Подобрать квартиру";
  const url = contactLink(project);
  if (inTelegram) {
    tg.MainButton.offClick(tg.MainButton.__handler || (() => {}));
    tg.MainButton.__handler = () => openLink(url);
    tg.MainButton.setParams({ text: label, is_visible: true });
    tg.MainButton.onClick(tg.MainButton.__handler);
    return;
  }
  cta.textContent = label;
  cta.href = url;
  cta.hidden = false;
  document.body.classList.add("has-cta");
}

function renderHome() {
  if (inTelegram) tg.BackButton.hide();
  document.title = "Каталог новостроек — Best of Cambodia Property";
  app.replaceChildren();
  const wrap = el("div", "wrap");
  const intro = el("header", "intro");
  intro.append(el("p", "eyebrow", "Best of Cambodia Property"), el("h1", "", "Каталог новостроек"),
    el("p", "", `${projects.length} проектов в Пномпене и Сиануквиле — описания, планировки и условия покупки`));

  const districts = ["Все", ...new Set(projects.map((p) => p.city))];
  const chips = el("div", "chips");
  chips.setAttribute("role", "group");
  chips.setAttribute("aria-label", "Город");
  for (const d of districts) {
    const chip = el("button", "chip", d);
    chip.type = "button";
    chip.setAttribute("aria-pressed", String(d === filter));
    chip.onclick = () => { filter = d; renderHome(); };
    chips.append(chip);
  }

  const grid = el("div", "grid");
  for (const p of projects.filter((x) => filter === "Все" || x.city === filter)) {
    const card = el("a", "card");
    card.href = `#/p/${p.slug}`;
    const img = el("img");
    img.src = p.cover;
    img.alt = "";
    img.loading = "lazy";
    img.decoding = "async";
    const meta = el("div", "meta");
    meta.append(el("h2", "", p.title), el("p", "", p.tagline));
    card.append(img, el("span", "tag", p.district), meta);
    grid.append(card);
  }
  wrap.append(intro, chips, grid, el("p", "footer", "Нажмите на проект, чтобы посмотреть подробности"));
  app.append(wrap);
  setCta(null);
}

const HIDDEN_TEXT = [/^наш сайт/i, /^презентацию по проекту$/i];

function renderBlock(block, project) {
  if (block.t === "text") {
    if (HIDDEN_TEXT.some((rx) => rx.test(plain(block.html)))) return null;
    if (/^посмотреть на карте$/i.test(plain(block.html))) {
      const btn = actionButton("📍", "Посмотреть на карте", "Google Maps");
      const city = project.city === "Сиануквиль" ? "Sihanoukville" : "Phnom Penh";
      btn.onclick = () => openLink(`https://www.google.com/maps/search/${encodeURIComponent(`${project.title} ${city}`)}`);
      return btn;
    }
    const p = el("p");
    p.innerHTML = block.html;
    return p;
  }
  if (block.t === "list") {
    const ul = el("ul");
    for (const item of block.items) {
      const li = el("li");
      li.innerHTML = item;
      ul.append(li);
    }
    return ul;
  }
  if (block.t === "image") {
    const fig = el("figure");
    const img = el("img");
    img.src = block.src;
    img.alt = "";
    img.loading = "lazy";
    img.decoding = "async";
    if (block.w && block.h) { img.width = block.w; img.height = block.h; }
    if (block.src.endsWith(".svg") || (block.w && block.w < 400)) fig.classList.add("logo");
    else fig.onclick = () => openLightbox(block.src);
    fig.append(img);
    return fig;
  }
  if (block.t === "table") {
    const box = el("div", "table");
    const table = el("table");
    block.rows.forEach((row, i) => {
      const tr = el("tr");
      for (const cell of row) {
        const td = el(block.header && i === 0 ? "th" : "td");
        td.innerHTML = cell;
        tr.append(td);
      }
      table.append(tr);
    });
    box.append(table);
    return box;
  }
  if (block.t === "file") {
    const btn = actionButton("PDF", "Презентация проекта", "Откроется в браузере");
    btn.onclick = () => openLink(absolute(block.src));
    return btn;
  }
  return null;
}

function actionButton(icon, title, subtitle) {
  const btn = el("button", "action");
  btn.type = "button";
  const label = el("span");
  label.append(el("strong", "", title), el("small", "", subtitle));
  btn.append(el("span", "icon", icon), label);
  return btn;
}

function renderProject(project) {
  document.title = `${project.title} — Best of Cambodia Property`;
  app.replaceChildren();
  window.scrollTo(0, 0);
  if (inTelegram) {
    tg.BackButton.show();
  }

  const hero = el("section", "hero");
  const img = el("img");
  img.src = project.cover;
  img.alt = project.title;
  const meta = el("div", "meta");
  meta.append(el("p", "eyebrow", project.district === project.city ? project.city : `${project.district} · ${project.city}`), el("h1", "", project.title), el("p", "", project.tagline));
  hero.append(img, meta);
  if (!inTelegram) {
    const back = el("button", "back", "← Каталог");
    back.type = "button";
    back.onclick = () => { location.hash = ""; };
    hero.append(back);
  }

  const wrap = el("div", "wrap");
  if (project.highlights.length) {
    const facts = el("div", "facts");
    for (const h of project.highlights) facts.append(el("span", "fact", h));
    wrap.append(facts);
  }

  const skipTitles = new Set([project.heading, project.tagline].map((t) => t.toLowerCase()));
  project.sections.forEach((section, index) => {
    const title = plain(section.title);
    const blocks = section.blocks.filter((b) => !(index === 0 && b.t === "image") && b.src !== project.cover);
    if (!blocks.length) return;
    const sec = el("section", "section");
    if (title && !skipTitles.has(title.toLowerCase())) sec.append(el("h3", "", title));
    for (const b of blocks) {
      const node = renderBlock(b, project);
      if (node) sec.append(node);
    }
    wrap.append(sec);
  });
  wrap.append(el("p", "footer", "Цены и наличие юнитов меняются — уточняйте актуальную информацию у агента"));
  app.append(hero, wrap);
  setCta(project);
}

function openLightbox(src) {
  lightbox.querySelector("img").src = src;
  lightbox.hidden = false;
}
lightbox.onclick = () => { lightbox.hidden = true; };

function route() {
  const m = location.hash.match(/^#\/p\/(.+)$/);
  const project = m && projects.find((p) => p.slug === decodeURIComponent(m[1]));
  if (project) renderProject(project);
  else renderHome();
}

if (inTelegram) tg.BackButton.onClick(() => { location.hash = ""; });
window.addEventListener("hashchange", route);

fetch("data/projects.json")
  .then((r) => r.json())
  .then((data) => { projects = data; route(); })
  .catch(() => { app.textContent = "Не удалось загрузить каталог. Попробуйте открыть позже."; });
