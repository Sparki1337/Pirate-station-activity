const data = window.CHAT_DASHBOARD_DATA;

const labels = {
  video_sticker: "Видео-стикеры",
  animated_sticker: "Аним. стикеры",
  sticker: "Стикеры",
  photo: "Фото",
  video: "Видео",
  file: "Файлы",
  voice: "Голосовые",
  round_video: "Круговые видео",
  media: "Прочее",
};

const assetLabels = {
  photos: "Фото",
  photoThumbs: "Миниатюры фото",
  stickers: "WebP-стикеры",
  animatedStickers: "TGS-стикеры",
  videoFiles: "Видео",
  videoStickers: "Видео-стикеры",
  voiceMessages: "Голосовые",
  roundVideoMessages: "Круговые видео",
  files: "Файлы",
};

const palette = ["#ffffff", "#d8d8d8", "#bdbdbd", "#9f9f9f", "#828282", "#666666", "#4f4f4f", "#393939", "#262626"];

const fmt = new Intl.NumberFormat("ru-RU");
const dateFmt = new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit" });
const fullDateFmt = new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "long", year: "numeric" });
const chartMeta = new Map();
const tooltip = document.createElement("div");
tooltip.className = "chart-tooltip";
document.body.appendChild(tooltip);

let sortKey = "messages";
let sortDir = "desc";

function $(selector) {
  return document.querySelector(selector);
}

function getCss(name) {
  return getComputedStyle(document.body).getPropertyValue(name).trim();
}

function formatNumber(value) {
  return fmt.format(value || 0);
}

function shortDate(iso) {
  return dateFmt.format(new Date(iso));
}

function fullDate(iso) {
  return fullDateFmt.format(new Date(iso));
}

function mediaName(name) {
  return labels[name] || name;
}

function clearCanvas(canvas) {
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.max(1, Math.floor(rect.width * dpr));
  canvas.height = Math.max(1, Math.floor((canvas.getAttribute("height") || rect.height) * dpr));
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, rect.width, rect.height);
  return { ctx, width: rect.width, height: Number(canvas.getAttribute("height")) || rect.height };
}

function showTooltip(html, event) {
  tooltip.innerHTML = html;
  tooltip.classList.add("is-visible");
  const offset = 16;
  const rect = tooltip.getBoundingClientRect();
  const x = Math.min(event.clientX + offset, window.innerWidth - rect.width - 12);
  const y = Math.min(event.clientY + offset, window.innerHeight - rect.height - 12);
  tooltip.style.left = `${Math.max(12, x)}px`;
  tooltip.style.top = `${Math.max(12, y)}px`;
}

function hideTooltip() {
  tooltip.classList.remove("is-visible");
}

