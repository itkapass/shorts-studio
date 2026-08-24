// _shared/auth.ts
//
// Supabase Edge Functions verify that a request carries *some* valid JWT
// before your code even runs — but the public anon key is itself a valid
// JWT, so "has a valid JWT" is not the same thing as "is a logged-in admin
// panel user". Every function in this folder calls requireUser() first and
// rejects with 401 if the caller is only holding the anon key. This is the
// same principle as the RLS fix in supabase/schema.sql: don't let holding
// the public client key be enough to do anything real.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

export async function requireUser(req: Request) {
  const authHeader = req.headers.get("Authorization") ?? "";
  const token = authHeader.replace("Bearer ", "");

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY")!;
  const client = createClient(supabaseUrl, anonKey, {
    global: { headers: { Authorization: authHeader } },
  });

  const { data, error } = await client.auth.getUser(token);
  if (error || !data?.user) {
    return { user: null, error: "Not authenticated. Log in to the Admin Panel and try again." };
  }
  return { user: data.user, error: null };
}

export function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
  });
}

export const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};
