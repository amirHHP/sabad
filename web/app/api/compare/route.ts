import { forwardToSabad } from "../../../lib/upstream";

export function POST(request: Request) {
  return forwardToSabad(request, "/api/v1/compare");
}
