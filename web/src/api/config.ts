import { api } from './client'

/** Persist a single config row (POST /api/config). Used by the auto-save UI in Settings. */
export async function saveConfigField(table: string, key: string, value: string): Promise<void> {
  await api('/config', {
    method: 'POST',
    body: JSON.stringify({ table, key, value }),
  })
}
