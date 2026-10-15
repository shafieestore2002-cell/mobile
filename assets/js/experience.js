// Scroll changes the composition; native scrolling, links and shopping stay native.
const root = document.documentElement;
const track = document.querySelector("#hero-story");
const stage = document.querySelector("#story-stage");
const shape = document.querySelector("#story-morph");
const video = document.querySelector("#story-video");
const toggle = document.querySelector("#motion-toggle");
const media = matchMedia("(prefers-reduced-motion: reduce)");
const finePointer = matchMedia("(hover: hover) and (pointer: fine)");
const scenes = [...document.querySelectorAll("[data-scroll-scene]")];
const preferenceKey = "shafiee-motion-preference";
const clamp = (n, min = 0, max = 1) => Math.min(max, Math.max(min, n));
const smooth = (start, end, n) => {
  const p = clamp((n - start) / (end - start));
  return p * p * (3 - 2 * p);
};
let preference;
try {
  preference = localStorage.getItem(preferenceKey);
} catch {
  /* Session-only controls still work. */
}
let reduced = false;
let frame = 0;
let progress = 0;
let pointer = null;
let pointerCard = null;
let videoLoaded = false;
let lastSeek = 0;
const runningAnimations = new Set();
const revealed = new WeakSet();

function fluidPath(p) {
  const points = Array.from({ length: 10 }, (_, i) => {
    const angle = (i / 10) * Math.PI * 2 - Math.PI / 2;
    const radius =
      225 +
      28 * Math.sin(angle * 3 + p * Math.PI * 2) +
      12 * Math.cos(angle * 2 - p * 4);
    return [
      300 + Math.cos(angle) * radius * (1 + p * 0.2),
      300 + Math.sin(angle) * radius * (1 - p * 0.16),
    ];
  });
  let path = `M ${points[0][0].toFixed(2)} ${points[0][1].toFixed(2)}`;
  for (let i = 0; i < points.length; i++) {
    const previous = points[(i + points.length - 1) % points.length];
    const current = points[i];
    const next = points[(i + 1) % points.length];
    const after = points[(i + 2) % points.length];
    const c1 = current.map((v, j) => v + (next[j] - previous[j]) / 6);
    const c2 = next.map((v, j) => v - (after[j] - current[j]) / 6);
    path += ` C ${c1.map((v) => v.toFixed(2)).join(" ")} ${c2.map((v) => v.toFixed(2)).join(" ")} ${next.map((v) => v.toFixed(2)).join(" ")}`;
  }
  return path + " Z";
}

function resetPointer() {
  if (pointerCard) {
    for (const name of ["--tilt-x", "--tilt-y", "--pointer-x", "--pointer-y"])
      pointerCard.style.removeProperty(name);
  }
  pointerCard = null;
  pointer = null;
}

async function loadVideo() {
  if (reduced || videoLoaded || navigator.connection?.saveData) return;
  videoLoaded = true;
  const source = video.querySelector("source");
  try {
    // The short clip is fully buffered so scrubbing also works on static
    // development servers that don't support HTTP Range requests.
    const response = await fetch(source.dataset.src);
    if (!response.ok) throw new Error("Video unavailable");
    const blob = await response.blob();
    if (reduced) {
      videoLoaded = false;
      return;
    }
    video.src = URL.createObjectURL(blob);
    video.preload = "auto";
    video.load();
  } catch {
    video.dataset.unavailable = "true";
  }
}

function renderStory(p) {
  const portal = smooth(0.26, 0.94, p);
  stage.style.setProperty("--story-progress", p.toFixed(4));
  stage.style.setProperty("--portal-radius", `${(portal * 115).toFixed(2)}%`);
  stage.style.setProperty("--product-turn", `${(-12 + p * 27).toFixed(2)}deg`);
  stage.style.setProperty("--product-tilt", `${(p * -24).toFixed(2)}deg`);
  stage.style.setProperty(
    "--product-scale",
    (1 + smooth(0.05, 0.65, p) * 0.65).toFixed(4),
  );
  stage.style.setProperty(
    "--product-opacity",
    (1 - smooth(0.43, 0.72, p)).toFixed(4),
  );
  stage.style.setProperty(
    "--intro-opacity",
    (1 - smooth(0.16, 0.48, p)).toFixed(4),
  );
  stage.style.setProperty("--finale-opacity", smooth(0.49, 0.75, p).toFixed(4));
  stage.dataset.storyProgress = p.toFixed(3);
  stage.classList.toggle("is-portal", p > 0.5);
  document.querySelector(".story-copy").inert = p > 0.5;
  document.querySelector("#story-finale").inert = p <= 0.5;
  document.querySelector("#story-progress").style.transform = `scaleX(${p})`;
  document.querySelector("#story-chapter").textContent =
    p > 0.5 ? "02 — A CLOSER FEELING" : "01 — THE FIRST FEELING";
  shape.setAttribute("d", fluidPath(p));
  if (
    !reduced &&
    videoLoaded &&
    Number.isFinite(video.duration) &&
    !video.seeking
  ) {
    const targetTime =
      smooth(0.18, 0.98, p) * Math.max(0, video.duration - 0.08);
    if (
      Math.abs(video.currentTime - targetTime) > 0.075 &&
      performance.now() - lastSeek > 80
    ) {
      lastSeek = performance.now();
      video.currentTime = targetTime;
    }
  }
}

