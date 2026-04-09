/** Public folder URLs (respects Astro `base` for GitHub project pages). */
export function publicAsset(path: string): string {
  const rawBase = import.meta.env.BASE_URL;
  const base = rawBase.replace(/\/$/, "");
  const clean = path.replace(/^\//, "");
  if (base === "") return `/${clean}`;
  return `${base}/${clean}`;
}
