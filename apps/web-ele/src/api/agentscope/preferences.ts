/**
 * Remote persistence for vben frontend preferences.
 *
 * The backend stores the full preferences object per user (keyed by the
 * `X-User-ID` header) so UI settings follow the user across devices. We use
 * `fetch` directly (like `chat.ts`) because these calls run during app
 * bootstrap, before the axios client / pinia stores are initialised.
 */
import { useAppConfig } from '@vben/hooks';

import { getAgentScopeUserId } from './request';

const { apiURL } = useAppConfig(import.meta.env, import.meta.env.PROD);

/** Fetch the saved preferences for the current user (`null` if none/failed). */
export async function loadRemotePreferences(): Promise<null | Record<
  string,
  any
>> {
  try {
    const res = await fetch(`${apiURL}/preferences/`, {
      headers: { 'X-User-ID': getAgentScopeUserId() },
    });
    if (!res.ok) return null;
    const body = await res.json();
    const data = body?.data ?? {};
    return Object.keys(data).length > 0 ? data : null;
  } catch {
    return null;
  }
}

/** Persist the full preferences object for the current user. */
export async function saveRemotePreferences(
  data: Record<string, any>,
): Promise<void> {
  try {
    await fetch(`${apiURL}/preferences/`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'X-User-ID': getAgentScopeUserId(),
      },
      body: JSON.stringify({ data }),
    });
  } catch {
    // best-effort; preferences also persist to localStorage
  }
}