function tick() {
  frame = 0;
  if (reduced || document.hidden) return;
  // Read layout before writing styles, once per animation frame.
  const rect = track.getBoundingClientRect();
  const travel = Math.max(1, rect.height - stage.offsetHeight - 12);
  const target = clamp((12 - rect.top) / travel);
  const sceneMetrics = scenes.map((node) => ({
    node,
    rect: node.getBoundingClientRect(),
  }));
  const pointerBounds = pointer?.card.isConnected
    ? pointer.card.getBoundingClientRect()
    : null;
  const difference = target - progress;
  progress =
    Math.abs(difference) < 0.0015 ? target : progress + difference * 0.18;
  renderStory(progress);
  for (const metric of sceneMetrics) {
    if (metric.rect.top > innerHeight + 150 || metric.rect.bottom < -150)
      continue;
    const p = clamp(
      (innerHeight - metric.rect.top) / (innerHeight + metric.rect.height),
    );
    metric.node.style.setProperty("--scene-progress", p.toFixed(4));
  }
  if (pointer && pointerBounds) {
    if (pointerCard !== pointer.card) resetPointerStyles(pointerCard);
    pointerCard = pointer.card;
    const x = clamp((pointer.x - pointerBounds.left) / pointerBounds.width);
    const y = clamp((pointer.y - pointerBounds.top) / pointerBounds.height);
    pointerCard.style.setProperty(
      "--tilt-x",
      `${((0.5 - y) * 9).toFixed(2)}deg`,
    );
    pointerCard.style.setProperty(
      "--tilt-y",
      `${((x - 0.5) * 9).toFixed(2)}deg`,
    );
    pointerCard.style.setProperty("--pointer-x", `${(x * 100).toFixed(1)}%`);
    pointerCard.style.setProperty("--pointer-y", `${(y * 100).toFixed(1)}%`);
  }
  if (Math.abs(target - progress) > 0.0015) queue();
}

function resetPointerStyles(node) {
  if (!node) return;
  for (const property of ["--tilt-x", "--tilt-y", "--pointer-x", "--pointer-y"])
    node.style.removeProperty(property);
}

function queue() {
  if (!frame && !reduced && !document.hidden)
    frame = requestAnimationFrame(tick);
}

function makeLogoStatic() {
  customElements.whenDefined("shafiee-logo-motion").then(() => {
    if (!reduced) return;
    const logo = document.querySelector("#features shafiee-logo-motion");
    if (logo?.active) {
      logo.stop();
      logo.finished = true;
      logo.render(4.6);
    }
  });
}

function setMode() {
  reduced =
    preference === "reduced" || (preference !== "full" && media.matches);
  root.dataset.motion = reduced ? "reduced" : "full";
  toggle.hidden = false;
  toggle.setAttribute("aria-pressed", String(reduced));
  toggle.setAttribute(
    "aria-label",
    reduced ? "فعال‌کردن حرکت‌های صفحه" : "کاهش حرکت‌های صفحه",
  );
  document.querySelector("#motion-toggle-label").textContent = reduced
    ? "فعال‌کردن حرکت"
    : "کاهش حرکت";
  cancelAnimationFrame(frame);
  frame = 0;
  resetPointer();
  if (reduced) {
    for (const animation of runningAnimations) animation.finish();
    runningAnimations.clear();
    progress = 0;
    renderStory(0);
    video.pause();
    for (const node of scenes) node.style.setProperty("--scene-progress", ".5");
    makeLogoStatic();
  } else {
    loadVideo();
    queue();
  }
}

toggle.addEventListener("click", () => {
  preference = reduced ? "full" : "reduced";
  try {
    localStorage.setItem(preferenceKey, preference);
  } catch {
    /* Keep the current choice in memory. */
  }
  setMode();
});
media.addEventListener("change", () => {
  preference = null;
  setMode();
});
finePointer.addEventListener("change", resetPointer);
window.addEventListener("scroll", queue, { passive: true });
window.addEventListener("resize", queue, { passive: true });
window.addEventListener("pageshow", queue);
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    cancelAnimationFrame(frame);
    frame = 0;
    resetPointer();
    video.pause();
  } else queue();
});
document.addEventListener(
  "pointermove",
  (event) => {
    if (reduced || !finePointer.matches || event.pointerType === "touch")
      return;
    const card = event.target.closest("[data-tilt]");
    if (!card) {
      resetPointer();
      return;
    }
    pointer = { card, x: event.clientX, y: event.clientY };
    queue();
  },
  { passive: true },
);
document.addEventListener(
  "pointerout",
  (event) => {
    if (pointerCard && !pointerCard.contains(event.relatedTarget))
      resetPointer();
  },
  { passive: true },
);
document.addEventListener("focusin", resetPointer);
video.addEventListener("loadedmetadata", queue);
video.addEventListener("seeked", queue);
video.addEventListener("error", () => {
  video.dataset.unavailable = "true";
});

const revealObserver = new IntersectionObserver(
  (entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting || revealed.has(entry.target)) continue;
      revealed.add(entry.target);
      revealObserver.unobserve(entry.target);
      if (reduced) continue;
      const animation = entry.target.animate(
        [
          { opacity: 0.32, transform: "translateY(26px)", filter: "blur(3px)" },
          { opacity: 1, transform: "translateY(0)", filter: "blur(0)" },
        ],
        { duration: 750, easing: "cubic-bezier(.2,.7,.2,1)" },
      );
      runningAnimations.add(animation);
      animation.onfinish = () => runningAnimations.delete(animation);
    }
  },
  { threshold: 0.15 },
);
for (const node of document.querySelectorAll("[data-reveal]"))
  revealObserver.observe(node);
new ResizeObserver(queue).observe(track);
document.fonts.ready.then(queue);
setMode();
