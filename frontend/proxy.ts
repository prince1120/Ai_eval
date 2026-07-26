import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  const hasSession = request.cookies.has("access_token");

  if (!hasSession) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/transcripts/:path*",
    "/templates/:path*",
    "/team/:path*",
    "/llm-costs/:path*",
    "/settings/:path*",
    "/analysis-runs/:path*",
  ],
};