function drawLineChart(canvas, rows) {
  const { ctx, width, height } = clearCanvas(canvas);
  const text = getCss("--text");
  const muted = getCss("--muted");
  const line = getCss("--line");
  const strong = getCss("--strong");
  const pad = { top: 12, right: 14, bottom: 34, left: 48 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const max = Math.max(...rows.map((row) => row.messages), 1);
  const points = rows.map((row, i) => {
    const x = pad.left + (plotW * i) / Math.max(rows.length - 1, 1);
    const y = pad.top + plotH - (row.messages / max) * plotH;
    return { ...row, x, y };
  });

  ctx.strokeStyle = line;
  ctx.lineWidth = 1;
  ctx.font = "11px system-ui";
  ctx.fillStyle = muted;
  for (let i = 0; i <= 4; i++) {
    const y = pad.top + (plotH * i) / 4;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(width - pad.right, y);
    ctx.stroke();
    const label = Math.round(max - (max * i) / 4);
    ctx.fillText(formatNumber(label), 6, y + 4);
  }

  ctx.strokeStyle = strong;
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  points.forEach((point, i) => {
    if (i === 0) ctx.moveTo(point.x, point.y);
    else ctx.lineTo(point.x, point.y);
  });
  ctx.stroke();

  points.forEach((point, i) => {
    if (i % Math.ceil(points.length / 8) !== 0 && i !== points.length - 1) return;
    ctx.fillStyle = muted;
    ctx.fillText(point.date.slice(5), point.x - 14, height - 12);
  });

  const top = [...points].sort((a, b) => b.messages - a.messages).slice(0, 3);
  top.forEach((point) => {
    ctx.fillStyle = strong;
    ctx.beginPath();
    ctx.arc(point.x, point.y, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillText(formatNumber(point.messages), point.x + 8, Math.max(14, point.y - 8));
  });

  ctx.fillStyle = text;
  chartMeta.set(canvas, { type: "line", rows, points });
}

function drawVerticalBars(canvas, rows) {
  const { ctx, width, height } = clearCanvas(canvas);
  const muted = getCss("--muted");
  const line = getCss("--line");
  const strong = getCss("--strong");
  const pad = { top: 12, right: 10, bottom: 30, left: 42 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const max = Math.max(...rows.map((row) => row.messages), 1);
  const barGap = 4;
  const barW = Math.max(3, plotW / rows.length - barGap);

  ctx.strokeStyle = line;
  ctx.font = "11px system-ui";
  for (let i = 0; i <= 3; i++) {
    const y = pad.top + (plotH * i) / 3;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(width - pad.right, y);
    ctx.stroke();
  }

  const bars = rows.map((row, i) => {
    const barH = (row.messages / max) * plotH;
    const x = pad.left + i * (barW + barGap);
    const y = pad.top + plotH - barH;
    ctx.fillStyle = strong;
    ctx.fillRect(x, y, barW, barH);
    if (i % 3 === 0) {
      ctx.fillStyle = muted;
      ctx.fillText(row.hour, x - 1, height - 10);
    }
    return { ...row, x, y, width: barW, height: barH };
  });
  chartMeta.set(canvas, { type: "bars", bars });
}

function drawDonut(canvas, rows) {
  const { ctx, width, height } = clearCanvas(canvas);
  const total = rows.reduce((sum, row) => sum + row.value, 0);
  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.min(width, height) * 0.35;
  const inner = radius * 0.58;
  let start = -Math.PI / 2;
  const slices = [];

  rows.forEach((row, i) => {
    const angle = total ? (row.value / total) * Math.PI * 2 : 0;
    const end = start + angle;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, radius, start, end);
    ctx.closePath();
    ctx.fillStyle = palette[i % palette.length];
    ctx.fill();
    slices.push({ ...row, start, end, total, color: palette[i % palette.length], cx, cy, radius, inner });
    start += angle;
  });

  ctx.globalCompositeOperation = "destination-out";
  ctx.beginPath();
  ctx.arc(cx, cy, inner, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalCompositeOperation = "source-over";

  ctx.fillStyle = getCss("--text");
  ctx.font = "700 24px system-ui";
  ctx.textAlign = "center";
  ctx.fillText(formatNumber(total), cx, cy - 2);
  ctx.fillStyle = getCss("--muted");
  ctx.font = "12px system-ui";
  ctx.fillText("медиа", cx, cy + 20);
  ctx.textAlign = "left";
  chartMeta.set(canvas, { type: "donut", slices });
}

function renderSummary() {
  const o = data.overview;
  const cards = [
    ["Сообщений", o.analyzedMessages],
    ["Участников (в периоде)", o.participants],
    ["Слов", o.totalWords],
    ["Медиа", o.mediaItems],
    ["Ссылок", o.linkItems],
    ["Ответов", `${o.replyRate}%`],
  ];
  $("#summaryGrid").innerHTML = cards
    .map(([label, value], i) => `
      <div class="metric" style="--i:${i}">
        <span class="metric-value">${typeof value === "number" ? formatNumber(value) : value}</span>
        <span class="metric-label">${label}</span>
      </div>
    `)
    .join("");
  $("#dateRange").textContent = `${fullDate(o.dateStart)} - ${fullDate(o.dateEnd)}`;
}

function renderTopBars() {
  const rows = data.activity.top10Users;
  const max = Math.max(...rows.map((row) => row.messages), 1);
  $("#topUsersBars").innerHTML = rows
    .map((row, i) => `
      <div class="bar-row" title="${row.name}" style="--i:${i}">
        <div class="bar-name">${row.name}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${(row.messages / max) * 100}%"></div></div>
        <div class="bar-value">${formatNumber(row.messages)}</div>
      </div>
    `)
    .join("");
}

function renderMedia() {
  const rows = data.media.types;
  drawDonut($("#mediaChart"), rows);
  $("#mediaLegend").innerHTML = rows
    .map((row, i) => `
      <div class="legend-item" style="--i:${i}">
        <span class="legend-label"><span style="color:${palette[i % palette.length]}">■</span> ${mediaName(row.name)}</span>
        <span class="legend-value">${formatNumber(row.value)}</span>
      </div>
    `)
    .join("");

  const inv = data.media.assetInventory.keyCounts;
  $("#assetGrid").innerHTML = Object.entries(inv)
    .filter(([, value]) => value)
    .map(([key, value], i) => `
      <div class="asset-item" style="--i:${i}">
        <span class="asset-label">${assetLabels[key] || key}</span>
        <span class="asset-value">${formatNumber(value)}</span>
      </div>
    `)
    .join("");
}

function renderHeatmap() {
  const rows = data.activity.heatmap;
  const max = Math.max(...rows.map((row) => row.messages), 1);
  const weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
  let html = `<div></div>${Array.from({ length: 24 }, (_, i) => `<div class="heat-label">${String(i).padStart(2, "0")}</div>`).join("")}`;
  weekdays.forEach((day) => {
    html += `<div class="heat-label">${day}</div>`;
    rows
      .filter((row) => row.weekday === day)
      .forEach((row, i) => {
        const opacity = 0.1 + (row.messages / max) * 0.9;
        const cellIndex = weekdays.indexOf(day) * 24 + i;
        html += `<div class="heat-cell" title="${day} ${row.hour}:00 - ${formatNumber(row.messages)}" style="--i:${cellIndex}; background: color-mix(in srgb, var(--strong) ${Math.round(opacity * 100)}%, var(--panel-2));"></div>`;
      });
  });
  $("#heatmap").innerHTML = html;
}

function renderWords() {
  const rows = data.content.topWords.slice(0, 32);
  const max = Math.max(...rows.map((row) => row.value), 1);
  $("#wordCloud").innerHTML = rows
    .map((row) => {
      const size = 13 + (row.value / max) * 24;
      return `<span class="word" style="--i:${rows.indexOf(row)}; font-size:${size}px">${row.name} <small>&nbsp;${formatNumber(row.value)}</small></span>`;
    })
    .join("");

  $("#phraseList").innerHTML = data.content.topBigrams
    .slice(0, 12)
    .map((row, i) => `<div class="stack-item" style="--i:${i}"><span class="stack-label">${row.name}</span><span class="stack-value">${formatNumber(row.value)}</span></div>`)
    .join("");
}

function renderUsersTable() {
  const rows = [...data.activity.topUsers].sort((a, b) => {
    const av = a[sortKey];
    const bv = b[sortKey];
    let an = parseFloat(av);
    let bn = parseFloat(bv);
    if (!Number.isNaN(an) && !Number.isNaN(bn)) {
      return sortDir === "asc" ? an - bn : bn - an;
    }
    const as = String(av).toLowerCase();
    const bs = String(bv).toLowerCase();
    return sortDir === "asc" ? as.localeCompare(bs, "ru") : bs.localeCompare(as, "ru");
  });
  $("#usersTable").innerHTML = rows
    .slice(0, 30)
    .map((row, i) => `
      <tr style="--i:${i}">
        <td>${row.name}</td>
        <td>${formatNumber(row.messages)}</td>
        <td>${row.share}%</td>
        <td>${formatNumber(row.words)}</td>
        <td>${formatNumber(row.media)}</td>
        <td>${formatNumber(row.replies)}</td>
        <td>${row.avgWords}</td>
        <td>${row.topWord || ""}</td>
      </tr>
    `)
    .join("");
}

function initTableSort() {
  const table = document.querySelector("#usersTable")?.closest("table");
  if (!table) return;
  const thead = table.querySelector("thead");
  thead.addEventListener("click", (e) => {
    const th = e.target.closest("th[data-sort]");
    if (!th) return;
    const key = th.dataset.sort;
    if (sortKey === key) {
      sortDir = sortDir === "asc" ? "desc" : "asc";
    } else {
      sortKey = key;
      sortDir = "desc";
    }
    renderUsersTable();
    thead.querySelectorAll("th").forEach((el) => el.classList.remove("is-asc", "is-desc"));
    th.classList.add(sortDir === "asc" ? "is-asc" : "is-desc");
  });
}

function renderLists() {
  $("#topDaysList").innerHTML = data.activity.topDays
    .slice(0, 10)
    .map((row, i) => `
      <div class="stack-item" style="--i:${i}">
        <span class="stack-label">${shortDate(row.date)} · ${row.activeUsers} участников · лидер: ${row.topUser}</span>
        <span class="stack-value">${formatNumber(row.messages)}</span>
      </div>
    `)
    .join("");
}

function handleChartMove(event) {
  const canvas = event.currentTarget;
  const meta = chartMeta.get(canvas);
  if (!meta) return;
  const rect = canvas.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;

  if (meta.type === "line") {
    const point = meta.points.reduce((nearest, item) => Math.abs(item.x - x) < Math.abs(nearest.x - x) ? item : nearest, meta.points[0]);
    showTooltip(`<strong>${fullDate(point.date)}</strong>${formatNumber(point.messages)} сообщений`, event);
    return;
  }

  if (meta.type === "bars") {
    const bar = meta.bars.find((item) => x >= item.x && x <= item.x + item.width);
    if (!bar) {
      hideTooltip();
      return;
    }
    showTooltip(`<strong>${String(bar.hour).padStart(2, "0")}:00</strong>${formatNumber(bar.messages)} сообщений`, event);
    return;
  }

  if (meta.type === "donut") {
    const slice = meta.slices[0];
    if (!slice) return;
    const dx = x - slice.cx;
    const dy = y - slice.cy;
    const distance = Math.hypot(dx, dy);
    if (distance < slice.inner || distance > slice.radius) {
      hideTooltip();
      return;
    }
    let angle = Math.atan2(dy, dx);
    if (angle < -Math.PI / 2) angle += Math.PI * 2;
    const current = meta.slices.find((item) => angle >= item.start && angle <= item.end);
    if (!current) {
      hideTooltip();
      return;
    }
    const percent = current.total ? Math.round((current.value / current.total) * 100) : 0;
    showTooltip(`<strong>${mediaName(current.name)}</strong>${formatNumber(current.value)} · ${percent}%`, event);
  }
}

function addRipple(target, event) {
  const rect = target.getBoundingClientRect();
  const ripple = document.createElement("span");
  ripple.className = "click-ripple";
  ripple.style.left = `${event.clientX - rect.left}px`;
  ripple.style.top = `${event.clientY - rect.top}px`;
  target.appendChild(ripple);
  ripple.addEventListener("animationend", () => ripple.remove());
}

function initInteractions() {
  document.querySelectorAll("canvas").forEach((canvas) => {
    canvas.addEventListener("mousemove", handleChartMove);
    canvas.addEventListener("mouseleave", hideTooltip);
  });

  document.addEventListener("click", (event) => {
    const word = event.target.closest(".word");
    if (word) {
      word.classList.toggle("is-active");
      return;
    }

    const target = event.target.closest(".metric, .panel, .legend-item, .asset-item, .stack-item");
    if (target) addRipple(target, event);
  });
}

function renderCharts() {
  drawLineChart($("#dailyChart"), data.activity.days);
  drawVerticalBars($("#hourChart"), data.activity.hours);
  renderMedia();
}

function render() {
  renderSummary();
  renderTopBars();
  renderCharts();
  renderHeatmap();
  renderWords();
  renderUsersTable();
  renderLists();
}

render();
initInteractions();
initTableSort();
window.addEventListener("resize", () => requestAnimationFrame(renderCharts));
