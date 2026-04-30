<script setup lang="ts">
import { computed } from 'vue'
import type { ConfigField } from '@/types/audio'

const props = defineProps<{
  modelValue: Record<string, string>
  fields: ConfigField[]
  mode: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: Record<string, string>): void
}>()

const visibleFields = computed(() =>
  props.fields.filter(f => !f.mode_visibility.length || f.mode_visibility.includes(props.mode)),
)

function update(key: string, value: string) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

function htmlType(field: ConfigField): string {
  if (field.type === 'password') return 'password'
  if (field.type === 'number') return 'number'
  if (field.type === 'url') return 'url'
  return 'text'
}
</script>

<template>
  <div v-if="visibleFields.length" class="provider-fields">
    <div v-for="f in visibleFields" :key="f.key" class="form-group">
      <label :for="`provider_field_${f.key}`">{{ f.label }}</label>
      <input
        :id="`provider_field_${f.key}`"
        :type="htmlType(f)"
        :value="modelValue[f.key] ?? f.default"
        :placeholder="f.placeholder"
        :required="f.required"
        @input="update(f.key, ($event.target as HTMLInputElement).value)"
      >
      <p v-if="f.help" class="field-help">{{ f.help }}</p>
    </div>
  </div>
</template>

<style scoped>
.provider-fields {
  margin-top: 1rem;
}
.form-group + .form-group {
  margin-top: 0.6rem;
}
.field-help {
  font-size: 0.7rem;
  color: var(--text-dark-muted);
  margin-top: 0.25rem;
}
</style>
