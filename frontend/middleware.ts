import { NextResponse, type NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const origin = request.headers.get("origin");
  if ((origin && new URL(origin).host !== request.headers.get("host")) ||
      request.headers.get("sec-fetch-site") === "cross-site") {
    return new NextResponse(null, { status: 403 });
  }
  return NextResponse.next();
}

export const config = { matcher: ["/api/sessions/:path*", "/api/jobs", "/api/jobs/:path*", "/api/v1/:path*"] };
