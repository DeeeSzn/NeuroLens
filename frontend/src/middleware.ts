import { NextRequest, NextResponse } from "next/server";
import { isLocalRequest } from "./lib/local-access";

export function middleware(request: NextRequest) {
  if (!isLocalRequest(
    request.headers.get("host"),
    request.headers.get("origin"),
    request.headers.get("sec-fetch-site"),
  )) {
    return new NextResponse("This instance only accepts local browser requests.", {
      status: 403,
    });
  }
  return NextResponse.next();
}
