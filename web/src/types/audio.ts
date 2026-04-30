/**
 * TypeScript twin of the backend's audio provider manifest dataclasses.
 * The frontend never hardcodes provider names; it reads these from
 * GET /api/audio/providers and renders the wizard/Settings dynamically.
 */

export type FieldType = 'text' | 'password' | 'number' | 'url'

export interface ConfigField {
  key: string
  label: string
  type: FieldType
  default: string
  placeholder: string
  help: string
  required: boolean
  mode_visibility: string[]
  storage_table: string
  storage_key: string
}

export interface SetupMode {
  id: string
  label: string
  description: string
  icon: string
}

export interface ProviderManifest {
  id: string
  label: string
  icon: string
  description: string
  setup_modes: SetupMode[]
  fields: ConfigField[]
}

export interface AudioState {
  provider: string
  mode: string
  config: Record<string, string>
}
