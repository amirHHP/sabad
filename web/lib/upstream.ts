function apiBase(request: Request) {
  const configured = process.env.SABAD_API_URL?.replace(/\/$/, "");
  if (configured) return configured;
  if (process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`;
  const host = request.headers.get("x-forwarded-host") || request.headers.get("host");
  if (host && process.env.VERCEL) {
    const proto = request.headers.get("x-forwarded-proto") || "https";
    return `${proto}://${host}`;
  }
  return "http://127.0.0.1:8000";
}

export async function forwardToSabad(request: Request, path: string) {
  const body = await request.json();
  const forwarded = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  const headers: Record<string, string> = {
    "content-type": "application/json",
    "x-sabad-client": forwarded || "local",
  };
  if (process.env.SABAD_API_KEY) {
    headers.authorization = `Bearer ${process.env.SABAD_API_KEY}`;
  }
  const response = await fetch(`${apiBase(request)}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  return Response.json(payload, { status: response.status });
}
