import { redirect } from "next/navigation";

/**
 * `/analyze` was a near-duplicate of the home upload flow with none of the
 * progress, history or error handling. The home page supersedes it, so this
 * route now exists only to keep old links working.
 */
export default function AnalyzePage() {
  redirect("/");
}
