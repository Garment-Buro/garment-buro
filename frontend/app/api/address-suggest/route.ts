import { NextRequest, NextResponse } from "next/server";

import { getAddressSuggestions } from "@/lib/server/geocoding/service";

export async function GET(request: NextRequest) {
    const query = request.nextUrl.searchParams.get("q")?.trim() || "";
    const city = request.nextUrl.searchParams.get("city")?.trim() || "";

    if (query.length < 3) {
        return NextResponse.json([]);
    }

    try {
        return NextResponse.json(await getAddressSuggestions(query, city));
    } catch (error) {
        console.error("[Address Suggest] Error:", error);
        return NextResponse.json(
            { error: "Address suggestions are temporarily unavailable" },
            { status: 502 },
        );
    }
}
