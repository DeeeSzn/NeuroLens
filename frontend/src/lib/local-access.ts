const HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

export function isLocalRequest(
  host: string | null,
  origin: string | null,
  fetchSite: string | null,
): boolean {
  if (!host || fetchSite === "cross-site") return false;
  try {
    const target = new URL(`http://${host}`);
    if (
      !HOSTS.has(target.hostname) || target.username || target.password ||
      target.pathname !== "/" || target.search || target.hash
    ) return false;
    if (origin === null) return true;
    const source = new URL(origin);
    return (
      source.protocol === "http:" && HOSTS.has(source.hostname) &&
      (source.port || "80") === (target.port || "80") &&
      !source.username && !source.password && source.pathname === "/" &&
      !source.search && !source.hash
    );
  } catch (error) {
    if (!(error instanceof TypeError)) throw error;
    return false;
  }
}
