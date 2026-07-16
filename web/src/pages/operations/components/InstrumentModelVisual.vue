<template>
  <svg class="instrument-visual" viewBox="0 0 320 132" role="img" :aria-label="`${model || name} 仪器示意图`">
    <defs>
      <linearGradient id="body" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#ffffff" />
        <stop offset="1" stop-color="#dce5ef" />
      </linearGradient>
      <linearGradient id="dark" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#263545" />
        <stop offset="1" stop-color="#07111e" />
      </linearGradient>
      <linearGradient id="glass" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#1d5261" />
        <stop offset="1" stop-color="#07131d" />
      </linearGradient>
      <filter id="shadow" x="-20%" y="-40%" width="140%" height="190%">
        <feGaussianBlur stdDeviation="4" />
      </filter>
    </defs>

    <ellipse cx="160" cy="119" rx="135" ry="10" fill="#9aabc0" opacity=".22" filter="url(#shadow)" />

    <g v-if="variant === 'gc'">
      <rect x="67" y="59" width="74" height="53" rx="3" fill="url(#dark)" />
      <rect x="72" y="65" width="58" height="39" rx="2" fill="#111d2a" />
      <circle cx="101" cy="84" r="17" fill="#070d15" stroke="#758aa0" stroke-width="3" />
      <circle cx="101" cy="84" r="10" fill="#1b2c3c" stroke="#b4c1cd" />
      <rect x="141" y="52" width="73" height="60" rx="3" fill="url(#body)" />
      <rect x="148" y="61" width="31" height="42" fill="url(#dark)" />
      <rect x="184" y="61" width="22" height="42" fill="#e8edf3" />
      <rect x="214" y="55" width="45" height="57" rx="3" fill="url(#body)" />
      <rect x="224" y="24" width="17" height="34" rx="2" fill="#d8e0e9" />
      <rect x="228" y="28" width="8" height="26" fill="#253342" />
      <rect x="221" y="68" width="31" height="6" rx="1" fill="#c4d0dc" />
      <path d="M67 59h73l9-8h57l8 4h45v6H67z" fill="#bfcbd7" />
    </g>

    <g v-else-if="variant === 'icp'">
      <rect x="44" y="54" width="91" height="57" rx="4" fill="url(#body)" />
      <rect x="52" y="63" width="55" height="38" rx="2" fill="#f5f7fa" />
      <rect x="112" y="64" width="18" height="37" fill="#cbd5df" />
      <rect x="135" y="49" width="88" height="62" rx="3" fill="url(#dark)" />
      <rect x="145" y="57" width="32" height="46" fill="#202d3a" />
      <rect x="181" y="57" width="35" height="46" fill="url(#glass)" />
      <circle cx="199" cy="77" r="7" fill="#071219" stroke="#58a18b" />
      <rect x="224" y="55" width="51" height="56" rx="3" fill="url(#body)" />
      <rect x="235" y="45" width="25" height="14" rx="2" fill="#aebdca" />
      <rect x="239" y="35" width="17" height="11" rx="4" fill="#8799a8" />
      <rect x="234" y="70" width="30" height="27" rx="2" fill="#ecf1f5" stroke="#c7d2dc" />
      <path d="M43 54h92l7-7h79l10 8h44v6H43z" fill="#d0dae4" />
    </g>

    <g v-else-if="variant === 'shimadzu'">
      <rect x="45" y="57" width="68" height="54" rx="3" fill="url(#dark)" />
      <path d="M45 57l14-11h54v11z" fill="#162333" />
      <rect x="57" y="68" width="42" height="8" rx="2" fill="#25384a" />
      <rect x="113" y="53" width="150" height="58" rx="3" fill="url(#body)" />
      <path d="M113 53l16-9h128l6 9z" fill="#182635" />
      <rect x="126" y="62" width="48" height="40" fill="#e8edf2" />
      <rect x="177" y="62" width="36" height="40" fill="#cad5df" />
      <rect x="216" y="62" width="39" height="40" fill="#f5f7f9" />
      <rect x="125" y="65" width="5" height="4" fill="#3b82f6" />
      <rect x="219" y="68" width="25" height="3" fill="#b9c5d0" />
    </g>

    <g v-else>
      <rect x="40" y="60" width="103" height="51" rx="3" fill="url(#dark)" />
      <path d="M40 60l13-10h90v10z" fill="#172637" />
      <rect x="50" y="69" width="35" height="29" rx="2" fill="#0b1622" />
      <rect x="57" y="75" width="21" height="4" fill="#2f6f8c" />
      <rect x="143" y="57" width="77" height="54" rx="3" fill="url(#body)" />
      <rect x="151" y="65" width="32" height="37" fill="#f7f9fb" />
      <rect x="187" y="65" width="25" height="37" fill="#dce4eb" />
      <rect x="220" y="52" width="51" height="59" rx="3" fill="url(#body)" />
      <rect x="230" y="43" width="24" height="15" rx="2" fill="#c4ced8" />
      <rect x="232" y="66" width="30" height="27" rx="2" fill="#e9eef3" stroke="#c6d1db" />
      <rect x="240" y="71" width="14" height="8" fill="#273746" />
      <rect x="149" y="63" width="5" height="3" fill="#3478d4" />
    </g>
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  name: string
  model?: string | null
}

const props = defineProps<Props>()

const variant = computed(() => {
  const text = `${props.name} ${props.model || ''}`.toLowerCase()
  if (text.includes('7000') || text.includes('gcms')) return 'gc'
  if (text.includes('icp')) return 'icp'
  if (text.includes('8050')) return 'shimadzu'
  return 'api'
})
</script>

<style scoped>
.instrument-visual {
  display: block;
  width: 100%;
  height: 100%;
  overflow: visible;
}
</style>
