const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type TokenResponse = {
  access_token: string;
  token_type: string;
  company_id: string;
  user_id: string;
};

export type RulePredicate = {
  field: string;
  operator: string;
  value: string | number | boolean | string[];
  description?: string | null;
};

export type Role = {
  id: string;
  title: string;
  department: string | null;
  location: string | null;
  employment_type: string | null;
  status: string;
  brief_text: string;
  stated_filters: RulePredicate[];
  hidden_filters: RulePredicate[];
  jd: Record<string, unknown> | null;
};

export type Company = {
  id: string;
  name: string;
  slug: string;
  auto_approve_gate1: boolean;
  auto_approve_gate2: boolean;
};

function authHeaders(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export async function register(body: {
  company_name: string;
  company_slug: string;
  email: string;
  password: string;
  full_name: string;
}): Promise<TokenResponse> {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse(res);
}

export async function login(body: { email: string; password: string }): Promise<TokenResponse> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse(res);
}

export async function getCompany(token: string): Promise<Company> {
  const res = await fetch(`${API_BASE}/companies/me`, { headers: authHeaders(token) });
  return parse(res);
}

export async function updateCompany(
  token: string,
  body: Partial<Pick<Company, "auto_approve_gate1" | "auto_approve_gate2" | "name">>,
): Promise<Company> {
  const res = await fetch(`${API_BASE}/companies/me`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  return parse(res);
}

export async function listRoles(token: string): Promise<Role[]> {
  const res = await fetch(`${API_BASE}/roles`, { headers: authHeaders(token) });
  return parse(res);
}

export async function createRole(
  token: string,
  body: {
    title: string;
    department?: string;
    location?: string;
    employment_type?: string;
    brief_text: string;
    stated_filters?: RulePredicate[];
    hidden_filters?: RulePredicate[];
    extract_filters?: boolean;
  },
): Promise<Role> {
  const res = await fetch(`${API_BASE}/roles`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  return parse(res);
}

export async function generateJd(
  token: string,
  roleId: string,
): Promise<{ role_id: string; jd: Record<string, unknown>; stub: boolean }> {
  const res = await fetch(`${API_BASE}/roles/${roleId}/generate-jd`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return parse(res);
}

export { API_BASE };
