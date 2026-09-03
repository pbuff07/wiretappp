const STORAGE_KEY = "wiretappp-theme";

export function resolveTheme() {
  if (typeof localStorage !== "undefined") {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark") return saved;
  }
  if (typeof window !== "undefined" && window.matchMedia) {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return "light";
}

export function getTheme() {
  return resolveTheme();
}

export function applyTheme(theme) {
  const next = theme === "dark" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(STORAGE_KEY, next);
  }
  return next;
}

export function initTheme() {
  return applyTheme(resolveTheme());
}

export function toggleTheme() {
  const next = getTheme() === "dark" ? "light" : "dark";
  return applyTheme(next);
}
