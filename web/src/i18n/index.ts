/**
 * vue-i18n setup. Locale defaults to French — that's the family-facing
 * language and what kids actually read. English and Arabic are bundled
 * for later switching but no UI to pick yet.
 *
 * For now this only powers the new tracker / combo strings; the rest of
 * the app keeps its hardcoded French strings until a separate migration
 * pass moves them in here.
 */
import { createI18n } from 'vue-i18n'
import fr from './locales/fr.json'
import en from './locales/en.json'
import ar from './locales/ar.json'

export const i18n = createI18n({
  legacy: false,
  locale: 'fr',
  fallbackLocale: 'fr',
  messages: { fr, en, ar },
})
