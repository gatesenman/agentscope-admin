/**
 * Sync vben preferences with the backend.
 *
 * On startup the saved preferences (if any) are applied so the backend is the
 * source of truth across devices; afterwards any preference change is
 * debounced and persisted back to the server. localStorage caching (vben's
 * default) still works as an offline fallback.
 */
import { toRaw, watch } from 'vue';

import { preferences, updatePreferences } from '@vben/preferences';

import {
  loadRemotePreferences,
  saveRemotePreferences,
} from '#/api/agentscope/preferences';

let applying = false;

export async function setupRemotePreferencesSync(): Promise<void> {
  // 1) Apply server-saved preferences (authoritative across devices).
  const remote = await loadRemotePreferences();
  if (remote) {
    applying = true;
    updatePreferences(remote);
    // Release the guard after the reactive flush so the apply itself does not
    // trigger an immediate save-back.
    setTimeout(() => {
      applying = false;
    }, 0);
  }

  // 2) Persist subsequent changes (debounced).
  let timer: null | ReturnType<typeof setTimeout> = null;
  watch(
    () => preferences,
    () => {
      if (applying) return;
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        void saveRemotePreferences(
          structuredClone(toRaw(preferences)) as Record<string, any>,
        );
      }, 800);
    },
    { deep: true },
  );
}
